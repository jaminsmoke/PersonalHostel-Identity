"""Registro de eventos de servicio desde Bar (productor del libro de oficio).

Bar autentica con JWT de negocio y registra eventos agregados (p. ej. «mesa
servida») para un camarero con membresía activa. El evento se persiste en la BD
de profesionales vía el transporte interno (idempotente por ``evento_id``).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.db import get_negocio_db
from app.errors import MEMBERSHIP_FORBIDDEN, ApiError
from app.internal import get_camareros_internal
from app.models import CuentaNegocio, Membresia, MembresiaEstado
from app.routes.establecimientos import _establecimiento_de_cuenta
from app.schemas import (
    ErrorResponse,
    ServicioRegistroRequest,
    ServicioRegistroResponse,
)

router = APIRouter(prefix="/v1/negocio/estadisticas", tags=["estadisticas"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}


@router.post(
    "/servicio",
    response_model=ServicioRegistroResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def registrar_servicio(
    payload: ServicioRegistroRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> ServicioRegistroResponse:
    establecimiento = _establecimiento_de_cuenta(payload.establecimiento_id, cuenta, db)
    membership = (
        db.query(Membresia)
        .filter_by(
            establecimiento_id=establecimiento.id,
            camarero_id=payload.camarero_id,
            estado=MembresiaEstado.activa,
        )
        .one_or_none()
    )
    if membership is None:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=MEMBERSHIP_FORBIDDEN,
            detail="El camarero no tiene membresía activa en este establecimiento",
        )
    resultado = get_camareros_internal().registrar_servicio(
        camarero_id=payload.camarero_id,
        establecimiento_id=establecimiento.id,
        evento_id=payload.evento_id,
        tipo=payload.tipo,
        cantidad=payload.cantidad,
        data_origin=establecimiento.data_origin.value,
    )
    return ServicioRegistroResponse(**resultado)
