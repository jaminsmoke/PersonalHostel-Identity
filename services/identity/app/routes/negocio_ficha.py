"""Ficha pública del negocio por enlace.

Sin token: el ``slug`` del enlace ``ficha_negocio`` es la llave. Devuelve solo
campos públicos del negocio (nombre, tipo, logo y establecimientos); el email y
el contacto quedan privados. El logo es branding público y se sirve siempre que
exista.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_negocio_db
from app.errors import ENLACE_NOT_FOUND, ENLACE_REVOCADO, FOTO_INEXISTENTE, ApiError
from app.models import (
    CuentaNegocio,
    EnlaceEstado,
    EnlacePublico,
    EnlaceTipo,
    Establecimiento,
)
from app.schemas import ErrorResponse, NegocioFichaPublica
from app.storage import get_foto_storage

router = APIRouter(prefix="/v1/negocio", tags=["negocio público"])


def _cuenta_por_ficha_slug(db: Session, slug: str) -> CuentaNegocio:
    enlace = (
        db.query(EnlacePublico)
        .filter_by(slug=slug, tipo=EnlaceTipo.ficha_negocio.value)
        .one_or_none()
    )
    if enlace is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Enlace de ficha no encontrado",
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
    establecimiento = db.get(Establecimiento, enlace.establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    cuenta = db.get(CuentaNegocio, establecimiento.cuenta_negocio_id)
    if cuenta is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Negocio no encontrado",
        )
    return cuenta


def _logo_url(slug: str, cuenta: CuentaNegocio) -> str | None:
    if not cuenta.logo_clave:
        return None
    return f"/v1/negocio/ficha/logo?slug={slug}"


@router.get(
    "/ficha",
    response_model=NegocioFichaPublica,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def ficha_negocio(
    slug: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> dict:
    cuenta = _cuenta_por_ficha_slug(db, slug)
    establecimientos = (
        db.query(Establecimiento)
        .filter_by(cuenta_negocio_id=cuenta.id)
        .order_by(Establecimiento.created_at)
        .all()
    )
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "nombre": cuenta.nombre_mostrar,
        "tipo_establecimiento": cuenta.tipo_establecimiento,
        "logo_url": _logo_url(slug, cuenta),
        "establecimientos": [{"id": e.id, "nombre": e.nombre} for e in establecimientos],
    }


@router.get(
    "/ficha/logo",
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def ficha_negocio_logo(
    slug: str,
    db: Session = Depends(get_negocio_db),
) -> Response:
    cuenta = _cuenta_por_ficha_slug(db, slug)
    if not cuenta.logo_clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El negocio no tiene logo",
        )
    data = get_foto_storage().leer(cuenta.logo_clave)
    if data is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El logo no está disponible",
        )
    return Response(
        content=data,
        media_type=cuenta.logo_mimetype or "image/webp",
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": f'"{cuenta.logo_clave}"',
        },
    )
