import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from pydantic import EmailStr
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    get_current_actor,
    get_current_camarero_id_optional,
    get_current_cuenta_negocio,
)
from app.db import get_negocio_db
from app.errors import (
    CAMARERO_NOT_FOUND,
    DATA_ORIGIN_MISMATCH,
    EMAIL_NOT_FOUND,
    ESTABLECIMIENTO_NOT_FOUND,
    FOTO_INEXISTENTE,
    FOTO_INVALIDA,
    INVITACION_DUPLICATE,
    INVITACION_EXPIRED,
    INVITACION_NOT_FOUND,
    INVITACION_USED,
    LAYOUT_NOT_FOUND,
    MEMBERSHIP_DUPLICATE,
    MEMBERSHIP_FORBIDDEN,
    VALIDATION_ERROR,
    ApiError,
)
from app.images import MAX_INPUT_BYTES, FotoInvalida, normalizar_foto
from app.internal import get_camareros_internal
from app.membresias import (
    _add_or_reactivate_membership,
    _estado_efectivo,
    _finalizar_aceptacion,
)
from app.models import (
    CuentaNegocio,
    EmailOutbox,
    EmailOutboxEstado,
    Establecimiento,
    Invitacion,
    InvitacionEstado,
    LayoutEstablecimiento,
    Membresia,
    MembresiaEstado,
    MembresiaRol,
    VisibleOtrosEstablecimientos,
)
from app.rate_limit import OPENAPI_RATE_LIMIT, enforce_upload_cuenta
from app.schemas import (
    CamareroDirectorioResponse,
    CamareroSearchResponse,
    ErrorResponse,
    EstablecimientoCreateRequest,
    EstablecimientoResponse,
    EstablecimientoUpdateRequest,
    InvitacionAcceptResponse,
    InvitacionCreateRequest,
    InvitacionRechazarResponse,
    InvitacionResponse,
    LayoutResponse,
    LayoutUpdateRequest,
    LogoNegocioResponse,
    MembresiaCreateRequest,
    MembresiaResponse,
    QrMemberRequest,
    layout_response_from_row,
)
from app.security import (
    get_session_secret_env,
    protect_invitation_token,
)
from app.storage import get_foto_storage

router = APIRouter(prefix="/v1/establecimientos", tags=["establecimientos"])
invitations_router = APIRouter(prefix="/v1/invitaciones", tags=["invitaciones"])

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


def _invitation_response(
    invitation: Invitacion, estado_efectivo: str | None = None
) -> InvitacionResponse:
    return InvitacionResponse(
        id=invitation.id,
        establecimiento_id=invitation.establecimiento_id,
        email=invitation.email_objetivo,
        rol=invitation.rol.value,
        estado=estado_efectivo or invitation.estado.value,
        expira_en=invitation.expira_en,
        creada_en=invitation.creada_en,
    )


@router.post(
    "",
    response_model=EstablecimientoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def crear_establecimiento(
    payload: EstablecimientoCreateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Establecimiento:
    establecimiento = Establecimiento(
        nombre=payload.nombre.strip(),
        tipo_establecimiento=payload.tipo_establecimiento or cuenta.tipo_establecimiento,
        cuenta_negocio_id=cuenta.id,
        data_origin=cuenta.data_origin,
    )
    db.add(establecimiento)
    db.flush()
    if cuenta.camarero_vinculado_id is not None:
        _add_or_reactivate_membership(
            db,
            establecimiento,
            cuenta.camarero_vinculado_id,
            MembresiaRol.dueno.value,
        )
    db.commit()
    db.refresh(establecimiento)
    return establecimiento


@router.patch(
    "/{establecimiento_id}",
    response_model=EstablecimientoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def actualizar_establecimiento(
    establecimiento_id: uuid.UUID,
    payload: EstablecimientoUpdateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Establecimiento:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    if payload.nombre is not None:
        establecimiento.nombre = payload.nombre.strip()
    if "tipo_establecimiento" in payload.model_fields_set:
        establecimiento.tipo_establecimiento = payload.tipo_establecimiento
    if "visible_directorio" in payload.model_fields_set:
        establecimiento.visible_directorio = payload.visible_directorio
    db.commit()
    db.refresh(establecimiento)
    return establecimiento


@router.post(
    "/{establecimiento_id}/logo",
    response_model=LogoNegocioResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        **OPENAPI_RATE_LIMIT,
    },
)
async def subir_logo_establecimiento(
    establecimiento_id: uuid.UUID,
    logo: UploadFile = File(...),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> LogoNegocioResponse:
    enforce_upload_cuenta(cuenta.id)
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    data = await logo.read(MAX_INPUT_BYTES + 1)
    try:
        processed, mimetype, size = normalizar_foto(data)
    except FotoInvalida as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=FOTO_INVALIDA,
            detail=str(exc),
        ) from exc
    storage = get_foto_storage()
    clave = storage.guardar(establecimiento.id, processed, "webp")
    if establecimiento.logo_clave:
        storage.borrar(establecimiento.logo_clave)
    establecimiento.logo_clave = clave
    establecimiento.logo_mimetype = mimetype
    establecimiento.logo_size = size
    establecimiento.logo_actualizada_en = datetime.now(UTC)
    db.commit()
    return LogoNegocioResponse(logo_url=establecimiento.logo_url)


@router.get(
    "/{establecimiento_id}/logo",
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def obtener_logo_establecimiento(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Response:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    clave = establecimiento.logo_efectivo_clave
    if not clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El establecimiento no tiene logo",
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
        headers={"ETag": f'"{clave}"'},
    )


@router.delete(
    "/{establecimiento_id}/logo",
    response_model=LogoNegocioResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def borrar_logo_establecimiento(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> LogoNegocioResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    if establecimiento.logo_clave:
        get_foto_storage().borrar(establecimiento.logo_clave)
    establecimiento.logo_clave = None
    establecimiento.logo_mimetype = None
    establecimiento.logo_size = None
    establecimiento.logo_actualizada_en = None
    db.commit()
    return LogoNegocioResponse(logo_url=establecimiento.logo_url)


@router.get(
    "/mios",
    response_model=list[EstablecimientoResponse],
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def mis_establecimientos(
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
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
    db: Session = Depends(get_negocio_db),
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
        if identidad != establecimiento.cuenta_negocio_id:
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
                camarero_id=identidad,
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


@router.put(
    "/{establecimiento_id}/layout",
    response_model=LayoutResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def guardar_layout(
    establecimiento_id: uuid.UUID,
    payload: LayoutUpdateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> LayoutResponse:
    """Copia de respaldo opaca del layout del mapa. Solo la cuenta dueña."""
    _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    snapshot = payload.snapshot()
    if len(payload.model_dump_json().encode("utf-8")) > 1_000_000:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code=VALIDATION_ERROR,
            detail="El layout supera el tamaño máximo de 1 MB",
        )
    layout = db.get(LayoutEstablecimiento, establecimiento_id)
    if layout is None:
        layout = LayoutEstablecimiento(
            establecimiento_id=establecimiento_id,
            documento=snapshot,
            version=1,
        )
        db.add(layout)
    else:
        layout.documento = snapshot
        layout.version += 1
    db.commit()
    db.refresh(layout)
    return layout_response_from_row(
        layout.establecimiento_id, layout.version, layout.updated_at, layout.documento
    )


@router.get(
    "/{establecimiento_id}/layout",
    response_model=LayoutResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def obtener_layout(
    establecimiento_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> LayoutResponse:
    """Devuelve la copia de respaldo opaca del layout. Solo la cuenta dueña."""
    _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    layout = db.get(LayoutEstablecimiento, establecimiento_id)
    if layout is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=LAYOUT_NOT_FOUND,
            detail="El establecimiento no tiene un layout respaldado",
        )
    return layout_response_from_row(
        layout.establecimiento_id, layout.version, layout.updated_at, layout.documento
    )


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
    db: Session = Depends(get_negocio_db),
) -> Membresia:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    membership = _add_or_reactivate_membership(
        db, establecimiento, payload.camarero_id, payload.rol
    )
    try:
        db.commit()
        db.refresh(membership)
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=MEMBERSHIP_DUPLICATE,
            detail="El camarero ya pertenece a este establecimiento",
        ) from exc
    return membership


@router.post(
    "/{establecimiento_id}/miembros/qr",
    response_model=MembresiaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def añadir_miembro_por_qr(
    establecimiento_id: uuid.UUID,
    payload: QrMemberRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> Membresia:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    camarero_id = get_camareros_internal().verificar_qr(payload.qr)
    membership = _add_or_reactivate_membership(db, establecimiento, camarero_id, payload.rol)
    db.commit()
    db.refresh(membership)
    return membership


@router.get(
    "/{establecimiento_id}/camareros/buscar",
    response_model=CamareroSearchResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def buscar_camarero(
    establecimiento_id: uuid.UUID,
    email: EmailStr,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> dict:
    _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    camarero = get_camareros_internal().buscar_por_email(str(email).lower())
    if camarero is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=EMAIL_NOT_FOUND,
            detail="No hay un camarero registrado con ese email",
        )
    return camarero


@router.get(
    "/{establecimiento_id}/camareros/directorio",
    response_model=list[CamareroDirectorioResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def directorio_camareros(
    establecimiento_id: uuid.UUID,
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[dict]:
    """Directorio de camareros visibles para invitar (sin email).

    Solo camareros que han optado por ser vistos (``siempre`` o ``solo_libre``).
    Los dueños de establecimiento nunca aparecen: pertenecen al dominio de
    establecimientos, no al de camareros. Quedan fuera también los miembros del
    propio establecimiento y los de distinta ``data_origin``.
    """
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)

    # Dueños: vinculados a una cuenta de negocio o con membresía de dueño activa.
    owner_ids = {
        row[0]
        for row in db.query(CuentaNegocio.camarero_vinculado_id)
        .filter(CuentaNegocio.camarero_vinculado_id.isnot(None))
        .all()
    }
    owner_ids |= {
        row[0]
        for row in db.query(Membresia.camarero_id)
        .filter(
            Membresia.rol == MembresiaRol.dueno,
            Membresia.estado == MembresiaEstado.activa,
        )
        .all()
    }

    # Ocupados: con membresía activa en cualquier establecimiento.
    occupied_ids = {
        row[0]
        for row in db.query(Membresia.camarero_id)
        .filter(Membresia.estado == MembresiaEstado.activa)
        .all()
    }

    # Miembros de este establecimiento (ya en el equipo; no invitables).
    this_members = {
        row[0]
        for row in db.query(Membresia.camarero_id)
        .filter(
            Membresia.establecimiento_id == establecimiento.id,
            Membresia.estado == MembresiaEstado.activa,
        )
        .all()
    }

    candidatos = get_camareros_internal().directorio()
    resultado: list[dict] = []
    for entry in candidatos:
        camarero_id = uuid.UUID(entry["id"])
        if camarero_id in owner_ids or camarero_id in this_members:
            continue
        if entry["data_origin"] != establecimiento.data_origin.value:
            continue
        libre = camarero_id not in occupied_ids
        if (
            entry["visible_otros_establecimientos"] == VisibleOtrosEstablecimientos.solo_libre.value
            and not libre
        ):
            continue
        if q:
            haystack = " ".join(
                filter(None, [entry["nombre"], entry["apellidos"], entry["nick"]])
            ).lower()
            if q.lower() not in haystack:
                continue
        resultado.append(
            {
                "id": camarero_id,
                "nombre": entry["nombre"],
                "apellidos": entry["apellidos"],
                "nick": entry["nick"],
                "foto_url": (
                    f"/v1/camareros/ficha/foto/{camarero_id}" if entry.get("foto_publica") else None
                ),
                "libre": libre,
                "visibilidad": entry["visible_otros_establecimientos"],
            }
        )
        if len(resultado) >= limit:
            break

    return resultado


@router.post(
    "/{establecimiento_id}/invitaciones",
    response_model=InvitacionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def crear_invitacion(
    establecimiento_id: uuid.UUID,
    payload: InvitacionCreateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> InvitacionResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    if payload.camarero_id is not None:
        perfil = get_camareros_internal().perfil(payload.camarero_id)
        if perfil is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code=CAMARERO_NOT_FOUND,
                detail="Camarero no encontrado",
            )
        if perfil["data_origin"] != establecimiento.data_origin.value:
            raise ApiError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code=DATA_ORIGIN_MISMATCH,
                detail="El camarero y el establecimiento deben tener la misma procedencia",
            )
        email = str(perfil["email"]).lower()
        camarero_id = payload.camarero_id
    else:
        email = str(payload.email).lower()
        camarero = get_camareros_internal().buscar_por_email(email)
        if camarero is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code=EMAIL_NOT_FOUND,
                detail="No hay un camarero registrado con ese email",
            )
        camarero_id = uuid.UUID(camarero["id"])
    active_membership = (
        db.query(Membresia)
        .filter_by(
            establecimiento_id=establecimiento.id,
            camarero_id=camarero_id,
            estado=MembresiaEstado.activa,
        )
        .one_or_none()
    )
    if active_membership is not None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=MEMBERSHIP_DUPLICATE,
            detail="El camarero ya pertenece a este establecimiento",
        )
    now = datetime.now(UTC)
    pending = (
        db.query(Invitacion)
        .filter(
            Invitacion.establecimiento_id == establecimiento.id,
            Invitacion.email_objetivo == email,
            Invitacion.estado == InvitacionEstado.pendiente,
            Invitacion.expira_en > now,
        )
        .one_or_none()
    )
    if pending is not None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=INVITACION_DUPLICATE,
            detail="Ya existe una invitación pendiente para ese email",
        )
    token = secrets.token_urlsafe(32)
    expires = now + timedelta(hours=max(1, int(os.environ.get("INVITATION_TTL_HOURS", "72"))))
    invitation = Invitacion(
        establecimiento_id=establecimiento.id,
        cuenta_negocio_id=cuenta.id,
        email_objetivo=email,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        rol=MembresiaRol(payload.rol),
        estado=InvitacionEstado.pendiente,
        expira_en=expires,
    )
    db.add(invitation)
    db.flush()
    outbox = EmailOutbox(
        invitacion_id=invitation.id,
        tipo="invitacion_establecimiento",
        destinatario=email,
        payload={
            "token_encrypted": protect_invitation_token(token, get_session_secret_env()),
            "invitation_url_base": os.environ.get(
                "INVITATION_URL_BASE", "http://localhost:8084/invitaciones"
            ),
            "establishment_name": establecimiento.nombre,
        },
        estado=EmailOutboxEstado.pendiente,
    )
    db.add(outbox)
    db.commit()
    db.refresh(invitation)
    return _invitation_response(invitation)


@router.post(
    "/{establecimiento_id}/invitaciones/{invitacion_id}/revocar",
    response_model=InvitacionResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def revocar_invitacion(
    establecimiento_id: uuid.UUID,
    invitacion_id: uuid.UUID,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> InvitacionResponse:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    invitation = (
        db.query(Invitacion)
        .filter_by(id=invitacion_id, establecimiento_id=establecimiento.id)
        .one_or_none()
    )
    if invitation is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=INVITACION_NOT_FOUND,
            detail="Invitación no encontrada",
        )
    if invitation.estado == InvitacionEstado.pendiente:
        invitation.estado = InvitacionEstado.revocada
        invitation.revocada_en = datetime.now(UTC)
        db.commit()
        db.refresh(invitation)
    return _invitation_response(invitation)


@router.get(
    "/{establecimiento_id}/invitaciones",
    response_model=list[InvitacionResponse],
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def listar_invitaciones(
    establecimiento_id: uuid.UUID,
    estado: InvitacionEstado | None = Query(default=None),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> list[InvitacionResponse]:
    establecimiento = _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    now = datetime.now(UTC)
    query = db.query(Invitacion).filter(Invitacion.establecimiento_id == establecimiento.id)
    if estado == InvitacionEstado.pendiente:
        query = query.filter(
            Invitacion.estado == InvitacionEstado.pendiente,
            Invitacion.expira_en > now,
        )
    elif estado == InvitacionEstado.expirada:
        query = query.filter(
            or_(
                Invitacion.estado == InvitacionEstado.expirada,
                and_(
                    Invitacion.estado == InvitacionEstado.pendiente,
                    Invitacion.expira_en <= now,
                ),
            )
        )
    elif estado is not None:
        query = query.filter(Invitacion.estado == estado)
    invitations = query.order_by(Invitacion.creada_en.desc()).all()
    return [_invitation_response(inv, _estado_efectivo(inv, now)) for inv in invitations]


@invitations_router.post(
    "/{token}/aceptar",
    response_model=InvitacionAcceptResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    },
)
def aceptar_invitacion(
    token: str,
    camarero_id: uuid.UUID | None = Depends(get_current_camarero_id_optional),
    db: Session = Depends(get_negocio_db),
) -> InvitacionAcceptResponse:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = db.query(Invitacion).filter_by(token_hash=token_hash).one_or_none()
    if invitation is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=INVITACION_NOT_FOUND,
            detail="Invitación no encontrada",
        )
    if camarero_id is None:
        perfil = get_camareros_internal().buscar_por_email(invitation.email_objetivo)
        if perfil is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code=CAMARERO_NOT_FOUND,
                detail="No existe una cuenta para el email de la invitación",
            )
        camarero_id = uuid.UUID(perfil["id"])
    membership = _finalizar_aceptacion(db, invitation, camarero_id)
    return InvitacionAcceptResponse(invitacion_id=invitation.id, membresia=membership)


@invitations_router.post(
    "/{token}/rechazar",
    response_model=InvitacionRechazarResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def rechazar_invitacion(
    token: str,
    db: Session = Depends(get_negocio_db),
) -> InvitacionRechazarResponse:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = db.query(Invitacion).filter_by(token_hash=token_hash).one_or_none()
    if invitation is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=INVITACION_NOT_FOUND,
            detail="Invitación no encontrada",
        )
    now = datetime.now(UTC)
    if invitation.estado != InvitacionEstado.pendiente:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=INVITACION_USED,
            detail="La invitación ya no está disponible",
        )
    if invitation.expira_en <= now:
        invitation.estado = InvitacionEstado.expirada
        db.commit()
        raise ApiError(
            status_code=status.HTTP_410_GONE,
            code=INVITACION_EXPIRED,
            detail="La invitación ha expirado",
        )
    invitation.estado = InvitacionEstado.rechazada
    invitation.revocada_en = now
    db.commit()
    return InvitacionRechazarResponse(
        invitacion_id=invitation.id,
        estado=invitation.estado.value,
    )


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
    db: Session = Depends(get_negocio_db),
) -> list[Membresia]:
    establecimiento = db.get(Establecimiento, establecimiento_id)
    if establecimiento is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=ESTABLECIMIENTO_NOT_FOUND,
            detail="Establecimiento no encontrado",
        )
    tipo, identidad = actor
    autorizado = tipo == "negocio" and identidad == establecimiento.cuenta_negocio_id
    if tipo == "camarero" and not autorizado:
        autorizado = (
            db.query(Membresia)
            .filter_by(
                establecimiento_id=establecimiento.id,
                camarero_id=identidad,
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
    db: Session = Depends(get_negocio_db),
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
    membership.revocada_en = datetime.now(UTC)
    db.commit()
    db.refresh(membership)
    return membership
