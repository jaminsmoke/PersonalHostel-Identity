"""Registro canónico de mesas CFC: conjunto de UUIDs + tokens opacos.

Bar envía el conjunto; Identity emite, revoca y rota. El layout de sala sigue
siendo un documento JSONB opaco: este módulo no lo lee.
"""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.cfc import admision_cfc, hash_token, mesa_activa_por_token
from app.db import get_negocio_db
from app.errors import (
    ESTABLECIMIENTO_NOT_FOUND,
    MEMBERSHIP_FORBIDDEN,
    MESA_CFC_NO_ENCONTRADA,
    ApiError,
)
from app.models import CuentaNegocio, EnlaceEstado, Establecimiento, MesaCfc
from app.schemas import (
    ErrorResponse,
    MesaCfcPublicaResponse,
    MesaCfcResponse,
    MesasCfcSyncRequest,
)
from app.security import (
    get_session_secret_env,
    protect_invitation_token,
    unprotect_invitation_token,
)

router = APIRouter(prefix="/v1/establecimientos", tags=["mesas-cfc"])
public_router = APIRouter(prefix="/v1/cfc", tags=["cfc-publico"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}
WEB_CFC_URL_BASE_ENV = "WEB_CFC_URL_BASE"


def _hash_token(token: str) -> str:
    return hash_token(token)


def _url_publica(token: str) -> str | None:
    base = os.environ.get(WEB_CFC_URL_BASE_ENV)
    if not base:
        return None
    return f"{base.rstrip('/')}/m/{token}"


def _token_de_fila(mesa: MesaCfc) -> str:
    return unprotect_invitation_token(mesa.token_protegido, get_session_secret_env())


def _respuesta(mesa: MesaCfc) -> MesaCfcResponse:
    return MesaCfcResponse(
        mesa_uuid=mesa.mesa_uuid,
        etiqueta=mesa.etiqueta,
        estado=mesa.estado,
        url_publica=_url_publica(_token_de_fila(mesa)),
    )


def _emitir(establecimiento_id: uuid.UUID, mesa_uuid: uuid.UUID, etiqueta: str) -> MesaCfc:
    token = secrets.token_urlsafe(32)
    return MesaCfc(
        establecimiento_id=establecimiento_id,
        mesa_uuid=mesa_uuid,
        etiqueta=etiqueta,
        token_hash=_hash_token(token),
        token_protegido=protect_invitation_token(token, get_session_secret_env()),
        estado=EnlaceEstado.activo.value,
    )


def _revocar(mesa: MesaCfc, ahora: datetime) -> None:
    mesa.estado = EnlaceEstado.revocado.value
    mesa.revocada_en = ahora


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


def _activas(db: Session, establecimiento_id: uuid.UUID) -> list[MesaCfc]:
    return (
        db.query(MesaCfc)
        .filter_by(
            establecimiento_id=establecimiento_id,
            estado=EnlaceEstado.activo.value,
        )
        .all()
    )


@router.put(
    "/{establecimiento_id}/mesas-cfc",
    response_model=list[MesaCfcResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def sincronizar_mesas_cfc(
    establecimiento_id: uuid.UUID,
    payload: MesasCfcSyncRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[MesaCfcResponse]:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    ahora = datetime.now(UTC)
    deseadas = {item.mesa_uuid: item.etiqueta.strip() for item in payload.mesas}
    activas = {mesa.mesa_uuid: mesa for mesa in _activas(db, establecimiento.id)}

    for mesa_uuid, mesa in activas.items():
        if mesa_uuid not in deseadas:
            _revocar(mesa, ahora)

    db.flush()

    resultado: list[MesaCfc] = []
    for mesa_uuid, etiqueta in deseadas.items():
        existente = activas.get(mesa_uuid)
        if existente is not None:
            existente.etiqueta = etiqueta
            resultado.append(existente)
            continue
        nueva = _emitir(establecimiento.id, mesa_uuid, etiqueta)
        db.add(nueva)
        resultado.append(nueva)

    db.commit()
    for mesa in resultado:
        db.refresh(mesa)
    return [_respuesta(mesa) for mesa in resultado]


@router.get(
    "/{establecimiento_id}/mesas-cfc",
    response_model=list[MesaCfcResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_mesas_cfc(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[MesaCfcResponse]:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    activas = sorted(_activas(db, establecimiento.id), key=lambda m: (m.etiqueta, str(m.mesa_uuid)))
    return [_respuesta(mesa) for mesa in activas]


@router.post(
    "/{establecimiento_id}/mesas-cfc/{mesa_uuid}/rotar",
    response_model=MesaCfcResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def rotar_mesa_cfc(
    establecimiento_id: uuid.UUID,
    mesa_uuid: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> MesaCfcResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    activa = (
        db.query(MesaCfc)
        .filter_by(
            establecimiento_id=establecimiento.id,
            mesa_uuid=mesa_uuid,
            estado=EnlaceEstado.activo.value,
        )
        .one_or_none()
    )
    if activa is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=MESA_CFC_NO_ENCONTRADA,
            detail="No hay una mesa CFC activa con ese identificador",
        )
    ahora = datetime.now(UTC)
    etiqueta = activa.etiqueta
    _revocar(activa, ahora)
    db.flush()
    nueva = _emitir(establecimiento.id, mesa_uuid, etiqueta)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return _respuesta(nueva)


@public_router.get(
    "/mesa/{token}",
    response_model=MesaCfcPublicaResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def resolver_mesa_cfc(
    token: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> MesaCfcPublicaResponse:
    response.headers["Cache-Control"] = "no-store"
    mesa = mesa_activa_por_token(db, token)
    establecimiento = db.get(Establecimiento, mesa.establecimiento_id)
    nombre = establecimiento.nombre if establecimiento is not None else ""
    admite, en_linea = (False, False)
    if establecimiento is not None:
        admite, en_linea = admision_cfc(db, establecimiento)
    return MesaCfcPublicaResponse(
        establecimiento_id=mesa.establecimiento_id,
        establecimiento_nombre=nombre,
        mesa_uuid=mesa.mesa_uuid,
        etiqueta=mesa.etiqueta,
        admite_pedidos=admite,
        bar_en_linea=en_linea,
    )
