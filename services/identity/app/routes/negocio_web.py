"""Web pública del negocio por enlace (sitio completo en una llamada).

Sin token: el ``slug`` de un enlace público (``web`` o ``carta``; residual
``ficha_negocio``) es la llave. La SPA en
``web.negocio.siberia.solutions/negocios/{slug}`` (y rutas hijas ``/carta``,
``/horario``, …) pinta toda la superficie con esta respuesta.

Si el establecimiento tiene ``web_publica=false``, toda la superficie responde
``410 identity.web_privada`` con ``Cache-Control: no-store``; el logo del local
es branding público por diseño y se sirve siempre.
"""

import uuid
from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_negocio_db
from app.errors import ENLACE_NOT_FOUND, ENLACE_REVOCADO, FOTO_INEXISTENTE, WEB_PRIVADA, ApiError
from app.internal import get_camareros_internal
from app.models import (
    CuentaNegocio,
    EnlaceEstado,
    EnlacePublico,
    EnlaceTipo,
    Establecimiento,
    ImagenEstablecimiento,
    Membresia,
    MembresiaEstado,
    PerfilEstablecimiento,
    ProductoCatalogo,
)
from app.routes.horario import filas_horario_establecimiento
from app.routes.perfil_web import get_perfil
from app.schemas import (
    ErrorResponse,
    HorarioDia,
    WebNegocioPublica,
)
from app.storage import get_foto_storage

router = APIRouter(prefix="/v1/negocio", tags=["negocio público"])

_TIPOS_WEB = (
    EnlaceTipo.web.value,
    EnlaceTipo.carta.value,
    EnlaceTipo.ficha_negocio.value,
)


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


def _web_privada(db: Session, establecimiento: Establecimiento) -> bool:
    """True si la superficie pública está apagada por el dueño del local."""
    perfil = get_perfil(db, establecimiento)
    return not perfil.web_publica


def _respuesta_privada(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_410_GONE,
        content={
            "code": WEB_PRIVADA,
            "detail": detail,
        },
        headers={"Cache-Control": "no-store"},
    )


def _logo_url(slug: str, establecimiento: Establecimiento) -> str | None:
    if not establecimiento.logo_efectivo_clave:
        return None
    return f"/v1/negocio/web/logo?slug={slug}"


def _hero_url(slug: str, perfil: PerfilEstablecimiento) -> str | None:
    if not perfil.hero_clave:
        return None
    return f"/v1/negocio/web/hero?slug={slug}"


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


def _abierto_ahora(
    db: Session, establecimiento: Establecimiento, perfil: PerfilEstablecimiento
) -> dict | None:
    """Estado actual del local respecto a su horario, en el huso del local.

    El reloj se resuelve en Postgres (``now() AT TIME ZONE``) para no depender de
    datos de tz localizados en el contenedor; ``proximo_cambio`` es el próximo
    cambio abrir/cerrar dentro de la semana, en hora local del establecimiento.
    """
    filas = filas_horario_establecimiento(db, establecimiento.id)
    if not filas:
        return None
    tz = perfil.tz or "Europe/Madrid"
    try:
        local_now, dow_pg = db.execute(
            text("SELECT now() AT TIME ZONE :tz, extract(dow FROM now() AT TIME ZONE :tz)::int"),
            {"tz": tz},
        ).one()
    except Exception:
        return None
    if not isinstance(local_now, datetime):
        return None
    # extract(dow): 0=domingo..6=sábado → día local (0=lunes, 6=domingo).
    dia_semana = (dow_pg + 6) % 7
    eventos: list[tuple[datetime, datetime]] = []
    for offset in range(8):
        fecha = local_now.date() + timedelta(days=offset)
        fila = next((f for f in filas if f.dia_semana == (dia_semana + offset) % 7), None)
        if fila is None or fila.cerrado:
            continue
        for turno in fila.turnos or []:
            try:
                abre = datetime.combine(fecha, time.fromisoformat(turno["abre"]))
                cierra = datetime.combine(fecha, time.fromisoformat(turno["cierra"]))
            except KeyError, TypeError, ValueError:
                continue
            eventos.append((abre, cierra))
    abierto = any(a <= local_now < c for a, c in eventos)
    futuros = sorted(e for a, c in eventos for e in (a, c) if e > local_now)
    return {
        "abierto": abierto,
        "proximo_cambio": futuros[0].isoformat() if futuros else None,
    }


def _equipo_publico(
    db: Session, establecimiento: Establecimiento, perfil: PerfilEstablecimiento
) -> list[dict]:
    """Equipo visible en la web (matriz AND: local + camarero).

    Solo aparece un miembro si el local tiene ``mostrar_equipo`` y el camarero
    tiene ``aparecer_web_negocio``; cada campo respeta la visibilidad pública del
    camarero (nick y foto opt-in).
    """
    if not perfil.mostrar_equipo:
        return []
    filas = (
        db.query(Membresia)
        .filter(
            Membresia.establecimiento_id == establecimiento.id,
            Membresia.estado == MembresiaEstado.activa,
        )
        .order_by(Membresia.creada_en)
        .all()
    )
    interno = get_camareros_internal()
    equipo: list[dict] = []
    for membresia in filas:
        publico = interno.perfil_publico(membresia.camarero_id)
        if publico is None or not publico["aparecer_web_negocio"]:
            continue
        equipo.append(
            {
                "camarero_id": publico["camarero_id"],
                "nombre": publico["nombre"],
                "apellidos": publico["apellidos"],
                "nick": publico["nick"],
                "foto_url": (
                    f"/v1/camareros/ficha/foto/{publico['camarero_id']}"
                    if publico["foto_publica"]
                    else None
                ),
                "rol": membresia.rol.value,
            }
        )
    return equipo


def _galeria_publica(db: Session, slug: str, establecimiento: Establecimiento) -> list[dict]:
    imagenes = (
        db.query(ImagenEstablecimiento)
        .filter_by(establecimiento_id=establecimiento.id)
        .order_by(ImagenEstablecimiento.orden, ImagenEstablecimiento.created_at)
        .all()
    )
    return [
        {
            "id": imagen.id,
            "url": f"/v1/negocio/web/galeria/{imagen.id}?slug={slug}",
        }
        for imagen in imagenes
    ]


def _servir_publico(clave: str, mimetype: str | None) -> Response:
    data = get_foto_storage().leer(clave)
    if data is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="La imagen no está disponible",
        )
    return Response(
        content=data,
        media_type=mimetype or "image/webp",
        headers={
            "Cache-Control": "public, max-age=300",
            "ETag": f'"{clave}"',
        },
    )


def servir_logo_efectivo(establecimiento: Establecimiento) -> Response:
    """Sirve el logo efectivo del establecimiento con cache pública."""
    clave = establecimiento.logo_efectivo_clave
    if not clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El negocio no tiene logo",
        )
    data = get_foto_storage().leer(clave)
    if data is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El logo no está disponible",
        )
    return Response(
        content=data,
        media_type=establecimiento.logo_efectivo_mimetype or "image/webp",
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": f'"{clave}"',
        },
    )


def producto_carta_publico(producto: ProductoCatalogo) -> dict:
    """DTO de carta: nombre, precio, destino y descripción opcional."""
    item: dict = {
        "nombre": producto.nombre,
        "precio_centimos": producto.precio_centimos,
        "moneda": producto.moneda,
        "destino": producto.destino.value,
    }
    if producto.descripcion:
        item["descripcion"] = producto.descripcion
    return item


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
        categorias.setdefault(producto.categoria, []).append(producto_carta_publico(producto))
    return [{"nombre": nombre, "productos": items} for nombre, items in categorias.items()]


@router.get(
    "/web",
    response_model=WebNegocioPublica,
    response_model_exclude_unset=True,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def web_negocio(
    slug: str,
    response: Response,
    db: Session = Depends(get_negocio_db),
) -> dict | JSONResponse:
    establecimiento = _establecimiento_por_slug(db, slug)
    if _web_privada(db, establecimiento):
        return _respuesta_privada("La web de este establecimiento es privada")
    perfil = get_perfil(db, establecimiento)
    response.headers["Cache-Control"] = "public, max-age=300"
    perfil_seccion = {
        "eslogan": perfil.eslogan,
        "descripcion": perfil.descripcion,
        "direccion": perfil.direccion,
        "ciudad": perfil.ciudad,
    }
    contacto_seccion = {
        "telefono": perfil.telefono,
        "email_contacto": perfil.email_contacto,
        "web": perfil.web,
        "redes": perfil.redes or {},
    }
    if not any(perfil_seccion.values()):
        perfil_seccion = None
    if (
        not any(contacto_seccion[k] for k in ("telefono", "email_contacto", "web"))
        and not contacto_seccion["redes"]
    ):
        contacto_seccion = None
    hero_url = _hero_url(slug, perfil)
    return {
        "establecimiento_id": establecimiento.id,
        "nombre": establecimiento.nombre,
        "tipo_establecimiento": establecimiento.tipo_efectivo,
        "logo_url": _logo_url(slug, establecimiento),
        "organizacion_nombre": establecimiento.cuenta_negocio.nombre_mostrar,
        "plantilla": perfil.plantilla or "estate_hospitality",
        "color_primario": perfil.color_primario,
        "perfil": perfil_seccion,
        "contacto": contacto_seccion,
        "hero": {"url": hero_url} if hero_url else None,
        "galeria": _galeria_publica(db, slug, establecimiento),
        "abierto_ahora": _abierto_ahora(db, establecimiento, perfil),
        "horario": _horario_publico(db, establecimiento),
        "equipo": _equipo_publico(db, establecimiento, perfil),
        "categorias": _categorias(db, establecimiento),
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


@router.get(
    "/web/hero",
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def web_negocio_hero(
    slug: str,
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_por_slug(db, slug)
    if _web_privada(db, establecimiento):
        return _respuesta_privada("La web de este establecimiento es privada")
    perfil = get_perfil(db, establecimiento)
    if not perfil.hero_clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="El establecimiento no tiene imagen de portada",
        )
    return _servir_publico(perfil.hero_clave, perfil.hero_mimetype)


@router.get(
    "/web/galeria/{imagen_id}",
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def web_negocio_galeria(
    imagen_id: uuid.UUID,
    slug: str,
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_por_slug(db, slug)
    if _web_privada(db, establecimiento):
        return _respuesta_privada("La web de este establecimiento es privada")
    imagen = (
        db.query(ImagenEstablecimiento)
        .filter_by(id=imagen_id, establecimiento_id=establecimiento.id)
        .one_or_none()
    )
    if imagen is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ENLACE_NOT_FOUND,
            detail="La imagen no existe",
        )
    return _servir_publico(imagen.clave, imagen.mimetype)
