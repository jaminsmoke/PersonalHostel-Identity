"""Fondos de la web pública por sección (gestión JWT).

El dueño asigna un fondo de catálogo Estate o sube una foto propia por slot
(``inicio``, ``horario``, ``carta``, ``equipo``, ``contacto``). La galería
sigue siendo un álbum aparte (``uso=galeria``).
"""

import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.db import get_negocio_db
from app.errors import FOTO_INEXISTENTE, FOTO_INVALIDA, ApiError
from app.fondos import (
    SECCIONES,
    asignar_catalogo,
    asignar_upload,
    borrar_upload_slot,
    catalogo_publico,
    exigir_seccion,
    exigir_upload_publico,
    limpiar_slot,
    resolver_todos,
    uso_fondo,
)
from app.images import IMAGEN_WEB_MAX_INPUT_BYTES, FotoInvalida, normalizar_imagen_web
from app.models import CuentaNegocio, ImagenEstablecimiento
from app.rate_limit import OPENAPI_RATE_LIMIT, enforce_upload_cuenta
from app.routes.establecimientos import _establecimiento_de_cuenta
from app.routes.perfil_web import get_perfil
from app.schemas import (
    CatalogoFondoItem,
    ErrorResponse,
    FondosAsignadosResponse,
    FondosUpdateRequest,
)
from app.storage import get_foto_storage

router = APIRouter(prefix="/v1/establecimientos", tags=["fondos web"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}
_FORBIDDEN = {"model": ErrorResponse}
_NOT_FOUND = {"model": ErrorResponse}
_VALIDATION = {"model": ErrorResponse}


def _servir(clave: str, mimetype: str | None, cache: str) -> Response:
    data = get_foto_storage().leer(clave)
    if data is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="La imagen no está disponible",
        )
    return Response(
        content=data,
        media_type=mimetype or "image/webp",
        headers={
            "Cache-Control": cache,
            "ETag": f'"{clave}"',
        },
    )


@router.get(
    "/{establecimiento_id}/fondos/catalogo",
    response_model=list[CatalogoFondoItem],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def listar_catalogo_fondos(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[dict]:
    _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    return catalogo_publico()


@router.get(
    "/{establecimiento_id}/fondos",
    response_model=FondosAsignadosResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def obtener_fondos(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    perfil = get_perfil(db, establecimiento)
    return resolver_todos(perfil)


@router.put(
    "/{establecimiento_id}/fondos",
    response_model=FondosAsignadosResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
    },
)
def actualizar_fondos(
    establecimiento_id: uuid.UUID,
    body: FondosUpdateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    perfil = get_perfil(db, establecimiento)
    storage = get_foto_storage()
    for slot in SECCIONES:
        if slot not in body.model_fields_set:
            continue
        valor = getattr(body, slot)
        borrar_upload_slot(db, perfil, slot, storage=storage)
        if valor is None:
            limpiar_slot(perfil, slot)
        else:
            asignar_catalogo(perfil, slot, valor.id)
    db.commit()
    db.refresh(perfil)
    return resolver_todos(perfil)


@router.get(
    "/{establecimiento_id}/fondos/{slot}",
    responses={
        status.HTTP_200_OK: {
            "content": {"image/webp": {}},
            "description": "Fondo propio del slot (WebP).",
        },
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
    },
)
def obtener_fondo_upload(
    establecimiento_id: uuid.UUID,
    slot: str,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    exigir_seccion(slot)
    perfil = get_perfil(db, establecimiento)
    imagen = exigir_upload_publico(db, perfil, slot)
    return _servir(imagen.clave, imagen.mimetype, "private, max-age=300")


@router.post(
    "/{establecimiento_id}/fondos/{slot}",
    response_model=FondosAsignadosResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
        **OPENAPI_RATE_LIMIT,
    },
)
async def subir_fondo(
    establecimiento_id: uuid.UUID,
    slot: str,
    imagen: UploadFile = File(...),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    enforce_upload_cuenta(cuenta.id)
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    exigir_seccion(slot)
    perfil = get_perfil(db, establecimiento)
    data = await imagen.read(IMAGEN_WEB_MAX_INPUT_BYTES + 1)
    try:
        payload, mimetype, size = normalizar_imagen_web(data)
    except FotoInvalida as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=FOTO_INVALIDA,
            detail=str(exc),
        ) from exc

    storage = get_foto_storage()
    borrar_upload_slot(db, perfil, slot, storage=storage)
    clave = storage.guardar(establecimiento.id, payload, "webp")
    fila = ImagenEstablecimiento(
        establecimiento_id=establecimiento.id,
        clave=clave,
        mimetype=mimetype,
        size=size,
        uso=uso_fondo(slot),
        data_origin=establecimiento.data_origin,
    )
    db.add(fila)
    db.flush()
    asignar_upload(perfil, slot, fila.id)
    db.commit()
    db.refresh(perfil)
    return resolver_todos(perfil)


@router.delete(
    "/{establecimiento_id}/fondos/{slot}",
    response_model=FondosAsignadosResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
    },
)
def borrar_fondo(
    establecimiento_id: uuid.UUID,
    slot: str,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    exigir_seccion(slot)
    perfil = get_perfil(db, establecimiento)
    borrar_upload_slot(db, perfil, slot, storage=get_foto_storage())
    limpiar_slot(perfil, slot)
    db.commit()
    db.refresh(perfil)
    return resolver_todos(perfil)
