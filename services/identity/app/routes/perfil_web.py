"""Perfil público y galería de la web del establecimiento (gestión).

Gestión con JWT de negocio (dueño del establecimiento): leer/editar el perfil de
la web y subir/borrar las imágenes (hero y galería). La lectura pública vive en
``negocio_web.py``; la cuenta de negocio (y Bar vía este contrato) alimenta la
superficie pública.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.auth import get_current_cuenta_negocio
from app.db import get_negocio_db
from app.errors import FOTO_INEXISTENTE, FOTO_INVALIDA, ApiError
from app.images import IMAGEN_WEB_MAX_INPUT_BYTES, FotoInvalida, normalizar_imagen_web
from app.models import (
    CuentaNegocio,
    Establecimiento,
    ImagenEstablecimiento,
    PerfilEstablecimiento,
)
from app.rate_limit import OPENAPI_RATE_LIMIT, enforce_upload_cuenta
from app.routes.establecimientos import _establecimiento_de_cuenta
from app.schemas import (
    ErrorResponse,
    ImagenEstablecimientoResponse,
    PerfilEstablecimientoResponse,
    PerfilEstablecimientoUpdateRequest,
)
from app.storage import get_foto_storage

router = APIRouter(prefix="/v1/establecimientos", tags=["perfil web"])

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}
_FORBIDDEN = {"model": ErrorResponse}
_NOT_FOUND = {"model": ErrorResponse}
_VALIDATION = {"model": ErrorResponse}


def get_perfil(db: Session, establecimiento: Establecimiento) -> PerfilEstablecimiento:
    """Devuelve el perfil del establecimiento, creándolo con defaults si falta."""
    perfil = (
        db.query(PerfilEstablecimiento)
        .filter_by(establecimiento_id=establecimiento.id)
        .one_or_none()
    )
    if perfil is None:
        perfil = PerfilEstablecimiento(
            establecimiento_id=establecimiento.id,
            data_origin=establecimiento.data_origin,
        )
        db.add(perfil)
        db.commit()
        db.refresh(perfil)
    return perfil


def _perfil_response(perfil: PerfilEstablecimiento) -> dict:
    hero_url = None
    if perfil.hero_clave:
        hero_url = f"/v1/establecimientos/{perfil.establecimiento_id}/hero"
    return {
        "establecimiento_id": perfil.establecimiento_id,
        "eslogan": perfil.eslogan,
        "descripcion": perfil.descripcion,
        "direccion": perfil.direccion,
        "ciudad": perfil.ciudad,
        "telefono": perfil.telefono,
        "email_contacto": perfil.email_contacto,
        "web": perfil.web,
        "redes": perfil.redes or {},
        "tz": perfil.tz,
        "plantilla": perfil.plantilla,
        "color_primario": perfil.color_primario,
        "web_publica": perfil.web_publica,
        "mostrar_equipo": perfil.mostrar_equipo,
        "hero_url": hero_url,
    }


def _servir_imagen(clave: str, mimetype: str | None, cache: str) -> Response:
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


def _imagen_response(establecimiento_id: uuid.UUID, imagen: ImagenEstablecimiento) -> dict:
    return {
        "id": imagen.id,
        "establecimiento_id": establecimiento_id,
        "url": f"/v1/establecimientos/{establecimiento_id}/galeria/{imagen.id}",
        "mimetype": imagen.mimetype,
        "size": imagen.size,
        "orden": imagen.orden,
        "creada_en": imagen.created_at,
    }


@router.get(
    "/{establecimiento_id}/perfil-web",
    response_model=PerfilEstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def obtener_perfil_web(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    perfil = get_perfil(db, establecimiento)
    return _perfil_response(perfil)


@router.patch(
    "/{establecimiento_id}/perfil-web",
    response_model=PerfilEstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
    },
)
def actualizar_perfil_web(
    establecimiento_id: uuid.UUID,
    payload: PerfilEstablecimientoUpdateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    perfil = get_perfil(db, establecimiento)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(perfil, campo, valor)
    db.commit()
    db.refresh(perfil)
    return _perfil_response(perfil)


@router.post(
    "/{establecimiento_id}/hero",
    response_model=PerfilEstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
        **OPENAPI_RATE_LIMIT,
    },
)
async def subir_hero(
    establecimiento_id: uuid.UUID,
    hero: UploadFile = File(...),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    enforce_upload_cuenta(cuenta.id)
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    data = await hero.read(IMAGEN_WEB_MAX_INPUT_BYTES + 1)
    try:
        payload, mimetype, size = normalizar_imagen_web(data)
    except FotoInvalida as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=FOTO_INVALIDA,
            detail=str(exc),
        ) from exc

    perfil = get_perfil(db, establecimiento)
    storage = get_foto_storage()
    if perfil.hero_clave:
        storage.borrar(perfil.hero_clave)

    clave = storage.guardar(establecimiento.id, payload, "webp")
    perfil.hero_clave = clave
    perfil.hero_mimetype = mimetype
    perfil.hero_size = size
    perfil.hero_actualizada_en = datetime.now(UTC)
    db.commit()
    db.refresh(perfil)
    return _perfil_response(perfil)


@router.delete(
    "/{establecimiento_id}/hero",
    response_model=PerfilEstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def borrar_hero(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    perfil = get_perfil(db, establecimiento)
    if perfil.hero_clave:
        get_foto_storage().borrar(perfil.hero_clave)
        perfil.hero_clave = None
        perfil.hero_mimetype = None
        perfil.hero_size = None
        perfil.hero_actualizada_en = None
        db.commit()
        db.refresh(perfil)
    return _perfil_response(perfil)


@router.get(
    "/{establecimiento_id}/hero",
    responses={
        status.HTTP_200_OK: {
            "content": {"image/webp": {}},
            "description": "Imagen de portada (WebP).",
        },
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def obtener_hero(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    perfil = get_perfil(db, establecimiento)
    if not perfil.hero_clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El establecimiento no tiene imagen de portada",
        )
    return _servir_imagen(perfil.hero_clave, perfil.hero_mimetype, "private, max-age=300")


@router.get(
    "/{establecimiento_id}/galeria",
    response_model=list[ImagenEstablecimientoResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def listar_galeria(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[dict]:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    imagenes = (
        db.query(ImagenEstablecimiento)
        .filter_by(establecimiento_id=establecimiento.id, uso="galeria")
        .order_by(ImagenEstablecimiento.orden, ImagenEstablecimiento.created_at)
        .all()
    )
    return [_imagen_response(establecimiento.id, img) for img in imagenes]


@router.post(
    "/{establecimiento_id}/galeria",
    response_model=ImagenEstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _VALIDATION,
        **OPENAPI_RATE_LIMIT,
    },
)
async def anadir_galeria(
    establecimiento_id: uuid.UUID,
    imagen: UploadFile = File(...),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    enforce_upload_cuenta(cuenta.id)
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
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
    clave = storage.guardar(establecimiento.id, payload, "webp")
    fila = ImagenEstablecimiento(
        establecimiento_id=establecimiento.id,
        clave=clave,
        mimetype=mimetype,
        size=size,
        uso="galeria",
        data_origin=establecimiento.data_origin,
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return _imagen_response(establecimiento.id, fila)


@router.get(
    "/{establecimiento_id}/galeria/{imagen_id}",
    responses={
        status.HTTP_200_OK: {
            "content": {"image/webp": {}},
            "description": "Imagen de galería (WebP).",
        },
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def obtener_galeria_imagen(
    establecimiento_id: uuid.UUID,
    imagen_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    imagen = (
        db.query(ImagenEstablecimiento)
        .filter_by(id=imagen_id, establecimiento_id=establecimiento.id, uso="galeria")
        .one_or_none()
    )
    if imagen is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="La imagen no existe",
        )
    return _servir_imagen(imagen.clave, imagen.mimetype, "private, max-age=300")


@router.delete(
    "/{establecimiento_id}/galeria/{imagen_id}",
    response_model=ImagenEstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: _FORBIDDEN,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def borrar_galeria_imagen(
    establecimiento_id: uuid.UUID,
    imagen_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    imagen = (
        db.query(ImagenEstablecimiento)
        .filter_by(id=imagen_id, establecimiento_id=establecimiento.id, uso="galeria")
        .one_or_none()
    )
    if imagen is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="La imagen no existe",
        )
    get_foto_storage().borrar(imagen.clave)
    db.delete(imagen)
    db.commit()
    return _imagen_response(establecimiento.id, imagen)
