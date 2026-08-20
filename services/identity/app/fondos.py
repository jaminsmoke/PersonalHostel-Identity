"""Catálogo de fondos Estate y resolución de slots de la web pública."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from fastapi import status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.errors import FONDO_INVALIDO, FOTO_INEXISTENTE, ApiError
from app.models import ImagenEstablecimiento, PerfilEstablecimiento

SECCIONES = ("inicio", "horario", "carta", "equipo", "contacto")

_WEB_BASE_ENV = "WEB_NEGOCIO_URL_BASE"


@dataclass(frozen=True)
class CatalogoFondo:
    id: str
    seccion: str


CATALOGO: tuple[CatalogoFondo, ...] = tuple(
    CatalogoFondo(id=f"estate-{seccion}-{n}", seccion=seccion)
    for seccion in SECCIONES
    for n in (1, 2)
)

_POR_ID = {item.id: item for item in CATALOGO}
DEFAULTS = {seccion: f"estate-{seccion}-1" for seccion in SECCIONES}


def uso_fondo(slot: str) -> str:
    return f"fondo_{slot}"


def web_base() -> str:
    return (os.environ.get(_WEB_BASE_ENV) or "").rstrip("/")


def url_catalogo(catalogo_id: str) -> str:
    base = web_base()
    path = f"/stubs/fondos/{catalogo_id}.webp"
    return f"{base}{path}" if base else path


def exigir_seccion(slot: str) -> str:
    if slot not in SECCIONES:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=FONDO_INVALIDO,
            detail="La sección de fondo no es válida",
        )
    return slot


def exigir_catalogo(slot: str, catalogo_id: str) -> CatalogoFondo:
    item = _POR_ID.get(catalogo_id)
    if item is None or item.seccion != slot:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=FONDO_INVALIDO,
            detail="El fondo de catálogo no pertenece a esa sección",
        )
    return item


def parse_uuid(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def catalogo_publico() -> list[dict]:
    return [
        {"id": item.id, "seccion": item.seccion, "url": url_catalogo(item.id)} for item in CATALOGO
    ]


def _raw_slot(perfil: PerfilEstablecimiento, slot: str) -> dict | None:
    raw = (perfil.fondos or {}).get(slot)
    if not isinstance(raw, dict):
        return None
    fuente = raw.get("fuente")
    if fuente == "catalogo":
        catalogo_id = raw.get("id")
        if (
            isinstance(catalogo_id, str)
            and catalogo_id in _POR_ID
            and _POR_ID[catalogo_id].seccion == slot
        ):
            return {"fuente": "catalogo", "id": catalogo_id}
        return None
    if fuente == "upload":
        imagen_id = parse_uuid(raw.get("imagen_id"))
        if imagen_id is not None:
            return {"fuente": "upload", "imagen_id": imagen_id}
        return None
    return None


def _url_hero(*, slug: str | None, establecimiento_id: uuid.UUID) -> str:
    if slug:
        return f"/v1/negocio/web/hero?slug={slug}"
    return f"/v1/establecimientos/{establecimiento_id}/hero"


def _url_upload(slot: str, *, slug: str | None, establecimiento_id: uuid.UUID) -> str:
    if slug:
        return f"/v1/negocio/web/fondo/{slot}?slug={slug}"
    return f"/v1/establecimientos/{establecimiento_id}/fondos/{slot}"


def resolver_slot(
    perfil: PerfilEstablecimiento,
    slot: str,
    *,
    slug: str | None = None,
) -> dict:
    """Resuelve un slot a ``{fuente, id?, url}``. Vacío → default de catálogo."""
    exigir_seccion(slot)
    raw = _raw_slot(perfil, slot)
    establecimiento_id = perfil.establecimiento_id
    if raw and raw["fuente"] == "upload":
        return {
            "fuente": "upload",
            "url": _url_upload(slot, slug=slug, establecimiento_id=establecimiento_id),
        }
    if raw and raw["fuente"] == "catalogo":
        catalogo_id = raw["id"]
        return {
            "fuente": "catalogo",
            "id": catalogo_id,
            "url": url_catalogo(catalogo_id),
        }
    if slot == "inicio" and perfil.hero_clave:
        return {
            "fuente": "hero",
            "url": _url_hero(slug=slug, establecimiento_id=establecimiento_id),
        }
    default_id = DEFAULTS[slot]
    return {
        "fuente": "catalogo",
        "id": default_id,
        "url": url_catalogo(default_id),
    }


def resolver_todos(perfil: PerfilEstablecimiento, *, slug: str | None = None) -> dict[str, dict]:
    return {slot: resolver_slot(perfil, slot, slug=slug) for slot in SECCIONES}


def _escribir(perfil: PerfilEstablecimiento, fondos: dict) -> None:
    perfil.fondos = fondos
    flag_modified(perfil, "fondos")


def imagen_upload(
    db: Session, establecimiento_id: uuid.UUID, slot: str
) -> ImagenEstablecimiento | None:
    return (
        db.query(ImagenEstablecimiento)
        .filter_by(establecimiento_id=establecimiento_id, uso=uso_fondo(slot))
        .one_or_none()
    )


def borrar_upload_slot(
    db: Session,
    perfil: PerfilEstablecimiento,
    slot: str,
    *,
    storage,
) -> None:
    imagen = imagen_upload(db, perfil.establecimiento_id, slot)
    if imagen is None:
        return
    storage.borrar(imagen.clave)
    db.delete(imagen)


def asignar_catalogo(perfil: PerfilEstablecimiento, slot: str, catalogo_id: str) -> None:
    exigir_catalogo(slot, catalogo_id)
    fondos = dict(perfil.fondos or {})
    fondos[slot] = {"fuente": "catalogo", "id": catalogo_id}
    _escribir(perfil, fondos)


def asignar_upload(perfil: PerfilEstablecimiento, slot: str, imagen_id: uuid.UUID) -> None:
    exigir_seccion(slot)
    fondos = dict(perfil.fondos or {})
    fondos[slot] = {"fuente": "upload", "imagen_id": str(imagen_id)}
    _escribir(perfil, fondos)


def limpiar_slot(perfil: PerfilEstablecimiento, slot: str) -> None:
    exigir_seccion(slot)
    fondos = dict(perfil.fondos or {})
    fondos.pop(slot, None)
    _escribir(perfil, fondos)


def exigir_upload_publico(
    db: Session, perfil: PerfilEstablecimiento, slot: str
) -> ImagenEstablecimiento:
    raw = _raw_slot(perfil, slot)
    if not raw or raw["fuente"] != "upload":
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El establecimiento no tiene fondo propio en esa sección",
        )
    imagen = (
        db.query(ImagenEstablecimiento)
        .filter_by(
            id=raw["imagen_id"],
            establecimiento_id=perfil.establecimiento_id,
            uso=uso_fondo(slot),
        )
        .one_or_none()
    )
    if imagen is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El fondo no está disponible",
        )
    return imagen
