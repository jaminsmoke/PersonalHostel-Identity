"""Web pública del negocio por enlace (ficha + carta en una sola página).

Sin token: el ``slug`` de un enlace público (``ficha_negocio`` o ``carta``) es la
llave. Devuelve los datos de la ficha y de la carta agrupados, para que la web
``web.negocio.siberia.solutions/negocios/{slug}`` renderice toda la superficie con
una sola llamada. No expone campos internos ni PII del negocio.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_negocio_db
from app.errors import ENLACE_NOT_FOUND, ENLACE_REVOCADO, ApiError
from app.models import (
    CuentaNegocio,
    EnlaceEstado,
    EnlacePublico,
    EnlaceTipo,
    Establecimiento,
    ProductoCatalogo,
)
from app.routes.horario import filas_horario_establecimiento
from app.routes.negocio_ficha import servir_logo_efectivo
from app.schemas import ErrorResponse, HorarioDia, WebNegocioPublica

router = APIRouter(prefix="/v1/negocio", tags=["negocio público"])

_TIPOS_WEB = (EnlaceTipo.ficha_negocio.value, EnlaceTipo.carta.value)


def _establecimiento_por_slug(db: Session, slug: str) -> Establecimiento:
    enlace = (
        db.query(EnlacePublico)
        .filter(EnlacePublico.slug == slug, EnlacePublico.tipo.in_(_TIPOS_WEB))
        .one_or_none()
    )
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
    establecimiento = db.get(Establecimiento, enlace.establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    if db.get(CuentaNegocio, establecimiento.cuenta_negocio_id) is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Negocio no encontrado",
        )
    return establecimiento


def _logo_url(slug: str, establecimiento: Establecimiento) -> str | None:
    if not establecimiento.logo_efectivo_clave:
        return None
    return f"/v1/negocio/web/logo?slug={slug}"


def _horario_publico(db: Session, establecimiento: Establecimiento) -> list[HorarioDia] | None:
    """Horario del establecimiento para la web pública, o None si no hay."""
    filas = filas_horario_establecimiento(db, establecimiento.id)
    if not filas:
        return None
    return [
        HorarioDia(
            dia_semana=fila.dia_semana,
            cerrado=fila.cerrado,
            turnos=fila.turnos or [],
        )
        for fila in filas
    ]


def _categorias(db: Session, establecimiento: Establecimiento) -> list[dict]:
    productos = (
        db.query(ProductoCatalogo)
        .filter(
            ProductoCatalogo.establecimiento_id == establecimiento.id,
            ProductoCatalogo.archived_at.is_(None),
            ProductoCatalogo.disponible.is_(True),
        )
        .order_by(ProductoCatalogo.categoria, ProductoCatalogo.nombre)
        .all()
    )
    categorias: dict[str, list[dict]] = {}
    for producto in productos:
        categorias.setdefault(producto.categoria, []).append(
            {
                "nombre": producto.nombre,
                "precio_centimos": producto.precio_centimos,
                "moneda": producto.moneda,
            }
        )
    return [{"nombre": nombre, "productos": items} for nombre, items in categorias.items()]


@router.get(
    "/web",
    response_model=WebNegocioPublica,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def web_negocio(
    slug: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_por_slug(db, slug)
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "establecimiento_id": establecimiento.id,
        "nombre": establecimiento.nombre,
        "tipo_establecimiento": establecimiento.tipo_efectivo,
        "logo_url": _logo_url(slug, establecimiento),
        "organizacion_nombre": establecimiento.cuenta_negocio.nombre_mostrar,
        "categorias": _categorias(db, establecimiento),
        "horario": _horario_publico(db, establecimiento),
    }


@router.get(
    "/web/logo",
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def web_negocio_logo(
    slug: str,
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_por_slug(db, slug)
    return servir_logo_efectivo(establecimiento)
