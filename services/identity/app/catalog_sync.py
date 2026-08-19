"""Dominio canónico de catálogo y primera vertical del protocolo de sync."""

import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.errors import (
    SYNC_CONFLICT_NOT_FOUND,
    SYNC_CONFLICT_RESOLVED,
    SYNC_OPERATION_ID_CONFLICT,
    SYNC_OPERATION_UNSUPPORTED,
    SYNC_RESOLUTION_STALE,
    VALIDATION_ERROR,
    ApiError,
)
from app.models import (
    ConflictoEstado,
    ConflictoSync,
    CuentaNegocio,
    Establecimiento,
    NotificacionNegocio,
    OperacionSync,
    ProductoCatalogo,
    ProductoDestino,
    SyncAccion,
    SyncEstado,
)
from app.schemas import OperacionSyncRequest, ProductoPayload

MAX_OPERATION_BYTES = 1_000_000


def product_snapshot(product: ProductoCatalogo) -> dict:
    return {
        "id": str(product.id),
        "establecimiento_id": str(product.establecimiento_id),
        "nombre": product.nombre,
        "data_origin": product.data_origin.value,
        "categoria": product.categoria,
        "descripcion": product.descripcion,
        "destino": product.destino.value,
        "precio_centimos": product.precio_centimos,
        "moneda": product.moneda,
        "disponible": product.disponible,
        "revision": product.revision,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat(),
        "archived_at": product.archived_at.isoformat() if product.archived_at else None,
    }


def operation_response(db: Session, operation: OperacionSync) -> dict:
    conflict = (
        db.query(ConflictoSync).filter_by(operacion_id=operation.id).one_or_none()
        if operation.estado == SyncEstado.conflicto
        else None
    )
    return {
        "operation_id": operation.id,
        "estado": operation.estado.value,
        "aggregate_type": operation.aggregate_type,
        "aggregate_id": operation.aggregate_id,
        "action": operation.action.value,
        "base_revision": operation.base_revision,
        "global_revision": operation.global_revision,
        "result_snapshot": operation.result_snapshot,
        "conflict_id": conflict.id if conflict else None,
        "client_created_at": operation.client_created_at,
        "server_received_at": operation.server_received_at,
    }


def conflict_response(conflict: ConflictoSync, operation: OperacionSync) -> dict:
    return {
        "id": conflict.id,
        "operation_id": operation.id,
        "aggregate_type": operation.aggregate_type,
        "aggregate_id": operation.aggregate_id,
        "action": operation.action.value,
        "base_revision": operation.base_revision,
        "canonical_revision": conflict.canonical_revision,
        "base_snapshot": conflict.base_snapshot,
        "canonical_snapshot": conflict.canonical_snapshot,
        "proposed_snapshot": conflict.proposed_snapshot,
        "estado": conflict.estado.value,
        "device_id": operation.device_id,
        "client_created_at": operation.client_created_at,
        "server_received_at": operation.server_received_at,
        "created_at": conflict.created_at,
        "resolved_at": conflict.resolved_at,
    }


def _payload_dict(payload: ProductoPayload | None) -> dict | None:
    return payload.model_dump(mode="json") if payload is not None else None


def _validate_request(payload: OperacionSyncRequest) -> None:
    if payload.aggregate_type != "producto":
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=SYNC_OPERATION_UNSUPPORTED,
            detail="El tipo de operación todavía no está soportado",
        )
    if payload.action != "archivar" and payload.payload is None:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=VALIDATION_ERROR,
            detail="Crear o actualizar un producto requiere el payload completo",
        )
    if payload.client_created_at.utcoffset() is None:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=VALIDATION_ERROR,
            detail="client_created_at debe incluir zona horaria",
        )
    raw = payload.model_dump_json().encode("utf-8")
    if len(raw) > MAX_OPERATION_BYTES:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=VALIDATION_ERROR,
            detail="La operación supera el tamaño máximo de 1 MB",
        )


def _same_request(operation: OperacionSync, payload: OperacionSyncRequest) -> bool:
    return (
        operation.establecimiento_id is not None
        and operation.device_id == payload.device_id
        and operation.aggregate_type == payload.aggregate_type
        and operation.aggregate_id == payload.aggregate_id
        and operation.action.value == payload.action
        and operation.base_revision == payload.base_revision
        and operation.base_snapshot == payload.base_snapshot
        and operation.payload == _payload_dict(payload.payload)
    )


def _set_product_fields(product: ProductoCatalogo, payload: ProductoPayload) -> None:
    product.nombre = payload.nombre.strip()
    product.categoria = payload.categoria.strip()
    texto = (payload.descripcion or "").strip()
    product.descripcion = texto or None
    product.destino = ProductoDestino(payload.destino)
    product.precio_centimos = payload.precio_centimos
    product.moneda = payload.moneda
    product.disponible = payload.disponible


def _create_conflict(
    db: Session,
    operation: OperacionSync,
    canonical: ProductoCatalogo | None,
) -> ConflictoSync:
    canonical_data = product_snapshot(canonical) if canonical else None
    conflict = ConflictoSync(
        operacion_id=operation.id,
        establecimiento_id=operation.establecimiento_id,
        canonical_revision=canonical.revision if canonical else 0,
        base_snapshot=operation.base_snapshot,
        canonical_snapshot=canonical_data,
        proposed_snapshot=(
            {"id": str(operation.aggregate_id), "archived": True}
            if operation.action == SyncAccion.archivar
            else {"id": str(operation.aggregate_id), **(operation.payload or {})}
        ),
        estado=ConflictoEstado.pendiente,
    )
    db.add(conflict)
    db.flush()
    db.add(
        NotificacionNegocio(
            establecimiento_id=operation.establecimiento_id,
            conflicto_id=conflict.id,
            tipo="conflicto_sync",
            titulo="Cambio de producto pendiente de decisión",
            mensaje=(
                "Un cambio offline no coincide con la versión actual. "
                "Revisa los valores antes de aceptar o rechazar."
            ),
            payload={
                "conflicto_id": str(conflict.id),
                "aggregate_type": operation.aggregate_type,
                "aggregate_id": str(operation.aggregate_id),
                "action": operation.action.value,
                "deep_link": (
                    "personalhostel://establecimientos/"
                    f"{operation.establecimiento_id}/conflictos/{conflict.id}"
                ),
            },
        )
    )
    return conflict


def _apply_operation(
    operation: OperacionSync,
    establishment: Establecimiento,
    product: ProductoCatalogo | None,
    now: datetime,
) -> ProductoCatalogo | None:
    if operation.action in (SyncAccion.crear, SyncAccion.actualizar):
        validated = ProductoPayload.model_validate(operation.payload)
        if product is None:
            product = ProductoCatalogo(
                id=operation.aggregate_id,
                establecimiento_id=establishment.id,
                data_origin=establishment.data_origin,
                revision=1,
                created_at=now,
                updated_at=now,
            )
        else:
            product.revision += 1
            product.updated_at = now
        _set_product_fields(product, validated)
        product.archived_at = None
    elif product is not None:
        product.revision += 1
        product.disponible = False
        product.updated_at = now
        product.archived_at = now

    establishment.sync_revision += 1
    operation.estado = SyncEstado.aplicada
    operation.global_revision = establishment.sync_revision
    if product is not None:
        operation.result_snapshot = product_snapshot(product)
    else:
        operation.result_snapshot = {
            "id": str(operation.aggregate_id),
            "establecimiento_id": str(establishment.id),
            "archived_at": now.isoformat(),
        }
    return product


def process_operation(
    db: Session,
    establishment_id: uuid.UUID,
    account: CuentaNegocio,
    payload: OperacionSyncRequest,
) -> dict:
    _validate_request(payload)
    existing = db.get(OperacionSync, payload.operation_id)
    if existing is not None:
        if existing.establecimiento_id != establishment_id or not _same_request(existing, payload):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=SYNC_OPERATION_ID_CONFLICT,
                detail="El identificador de operación ya está asociado a otra intención",
            )
        return operation_response(db, existing)

    establishment = (
        db.query(Establecimiento)
        .filter(Establecimiento.id == establishment_id)
        .with_for_update()
        .one()
    )
    concurrent_existing = db.get(OperacionSync, payload.operation_id)
    if concurrent_existing is not None:
        if not _same_request(concurrent_existing, payload):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=SYNC_OPERATION_ID_CONFLICT,
                detail="El identificador de operación ya está asociado a otra intención",
            )
        return operation_response(db, concurrent_existing)
    any_product = (
        db.query(ProductoCatalogo)
        .filter(ProductoCatalogo.id == payload.aggregate_id)
        .with_for_update()
        .one_or_none()
    )
    if any_product is not None and any_product.establecimiento_id != establishment_id:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=SYNC_OPERATION_ID_CONFLICT,
            detail="El identificador del producto ya está en uso",
        )
    product = any_product
    now = datetime.now(UTC)
    operation = OperacionSync(
        id=payload.operation_id,
        establecimiento_id=establishment_id,
        device_id=payload.device_id,
        actor_type="negocio",
        actor_id=account.id,
        aggregate_type=payload.aggregate_type,
        aggregate_id=payload.aggregate_id,
        action=SyncAccion(payload.action),
        base_revision=payload.base_revision,
        base_snapshot=payload.base_snapshot,
        payload=_payload_dict(payload.payload),
        client_created_at=payload.client_created_at,
        server_received_at=now,
        estado=SyncEstado.conflicto,
    )
    db.add(operation)
    # No hay relationship ORM entre el sobre genérico y cada tipo de conflicto;
    # materializamos primero la FK para conservar ese desacoplamiento.
    db.flush()

    is_conflict = (
        operation.action == SyncAccion.crear
        and (product is not None or operation.base_revision != 0)
    ) or (
        operation.action in (SyncAccion.actualizar, SyncAccion.archivar)
        and (product is None or product.revision != operation.base_revision)
    )
    if is_conflict:
        _create_conflict(db, operation, product)
    else:
        product = _apply_operation(operation, establishment, product, now)
        if product is not None:
            db.add(product)

    db.commit()
    db.refresh(operation)
    return operation_response(db, operation)


def resolve_conflict(
    db: Session,
    establishment_id: uuid.UUID,
    conflict_id: uuid.UUID,
    account: CuentaNegocio,
    decision: str,
    expected_revision: int,
) -> dict:
    # Mantener el mismo orden de locks que process_operation evita el ciclo
    # establecimiento -> producto / producto -> establecimiento.
    establishment = (
        db.query(Establecimiento)
        .filter(Establecimiento.id == establishment_id)
        .with_for_update()
        .one()
    )
    conflict = (
        db.query(ConflictoSync)
        .filter_by(id=conflict_id, establecimiento_id=establishment_id)
        .with_for_update()
        .one_or_none()
    )
    if conflict is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=SYNC_CONFLICT_NOT_FOUND,
            detail="Conflicto no encontrado",
        )
    if conflict.estado != ConflictoEstado.pendiente:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=SYNC_CONFLICT_RESOLVED,
            detail="El conflicto ya fue resuelto",
        )
    operation = db.get(OperacionSync, conflict.operacion_id)
    product = (
        db.query(ProductoCatalogo)
        .filter(ProductoCatalogo.id == operation.aggregate_id)
        .with_for_update()
        .one_or_none()
    )
    if product is not None and product.establecimiento_id != establishment_id:
        product = None
    current_revision = product.revision if product else 0
    if expected_revision != conflict.canonical_revision or current_revision != expected_revision:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=SYNC_RESOLUTION_STALE,
            detail="El dato canónico cambió; refresca el conflicto antes de decidir",
        )

    now = datetime.now(UTC)
    conflict.resolved_at = now
    conflict.resolved_by = account.id
    if decision == "rechazar":
        conflict.estado = ConflictoEstado.rechazado
        operation.estado = SyncEstado.rechazada
    else:
        product = _apply_operation(operation, establishment, product, now)
        if product is not None:
            db.add(product)
        conflict.estado = ConflictoEstado.aceptado
    db.commit()
    db.refresh(conflict)
    db.refresh(operation)
    return conflict_response(conflict, operation)
