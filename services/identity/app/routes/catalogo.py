"""Catálogo canónico y endpoints de sincronización para mirrors offline."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_actor, get_current_cuenta_negocio
from app.catalog_sync import conflict_response, process_operation, resolve_conflict
from app.db import get_negocio_db
from app.errors import (
    ESTABLECIMIENTO_NOT_FOUND,
    MEMBERSHIP_FORBIDDEN,
    NOTIFICACION_NOT_FOUND,
    ApiError,
)
from app.models import (
    ConflictoEstado,
    ConflictoSync,
    CuentaNegocio,
    Establecimiento,
    Membresia,
    MembresiaEstado,
    NotificacionNegocio,
    OperacionSync,
    ProductoCatalogo,
    SyncEstado,
)
from app.schemas import (
    CambiosSyncResponse,
    CatalogoResponse,
    ConflictoSyncResponse,
    ErrorResponse,
    NotificacionNegocioResponse,
    OperacionSyncRequest,
    OperacionSyncResponse,
    ResolverConflictoRequest,
)

router = APIRouter(prefix="/v1/establecimientos", tags=["catálogo y sincronización"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}


def _get_establishment(db: Session, establishment_id: uuid.UUID) -> Establecimiento:
    establishment = db.get(Establecimiento, establishment_id)
    if establishment is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    return establishment


def _owner_establishment(
    db: Session, establishment_id: uuid.UUID, account: CuentaNegocio
) -> Establecimiento:
    establishment = _get_establishment(db, establishment_id)
    if establishment.cuenta_negocio_id != account.id:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=MEMBERSHIP_FORBIDDEN,
            detail="La cuenta no tiene acceso a este establecimiento",
        )
    return establishment


def _readable_establishment(
    db: Session, establishment_id: uuid.UUID, actor: tuple[str, uuid.UUID]
) -> Establecimiento:
    establishment = _get_establishment(db, establishment_id)
    actor_type, actor_id = actor
    if actor_type == "negocio" and actor_id == establishment.cuenta_negocio_id:
        return establishment
    if actor_type == "camarero":
        membership = (
            db.query(Membresia)
            .filter_by(
                establecimiento_id=establishment.id,
                camarero_id=actor_id,
                estado=MembresiaEstado.activa,
            )
            .one_or_none()
        )
        if membership is not None:
            return establishment
    raise ApiError(
        status_code=status.HTTP_403_FORBIDDEN,
        code=MEMBERSHIP_FORBIDDEN,
        detail="No tienes acceso al catálogo de este establecimiento",
    )


@router.get(
    "/{establecimiento_id}/catalogo",
    response_model=CatalogoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def obtener_catalogo(
    establecimiento_id: uuid.UUID,
    actor=Depends(get_current_actor),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establishment = _readable_establishment(db, establecimiento_id, actor)
    products = (
        db.query(ProductoCatalogo)
        .filter_by(establecimiento_id=establishment.id, archived_at=None)
        .order_by(ProductoCatalogo.categoria, ProductoCatalogo.nombre, ProductoCatalogo.id)
        .all()
    )
    return {
        "establecimiento_id": establishment.id,
        "revision": establishment.sync_revision,
        "server_time": datetime.now(UTC),
        "productos": products,
    }


@router.get(
    "/{establecimiento_id}/sync/cambios",
    response_model=CambiosSyncResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def obtener_cambios(
    establecimiento_id: uuid.UUID,
    desde: int = Query(default=0, ge=0),
    actor=Depends(get_current_actor),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establishment = _readable_establishment(db, establecimiento_id, actor)
    operations = (
        db.query(OperacionSync)
        .filter(
            OperacionSync.establecimiento_id == establishment.id,
            OperacionSync.estado == SyncEstado.aplicada,
            OperacionSync.global_revision > desde,
        )
        .order_by(OperacionSync.global_revision)
        .all()
    )
    return {
        "establecimiento_id": establishment.id,
        "desde": desde,
        "revision_actual": establishment.sync_revision,
        "cambios": [
            {
                "revision": operation.global_revision,
                "operation_id": operation.id,
                "aggregate_type": operation.aggregate_type,
                "aggregate_id": operation.aggregate_id,
                "action": operation.action.value,
                "snapshot": operation.result_snapshot,
            }
            for operation in operations
        ],
    }


@router.post(
    "/{establecimiento_id}/sync/operaciones",
    response_model=OperacionSyncResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def entregar_operacion(
    establecimiento_id: uuid.UUID,
    payload: OperacionSyncRequest,
    account: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    _owner_establishment(db, establecimiento_id, account)
    return process_operation(db, establecimiento_id, account, payload)


@router.get(
    "/{establecimiento_id}/sync/conflictos",
    response_model=list[ConflictoSyncResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_conflictos(
    establecimiento_id: uuid.UUID,
    estado: str = Query(default="pendiente", pattern="^(pendiente|aceptado|rechazado|todos)$"),
    account: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[dict]:
    _owner_establishment(db, establecimiento_id, account)
    query = db.query(ConflictoSync).filter_by(establecimiento_id=establecimiento_id)
    if estado != "todos":
        query = query.filter(ConflictoSync.estado == ConflictoEstado(estado))
    conflicts = query.order_by(ConflictoSync.created_at.desc()).all()
    return [
        conflict_response(conflict, db.get(OperacionSync, conflict.operacion_id))
        for conflict in conflicts
    ]


@router.post(
    "/{establecimiento_id}/sync/conflictos/{conflicto_id}/resolver",
    response_model=ConflictoSyncResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def resolver_conflicto(
    establecimiento_id: uuid.UUID,
    conflicto_id: uuid.UUID,
    payload: ResolverConflictoRequest,
    account: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    _owner_establishment(db, establecimiento_id, account)
    return resolve_conflict(
        db,
        establecimiento_id,
        conflicto_id,
        account,
        payload.decision,
        payload.expected_revision,
    )


@router.get(
    "/{establecimiento_id}/notificaciones",
    response_model=list[NotificacionNegocioResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_notificaciones(
    establecimiento_id: uuid.UUID,
    solo_no_leidas: bool = False,
    account: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[NotificacionNegocio]:
    _owner_establishment(db, establecimiento_id, account)
    query = db.query(NotificacionNegocio).filter_by(establecimiento_id=establecimiento_id)
    if solo_no_leidas:
        query = query.filter(NotificacionNegocio.read_at.is_(None))
    return query.order_by(NotificacionNegocio.created_at.desc()).all()


@router.post(
    "/{establecimiento_id}/notificaciones/{notificacion_id}/leer",
    response_model=NotificacionNegocioResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def marcar_notificacion_leida(
    establecimiento_id: uuid.UUID,
    notificacion_id: uuid.UUID,
    account: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> NotificacionNegocio:
    _owner_establishment(db, establecimiento_id, account)
    notification = (
        db.query(NotificacionNegocio)
        .filter_by(id=notificacion_id, establecimiento_id=establecimiento_id)
        .one_or_none()
    )
    if notification is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=NOTIFICACION_NOT_FOUND,
            detail="Notificación no encontrada",
        )
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return notification
