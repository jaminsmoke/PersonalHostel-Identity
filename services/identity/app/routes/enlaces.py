"""Enlaces públicos revocables (ficha de negocio, carta, futuros compartibles).

Un enlace es un "compartible público" por diseño: no lleva firma ni identidad
que verificar, solo un ``slug`` opaco que resuelve a ``(tipo, establecimiento)``
y un toggle activo/revocado. La cache pública es de TTL corto para que la
revocación sea efectiva en minutos.
"""

import os
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.db import get_negocio_db
from app.errors import (
    ENLACE_ACTIVO_EXISTENTE,
    ENLACE_DUPLICATE,
    ENLACE_NOT_FOUND,
    ENLACE_REVOCADO,
    ESTABLECIMIENTO_NOT_FOUND,
    MEMBERSHIP_FORBIDDEN,
    ApiError,
)
from app.models import CuentaNegocio, EnlaceEstado, EnlacePublico, Establecimiento
from app.schemas import (
    EnlacePublicoCreateRequest,
    EnlacePublicoRotarRequest,
    EnlacePublicoResolucion,
    EnlacePublicoResponse,
    ErrorResponse,
)

router = APIRouter(prefix="/v1/establecimientos", tags=["enlaces públicos"])
public_router = APIRouter(prefix="/v1/enlaces", tags=["enlaces públicos"])

_TIPO_SLUG_SUFIJO = {"ficha_negocio": "ficha", "carta": "carta"}
_TIPO_URL_ENV = {
    "ficha_negocio": "FICHA_NEGOCIO_URL_BASE",
    "carta": "CARTA_URL_BASE",
}

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}


def _slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "establecimiento"


def _url_publica(tipo: str, slug: str) -> str | None:
    base = os.environ.get(_TIPO_URL_ENV[tipo])
    if not base:
        return None
    return f"{base.rstrip('/')}?slug={quote(slug)}"


def _respuesta(enlace: EnlacePublico) -> EnlacePublicoResponse:
    return EnlacePublicoResponse(
        id=enlace.id,
        establecimiento_id=enlace.establecimiento_id,
        tipo=enlace.tipo,
        slug=enlace.slug,
        estado=enlace.estado,
        expira_en=enlace.expira_en,
        url_publica=_url_publica(enlace.tipo, enlace.slug),
    )


def _slug_disponible(db: Session, base: str) -> str:
    if db.query(EnlacePublico).filter_by(slug=base).one_or_none() is None:
        return base
    for _ in range(10):
        candidate = f"{base[:91]}-{uuid.uuid4().hex[:8]}"
        if db.query(EnlacePublico).filter_by(slug=candidate).one_or_none() is None:
            return candidate
    raise ApiError(
        status_code=status.HTTP_409_CONFLICT,
        code=ENLACE_DUPLICATE,
        detail="No se pudo generar un slug disponible",
    )


def _activo_del_tipo(
    db: Session, establecimiento_id: uuid.UUID, tipo: str
) -> EnlacePublico | None:
    enlace = (
        db.query(EnlacePublico)
        .filter_by(
            establecimiento_id=establecimiento_id,
            tipo=tipo,
            estado=EnlaceEstado.activo.value,
        )
        .one_or_none()
    )
    if enlace is not None and enlace.expira_en is not None and enlace.expira_en <= datetime.now(UTC):
        enlace.estado = EnlaceEstado.revocado.value
        enlace.revocada_en = datetime.now(UTC)
        db.flush()
        return None
    return enlace


def _guardar_enlace(db: Session, enlace: EnlacePublico) -> EnlacePublico:
    db.add(enlace)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=ENLACE_ACTIVO_EXISTENTE,
            detail="Ya existe un enlace activo de ese tipo",
        ) from exc
    db.refresh(enlace)
    return enlace


def _owner_establishment(
    db: Session, establecimiento_id: uuid.UUID, cuenta: CuentaNegocio
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


def _enlace_activo(db: Session, slug: str) -> EnlacePublico:
    enlace = db.query(EnlacePublico).filter_by(slug=slug).one_or_none()
    if enlace is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Enlace no encontrado",
        )
    now = datetime.now(UTC)
    if enlace.estado != EnlaceEstado.activo.value or (
        enlace.expira_en is not None and enlace.expira_en <= now
    ):
        raise ApiError(
            status_code=status.HTTP_410_GONE,
            code=ENLACE_REVOCADO,
            detail="Enlace no disponible",
        )
    return enlace


@router.post(
    "/{establecimiento_id}/enlaces",
    response_model=EnlacePublicoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def crear_enlace(
    establecimiento_id: uuid.UUID,
    payload: EnlacePublicoCreateRequest,
    response: Response,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> EnlacePublicoResponse:
    establecimiento = _owner_establishment(db, establecimiento_id, cuenta)
    activo = _activo_del_tipo(db, establecimiento.id, payload.tipo)
    if activo is not None:
        if payload.slug is None or payload.slug.strip() == activo.slug:
            response.status_code = status.HTTP_200_OK
            return _respuesta(activo)
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=ENLACE_ACTIVO_EXISTENTE,
            detail="Ya existe un enlace activo de ese tipo; rótalo para sustituirlo",
        )
    if payload.slug:
        slug = payload.slug.strip()
        if db.query(EnlacePublico).filter_by(slug=slug).one_or_none() is not None:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=ENLACE_DUPLICATE,
                detail="Ya existe un enlace con ese slug",
            )
    else:
        slug = _slug_disponible(
            db,
            f"{_slugify(establecimiento.nombre)}-{_TIPO_SLUG_SUFIJO[payload.tipo]}",
        )
    enlace = EnlacePublico(
        establecimiento_id=establecimiento.id,
        tipo=payload.tipo,
        slug=slug,
        estado=EnlaceEstado.activo.value,
    )
    return _respuesta(_guardar_enlace(db, enlace))


@router.get(
    "/{establecimiento_id}/enlaces",
    response_model=list[EnlacePublicoResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_enlaces(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[EnlacePublicoResponse]:
    establecimiento = _owner_establishment(db, establecimiento_id, cuenta)
    enlaces = (
        db.query(EnlacePublico)
        .filter_by(establecimiento_id=establecimiento.id)
        .order_by(EnlacePublico.creada_en)
        .all()
    )
    return [_respuesta(enlace) for enlace in enlaces]


@router.post(
    "/{establecimiento_id}/enlaces/{enlace_id}/revocar",
    response_model=EnlacePublicoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def revocar_enlace(
    establecimiento_id: uuid.UUID,
    enlace_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> EnlacePublicoResponse:
    establecimiento = _owner_establishment(db, establecimiento_id, cuenta)
    enlace = (
        db.query(EnlacePublico)
        .filter_by(id=enlace_id, establecimiento_id=establecimiento.id)
        .one_or_none()
    )
    if enlace is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Enlace no encontrado",
        )
    if enlace.estado == EnlaceEstado.activo.value:
        enlace.estado = EnlaceEstado.revocado.value
        enlace.revocada_en = datetime.now(UTC)
        db.commit()
        db.refresh(enlace)
    return _respuesta(enlace)


@router.post(
    "/{establecimiento_id}/enlaces/{enlace_id}/rotar",
    response_model=EnlacePublicoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def rotar_enlace(
    establecimiento_id: uuid.UUID,
    enlace_id: uuid.UUID,
    payload: EnlacePublicoRotarRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> EnlacePublicoResponse:
    establecimiento = _owner_establishment(db, establecimiento_id, cuenta)
    anterior = (
        db.query(EnlacePublico)
        .filter_by(id=enlace_id, establecimiento_id=establecimiento.id)
        .one_or_none()
    )
    if anterior is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Enlace no encontrado",
        )
    activo = _activo_del_tipo(db, establecimiento.id, anterior.tipo)
    if activo is not None and activo.id != anterior.id:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=ENLACE_ACTIVO_EXISTENTE,
            detail="Otro enlace de ese tipo ya está activo",
        )
    if payload.slug:
        slug = payload.slug.strip()
        if db.query(EnlacePublico).filter_by(slug=slug).one_or_none() is not None:
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=ENLACE_DUPLICATE,
                detail="Ya existe un enlace con ese slug",
            )
    else:
        slug = _slug_disponible(
            db,
            f"{_slugify(establecimiento.nombre)}-{_TIPO_SLUG_SUFIJO[anterior.tipo]}",
        )
    if anterior.estado == EnlaceEstado.activo.value:
        anterior.estado = EnlaceEstado.revocado.value
        anterior.revocada_en = datetime.now(UTC)
        db.flush()
    nuevo = EnlacePublico(
        establecimiento_id=establecimiento.id,
        tipo=anterior.tipo,
        slug=slug,
        estado=EnlaceEstado.activo.value,
    )
    return _respuesta(_guardar_enlace(db, nuevo))


@public_router.get(
    "/{slug}",
    response_model=EnlacePublicoResolucion,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def resolver_enlace(
    slug: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> dict:
    enlace = _enlace_activo(db, slug)
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"tipo": enlace.tipo, "establecimiento_id": enlace.establecimiento_id}
