from typing import cast
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_actor, get_current_cuenta_negocio
from app.db import get_db
from app.errors import (
    CAMARERO_NOT_FOUND,
    ESTABLECIMIENTO_NOT_FOUND,
    MEMBERSHIP_DUPLICATE,
    MEMBERSHIP_FORBIDDEN,
    ApiError,
)
from app.models import (
    Camarero,
    CuentaNegocio,
    Establecimiento,
    Membresia,
    MembresiaEstado,
    MembresiaRol,
)
from app.schemas import (
    ErrorResponse,
    EstablecimientoCreateRequest,
    EstablecimientoResponse,
    MembresiaCreateRequest,
    MembresiaResponse,
)

router = APIRouter(prefix="/v1/establecimientos", tags=["establecimientos"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}


def _establecimiento_de_cuenta(
    establecimiento_id, cuenta: CuentaNegocio, db: Session
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


@router.post(
    "",
    response_model=EstablecimientoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def crear_establecimiento(
    payload: EstablecimientoCreateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> Establecimiento:
    establecimiento = Establecimiento(
        nombre=payload.nombre.strip(), cuenta_negocio_id=cuenta.id
    )
    db.add(establecimiento)
    db.flush()
    if cuenta.camarero_vinculado_id is not None:
        db.add(
            Membresia(
                establecimiento_id=establecimiento.id,
                camarero_id=cuenta.camarero_vinculado_id,
                rol=MembresiaRol.dueno,
                estado=MembresiaEstado.activa,
            )
        )
    db.commit()
    db.refresh(establecimiento)
    return establecimiento


@router.get(
    "/mios",
    response_model=list[EstablecimientoResponse],
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def mis_establecimientos(
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> list[Establecimiento]:
    return (
        db.query(Establecimiento)
        .filter(Establecimiento.cuenta_negocio_id == cuenta.id)
        .order_by(Establecimiento.created_at)
        .all()
    )


@router.get(
    "/{establecimiento_id}",
    response_model=EstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def obtener_establecimiento(
    establecimiento_id: uuid.UUID,
    actor=Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> Establecimiento:
    tipo, identidad = actor
    establecimiento = db.get(Establecimiento, establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    if tipo == "negocio":
        if cast(CuentaNegocio, identidad).id != establecimiento.cuenta_negocio_id:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code=MEMBERSHIP_FORBIDDEN,
                detail="La cuenta no tiene acceso a este establecimiento",
            )
    else:
        membership = (
            db.query(Membresia)
            .filter_by(
                establecimiento_id=establecimiento.id,
                camarero_id=cast(Camarero, identidad).id,
                estado=MembresiaEstado.activa,
            )
            .one_or_none()
        )
        if membership is None:
            raise ApiError(
                status_code=status.HTTP_403_FORBIDDEN,
                code=MEMBERSHIP_FORBIDDEN,
                detail="El camarero no pertenece a este establecimiento",
            )
    return establecimiento


@router.post(
    "/{establecimiento_id}/miembros",
    response_model=MembresiaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def añadir_miembro(
    establecimiento_id: uuid.UUID,
    payload: MembresiaCreateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> Membresia:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    if db.get(Camarero, payload.camarero_id) is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=CAMARERO_NOT_FOUND,
            detail="Camarero no encontrado",
        )
    existing = (
        db.query(Membresia)
        .filter_by(
            establecimiento_id=establecimiento.id, camarero_id=payload.camarero_id
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.estado == MembresiaEstado.revocada:
            existing.estado = MembresiaEstado.activa
            existing.revocada_en = None
            existing.rol = MembresiaRol(payload.rol)
            db.commit()
            db.refresh(existing)
            return existing
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=MEMBERSHIP_DUPLICATE,
            detail="El camarero ya pertenece a este establecimiento",
        )
    membership = Membresia(
        establecimiento_id=establecimiento.id,
        camarero_id=payload.camarero_id,
        rol=MembresiaRol(payload.rol),
        estado=MembresiaEstado.activa,
    )
    db.add(membership)
    try:
        db.commit()
        db.refresh(membership)
    except IntegrityError:
        db.rollback()
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=MEMBERSHIP_DUPLICATE,
            detail="El camarero ya pertenece a este establecimiento",
        )
    return membership


@router.get(
    "/{establecimiento_id}/miembros",
    response_model=list[MembresiaResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_miembros(
    establecimiento_id: uuid.UUID,
    actor=Depends(get_current_actor),
    db: Session = Depends(get_db),
) -> list[Membresia]:
    establecimiento = db.get(Establecimiento, establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    tipo, identidad = actor
    autorizado = tipo == "negocio" and cast(CuentaNegocio, identidad).id == establecimiento.cuenta_negocio_id
    if tipo == "camarero" and not autorizado:
        autorizado = (
            db.query(Membresia)
            .filter_by(
                establecimiento_id=establecimiento.id,
                camarero_id=cast(Camarero, identidad).id,
                estado=MembresiaEstado.activa,
            )
            .count()
            > 0
        )
    if not autorizado:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=MEMBERSHIP_FORBIDDEN,
            detail="No tienes acceso a los miembros de este establecimiento",
        )
    return (
        db.query(Membresia)
        .filter_by(establecimiento_id=establecimiento.id, estado=MembresiaEstado.activa)
        .order_by(Membresia.creada_en)
        .all()
    )


@router.delete(
    "/{establecimiento_id}/miembros/{camarero_id}",
    response_model=MembresiaResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def revocar_miembro(
    establecimiento_id: uuid.UUID,
    camarero_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> Membresia:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    membership = (
        db.query(Membresia)
        .filter_by(establecimiento_id=establecimiento.id, camarero_id=camarero_id)
        .one_or_none()
    )
    if membership is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=CAMARERO_NOT_FOUND,
            detail="Membresía no encontrada",
        )
    membership.estado = MembresiaEstado.revocada
    from datetime import datetime, timezone

    membership.revocada_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(membership)
    return membership
