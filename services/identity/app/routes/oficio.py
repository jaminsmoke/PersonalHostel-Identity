"""Jornadas y resumen de oficio del camarero (libro de oficio canónico).

Los intervalos de jornada (``jornadas``) y los eventos de servicio
(``servicios``) viven en la BD de profesionales. El camarero autenticado
abre/cierra su jornada y consulta el resumen agregado (horas + mesas servidas).
Los eventos ``servicios`` los produce Bar a través del servicio de negocio y el
transporte interno.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth import get_current_camarero
from app.db import get_camarero_db
from app.errors import (
    JORNADA_NO_ABIERTA,
    JORNADA_YA_ABIERTA,
    MEMBERSHIP_FORBIDDEN,
    VALIDATION_ERROR,
    ApiError,
)
from app.internal import get_negocio_internal
from app.models import Camarero, Jornada, Servicio
from app.schemas import (
    ErrorResponse,
    JornadaIniciarRequest,
    JornadaResponse,
    ResumenOficioResponse,
    ResumenPorEstablecimiento,
)

router = APIRouter(prefix="/v1/camareros", tags=["camareros"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}


def _jornada_abierta(db: Session, camarero_id: uuid.UUID) -> Jornada | None:
    return (
        db.query(Jornada)
        .filter_by(camarero_id=camarero_id, fin=None)
        .order_by(Jornada.inicio.desc())
        .first()
    )


def _exige_membresia(camarero: Camarero, establecimiento_id: uuid.UUID) -> None:
    establecimientos = get_negocio_internal().establecimientos_de(camarero.id)
    if str(establecimiento_id) not in {e["id"] for e in establecimientos}:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=MEMBERSHIP_FORBIDDEN,
            detail="El camarero no tiene membresía activa en ese establecimiento",
        )


def _jornada_response(jornada: Jornada) -> JornadaResponse:
    return JornadaResponse(
        id=jornada.id,
        camarero_id=jornada.camarero_id,
        establecimiento_id=jornada.establecimiento_id,
        inicio=jornada.inicio,
        fin=jornada.fin,
    )


@router.post(
    "/me/jornadas/iniciar",
    response_model=JornadaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def iniciar_jornada(
    payload: JornadaIniciarRequest,
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> JornadaResponse:
    _exige_membresia(camarero, payload.establecimiento_id)
    if _jornada_abierta(db, camarero.id) is not None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=JORNADA_YA_ABIERTA,
            detail="Ya hay una jornada abierta",
        )
    jornada = Jornada(
        camarero_id=camarero.id,
        establecimiento_id=payload.establecimiento_id,
        inicio=datetime.now(UTC),
        data_origin=camarero.data_origin,
    )
    db.add(jornada)
    db.commit()
    db.refresh(jornada)
    return _jornada_response(jornada)


@router.post(
    "/me/jornadas/cortar",
    response_model=JornadaResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def cortar_jornada(
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> JornadaResponse:
    jornada = _jornada_abierta(db, camarero.id)
    if jornada is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=JORNADA_NO_ABIERTA,
            detail="No hay una jornada abierta",
        )
    jornada.fin = datetime.now(UTC)
    db.commit()
    db.refresh(jornada)
    return _jornada_response(jornada)


@router.get(
    "/me/jornadas",
    response_model=list[JornadaResponse],
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def listar_jornadas(
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> list[JornadaResponse]:
    query = db.query(Jornada).filter(Jornada.camarero_id == camarero.id)
    if desde is not None:
        query = query.filter(Jornada.inicio >= desde)
    if hasta is not None:
        query = query.filter(Jornada.inicio <= hasta)
    return [_jornada_response(j) for j in query.order_by(Jornada.inicio.desc()).all()]


def _resumen(
    db: Session, camarero_id: uuid.UUID, desde: datetime, hasta: datetime
) -> ResumenOficioResponse:
    jornadas = (
        db.query(Jornada)
        .filter(
            Jornada.camarero_id == camarero_id,
            Jornada.inicio < hasta,
            or_(Jornada.fin.is_(None), Jornada.fin > desde),
        )
        .all()
    )
    horas_por_est: dict[uuid.UUID, float] = {}
    for jornada in jornadas:
        inicio = max(jornada.inicio, desde)
        fin = min(jornada.fin or hasta, hasta)
        segundos = max(0.0, (fin - inicio).total_seconds())
        horas_por_est[jornada.establecimiento_id] = (
            horas_por_est.get(jornada.establecimiento_id, 0.0) + segundos
        )

    filas_mesas = (
        db.query(Servicio.establecimiento_id, func.sum(Servicio.cantidad))
        .filter(
            Servicio.camarero_id == camarero_id,
            Servicio.created_at >= desde,
            Servicio.created_at <= hasta,
        )
        .group_by(Servicio.establecimiento_id)
        .all()
    )
    mesas_por_est: dict[uuid.UUID, int] = {
        est_id: int(total or 0) for est_id, total in filas_mesas
    }

    establecimiento_ids = set(horas_por_est) | set(mesas_por_est)
    por_establecimiento = [
        ResumenPorEstablecimiento(
            establecimiento_id=est_id,
            horas_segundos=int(round(horas_por_est.get(est_id, 0.0))),
            mesas_servidas=mesas_por_est.get(est_id, 0),
        )
        for est_id in sorted(establecimiento_ids, key=str)
    ]

    return ResumenOficioResponse(
        desde=desde,
        hasta=hasta,
        horas_segundos=sum(p.horas_segundos for p in por_establecimiento),
        mesas_servidas=sum(p.mesas_servidas for p in por_establecimiento),
        por_establecimiento=por_establecimiento,
    )


@router.get(
    "/me/resumen",
    response_model=ResumenOficioResponse,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def resumen_oficio(
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> ResumenOficioResponse:
    now = datetime.now(UTC)
    hasta = hasta or now
    desde = desde or (now - timedelta(days=30))
    if hasta <= desde:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=VALIDATION_ERROR,
            detail="hasta debe ser posterior a desde",
        )
    return _resumen(db, camarero.id, desde, hasta)
