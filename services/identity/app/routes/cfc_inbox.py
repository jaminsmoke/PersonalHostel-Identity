"""Jornada de local, bandeja de pedidos CFC y superficie pública de carta/cuenta."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.cfc import (
    NO_STORE,
    PEDIDO_ACEPTADO,
    PEDIDO_EXPIRADO,
    PEDIDO_PENDIENTE,
    PEDIDO_RECHAZADO,
    admision_cfc,
    heartbeat_fresco,
    jornada_abierta,
    mesa_activa_por_token,
    siguiente_seq,
)
from app.db import get_negocio_db
from app.errors import (
    CFC_CERRADO,
    CFC_JORNADA_NO_ABIERTA,
    CFC_PEDIDO_NO_ENCONTRADO,
    ESTABLECIMIENTO_NOT_FOUND,
    MEMBERSHIP_FORBIDDEN,
    PRODUCTO_NOT_FOUND,
    ApiError,
)
from app.models import (
    CuentaNegocio,
    Establecimiento,
    JornadaCfc,
    PedidoCfc,
    ProductoCatalogo,
)
from app.rate_limit import OPENAPI_RATE_LIMIT, enforce_cfc_mesa
from app.schemas import (
    CartaCfcResponse,
    CuentaCfcResponse,
    ErrorResponse,
    JornadaCfcResponse,
    PedidoCfcAckRequest,
    PedidoCfcCreateRequest,
    PedidoCfcLinea,
    PedidoCfcResponse,
    PedidosCfcListaResponse,
    ProductoCartaCfc,
)

router = APIRouter(prefix="/v1/establecimientos", tags=["cfc-inbox"])
public_router = APIRouter(prefix="/v1/cfc", tags=["cfc-publico"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}


def _establecimiento_de_cuenta(
    establecimiento_id: uuid.UUID, cuenta: CuentaNegocio, db: Session
) -> Establecimiento:
    establecimiento = db.get(Establecimiento, establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    if establecimiento.cuenta_negocio_id != cuenta.id:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=MEMBERSHIP_FORBIDDEN,
            detail="La cuenta no tiene acceso a este establecimiento",
        )
    return establecimiento


def _jornada_response(jornada: JornadaCfc) -> JornadaCfcResponse:
    return JornadaCfcResponse(
        id=jornada.id,
        establecimiento_id=jornada.establecimiento_id,
        abierta_en=jornada.abierta_en,
        ultimo_heartbeat=jornada.ultimo_heartbeat,
        cerrada_en=jornada.cerrada_en,
        bar_en_linea=jornada.cerrada_en is None and heartbeat_fresco(jornada),
    )


def _pedido_response(pedido: PedidoCfc) -> PedidoCfcResponse:
    return PedidoCfcResponse(
        id=pedido.id,
        mesa_uuid=pedido.mesa_uuid,
        etiqueta=pedido.etiqueta_snapshot,
        estado=pedido.estado,
        seq=pedido.seq,
        lineas=[PedidoCfcLinea.model_validate(linea) for linea in pedido.lineas],
        total_centimos=pedido.total_centimos,
        creado_en=pedido.creado_en,
    )


def _cerrar_jornada(db: Session, jornada: JornadaCfc, ahora: datetime) -> None:
    jornada.cerrada_en = ahora
    (
        db.query(PedidoCfc)
        .filter_by(jornada_id=jornada.id, estado=PEDIDO_PENDIENTE)
        .update({PedidoCfc.estado: PEDIDO_EXPIRADO, PedidoCfc.actualizado_en: ahora})
    )


@router.post(
    "/{establecimiento_id}/cfc/jornada/abrir",
    response_model=JornadaCfcResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def abrir_jornada_cfc(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> JornadaCfcResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    existente = jornada_abierta(db, establecimiento.id)
    if existente is not None:
        existente.ultimo_heartbeat = datetime.now(UTC)
        db.commit()
        db.refresh(existente)
        return _jornada_response(existente)
    ahora = datetime.now(UTC)
    jornada = JornadaCfc(
        establecimiento_id=establecimiento.id,
        abierta_en=ahora,
        ultimo_heartbeat=ahora,
    )
    db.add(jornada)
    db.commit()
    db.refresh(jornada)
    return _jornada_response(jornada)


@router.post(
    "/{establecimiento_id}/cfc/jornada/cerrar",
    response_model=JornadaCfcResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def cerrar_jornada_cfc(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> JornadaCfcResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    jornada = jornada_abierta(db, establecimiento.id)
    if jornada is None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CFC_JORNADA_NO_ABIERTA,
            detail="No hay una jornada CFC abierta",
        )
    _cerrar_jornada(db, jornada, datetime.now(UTC))
    db.commit()
    db.refresh(jornada)
    return _jornada_response(jornada)


@router.put(
    "/{establecimiento_id}/cfc/heartbeat",
    response_model=JornadaCfcResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def heartbeat_jornada_cfc(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> JornadaCfcResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    jornada = jornada_abierta(db, establecimiento.id)
    if jornada is None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CFC_JORNADA_NO_ABIERTA,
            detail="No hay una jornada CFC abierta",
        )
    jornada.ultimo_heartbeat = datetime.now(UTC)
    db.commit()
    db.refresh(jornada)
    return _jornada_response(jornada)


@router.get(
    "/{establecimiento_id}/cfc/pedidos",
    response_model=PedidosCfcListaResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_pedidos_cfc(
    establecimiento_id: uuid.UUID,
    cursor: int = Query(default=0, ge=0),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> PedidosCfcListaResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    filas = (
        db.query(PedidoCfc)
        .filter(
            PedidoCfc.establecimiento_id == establecimiento.id,
            PedidoCfc.estado == PEDIDO_PENDIENTE,
            PedidoCfc.seq > cursor,
        )
        .order_by(PedidoCfc.seq)
        .all()
    )
    ultimo = filas[-1].seq if filas else cursor
    return PedidosCfcListaResponse(
        pedidos=[_pedido_response(p) for p in filas],
        cursor=ultimo,
    )


@router.post(
    "/{establecimiento_id}/cfc/pedidos/{pedido_id}/ack",
    response_model=PedidoCfcResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def ack_pedido_cfc(
    establecimiento_id: uuid.UUID,
    pedido_id: uuid.UUID,
    payload: PedidoCfcAckRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> PedidoCfcResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    pedido = (
        db.query(PedidoCfc)
        .filter_by(id=pedido_id, establecimiento_id=establecimiento.id)
        .one_or_none()
    )
    if pedido is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=CFC_PEDIDO_NO_ENCONTRADO,
            detail="Pedido CFC no encontrado",
        )
    if pedido.estado != PEDIDO_PENDIENTE:
        return _pedido_response(pedido)
    pedido.estado = PEDIDO_ACEPTADO if payload.decision == "aceptado" else PEDIDO_RECHAZADO
    pedido.actualizado_en = datetime.now(UTC)
    db.commit()
    db.refresh(pedido)
    return _pedido_response(pedido)


def _carta_productos(db: Session, establecimiento_id: uuid.UUID) -> list[ProductoCartaCfc]:
    productos = (
        db.query(ProductoCatalogo)
        .filter_by(
            establecimiento_id=establecimiento_id,
            archived_at=None,
            disponible=True,
        )
        .order_by(ProductoCatalogo.categoria, ProductoCatalogo.nombre)
        .all()
    )
    return [
        ProductoCartaCfc(
            id=p.id,
            nombre=p.nombre,
            precio_centimos=p.precio_centimos,
            categoria=p.categoria,
            destino=p.destino.value,
        )
        for p in productos
    ]


@public_router.get(
    "/mesa/{token}/carta",
    response_model=CartaCfcResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def carta_mesa_cfc(
    token: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> CartaCfcResponse:
    response.headers["Cache-Control"] = "no-store"
    mesa = mesa_activa_por_token(db, token)
    establecimiento = db.get(Establecimiento, mesa.establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
            headers=NO_STORE,
        )
    admite, en_linea = admision_cfc(db, establecimiento)
    return CartaCfcResponse(
        establecimiento_id=establecimiento.id,
        nombre=establecimiento.nombre,
        admite_pedidos=admite,
        bar_en_linea=en_linea,
        productos=_carta_productos(db, establecimiento.id),
    )


@public_router.get(
    "/mesa/{token}/cuenta",
    response_model=CuentaCfcResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def cuenta_mesa_cfc(
    token: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> CuentaCfcResponse:
    response.headers["Cache-Control"] = "no-store"
    mesa = mesa_activa_por_token(db, token)
    establecimiento = db.get(Establecimiento, mesa.establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
            headers=NO_STORE,
        )
    admite, en_linea = admision_cfc(db, establecimiento)
    jornada = jornada_abierta(db, establecimiento.id)
    lineas: list[PedidoCfcLinea] = []
    if jornada is not None:
        pedidos = (
            db.query(PedidoCfc)
            .filter(
                PedidoCfc.jornada_id == jornada.id,
                PedidoCfc.mesa_uuid == mesa.mesa_uuid,
                PedidoCfc.estado.in_((PEDIDO_PENDIENTE, PEDIDO_ACEPTADO)),
            )
            .order_by(PedidoCfc.seq)
            .all()
        )
        for pedido in pedidos:
            lineas.extend(PedidoCfcLinea.model_validate(item) for item in pedido.lineas)
    return CuentaCfcResponse(
        mesa_uuid=mesa.mesa_uuid,
        etiqueta=mesa.etiqueta,
        admite_pedidos=admite,
        bar_en_linea=en_linea,
        lineas=lineas,
        total_centimos=sum(linea.precio_centimos * linea.cantidad for linea in lineas),
    )


@public_router.post(
    "/mesa/{token}/pedidos",
    response_model=PedidoCfcResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        **OPENAPI_RATE_LIMIT,
    },
)
def crear_pedido_cfc(
    token: str,
    payload: PedidoCfcCreateRequest,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> PedidoCfcResponse:
    response.headers["Cache-Control"] = "no-store"
    mesa = mesa_activa_por_token(db, token)
    establecimiento = db.get(Establecimiento, mesa.establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
            headers=NO_STORE,
        )
    admite, _en_linea = admision_cfc(db, establecimiento)
    if not admite:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CFC_CERRADO,
            detail="El local no admite pedidos ahora",
            headers=NO_STORE,
        )
    jornada = jornada_abierta(db, establecimiento.id)
    if jornada is None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CFC_CERRADO,
            detail="El local no admite pedidos ahora",
            headers=NO_STORE,
        )
    previo = (
        db.query(PedidoCfc)
        .filter_by(
            establecimiento_id=establecimiento.id,
            idempotency_key=payload.idempotency_key,
        )
        .one_or_none()
    )
    if previo is not None:
        return _pedido_response(previo)

    enforce_cfc_mesa(token)

    snapshot: list[dict] = []
    total = 0
    for linea in payload.lineas:
        producto = (
            db.query(ProductoCatalogo)
            .filter_by(
                id=linea.producto_id,
                establecimiento_id=establecimiento.id,
                archived_at=None,
                disponible=True,
            )
            .one_or_none()
        )
        if producto is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code=PRODUCTO_NOT_FOUND,
                detail="Un producto del pedido no está disponible",
                headers=NO_STORE,
            )
        snapshot.append(
            {
                "producto_id": str(producto.id),
                "nombre": producto.nombre,
                "cantidad": linea.cantidad,
                "precio_centimos": producto.precio_centimos,
                "destino": producto.destino.value,
            }
        )
        total += producto.precio_centimos * linea.cantidad

    pedido = PedidoCfc(
        establecimiento_id=establecimiento.id,
        jornada_id=jornada.id,
        mesa_uuid=mesa.mesa_uuid,
        etiqueta_snapshot=mesa.etiqueta,
        idempotency_key=payload.idempotency_key,
        seq=siguiente_seq(db, establecimiento.id),
        estado=PEDIDO_PENDIENTE,
        lineas=snapshot,
        total_centimos=total,
    )
    db.add(pedido)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        repetido = (
            db.query(PedidoCfc)
            .filter_by(
                establecimiento_id=establecimiento.id,
                idempotency_key=payload.idempotency_key,
            )
            .one()
        )
        return _pedido_response(repetido)
    db.refresh(pedido)
    return _pedido_response(pedido)
