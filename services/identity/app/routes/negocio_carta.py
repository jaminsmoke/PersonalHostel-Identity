"""Carta pública del establecimiento por enlace.

Sin token: el ``slug`` del enlace ``carta`` es la llave. Devuelve solo lectura
los productos disponibles (no archivados), agrupados por categoría, con precio.
No expone campos internos (``destino``, ``revision``, ``data_origin``).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db import get_negocio_db
from app.errors import ENLACE_NOT_FOUND, ENLACE_REVOCADO, ApiError
from app.models import (
    EnlaceEstado,
    EnlacePublico,
    EnlaceTipo,
    Establecimiento,
    ProductoCatalogo,
)
from app.schemas import CartaPublicaResponse, ErrorResponse

router = APIRouter(prefix="/v1/negocio", tags=["negocio público"])


def _establecimiento_por_carta_slug(db: Session, slug: str) -> Establecimiento:
    enlace = db.query(EnlacePublico).filter_by(slug=slug, tipo=EnlaceTipo.carta.value).one_or_none()
    if enlace is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="Enlace de carta no encontrado",
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
    return establecimiento


@router.get(
    "/carta",
    response_model=CartaPublicaResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def carta_negocio(
    slug: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_por_carta_slug(db, slug)
    productos = (
        db.query(ProductoCatalogo)
        .filter_by(
            establecimiento_id=establecimiento.id,
            archived_at=None,
            disponible=True,
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
    response.headers["Cache-Control"] = "public, max-age=300"
    return {
        "establecimiento_id": establecimiento.id,
        "nombre": establecimiento.nombre,
        "categorias": [
            {"nombre": nombre, "productos": items} for nombre, items in categorias.items()
        ],
    }
