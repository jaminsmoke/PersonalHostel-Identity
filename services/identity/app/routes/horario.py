"""Horario semanal del establecimiento (fuente canónica para la web).

Gestión con JWT de negocio (dueño del establecimiento). La lectura pública vive
en ``negocio_web.py`` (``GET /v1/negocio/web``); este router expone la fuente
canónica y su validación. La sincronización con Bar se añadirá cuando el ítem de
Bar la pida (protocolo ``OperacionSync`` ya existente).
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.db import get_negocio_db
from app.models import CuentaNegocio, HorarioEstablecimiento
from app.routes.establecimientos import _establecimiento_de_cuenta
from app.schemas import ErrorResponse, HorarioDia, HorarioResponse, HorarioUpdateRequest

router = APIRouter(prefix="/v1/establecimientos", tags=["horario"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}
_FORBIDDEN = {"model": ErrorResponse}
_NOT_FOUND = {"model": ErrorResponse}


def filas_horario_establecimiento(
    db: Session, establecimiento_id: uuid.UUID
) -> list[HorarioEstablecimiento]:
    return (
        db.query(HorarioEstablecimiento)
        .filter(HorarioEstablecimiento.establecimiento_id == establecimiento_id)
        .order_by(HorarioEstablecimiento.dia_semana)
        .all()
    )


def _horario_response(db: Session, establecimiento_id: uuid.UUID) -> dict:
    filas = filas_horario_establecimiento(db, establecimiento_id)
    return {
        "establecimiento_id": establecimiento_id,
        "dias": [
            HorarioDia(
                dia_semana=fila.dia_semana,
                cerrado=fila.cerrado,
                turnos=fila.turnos or [],
            )
            for fila in filas
        ],
        "updated_at": max((fila.updated_at for fila in filas), default=None),
    }


@router.get(
    "/{establecimiento_id}/horario",
    response_model=HorarioResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def obtener_horario(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    return _horario_response(db, establecimiento.id)


@router.patch(
    "/{establecimiento_id}/horario",
    response_model=HorarioResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def actualizar_horario(
    establecimiento_id: uuid.UUID,
    payload: HorarioUpdateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    db.query(HorarioEstablecimiento).filter(
        HorarioEstablecimiento.establecimiento_id == establecimiento.id
    ).delete()
    for dia in payload.dias:
        db.add(
            HorarioEstablecimiento(
                establecimiento_id=establecimiento.id,
                dia_semana=dia.dia_semana,
                cerrado=dia.cerrado,
                turnos=[turno.model_dump(mode="json") for turno in dia.turnos],
            )
        )
    db.commit()
    db.expire_all()
    return _horario_response(db, establecimiento.id)
