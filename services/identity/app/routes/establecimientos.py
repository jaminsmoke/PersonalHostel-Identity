import hashlib
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, status
from pydantic import EmailStr
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
    EMAIL_NOT_FOUND,
    ESTABLECIMIENTO_NOT_FOUND,
    INVITACION_DUPLICATE,
    INVITACION_NOT_FOUND,
    LAYOUT_NOT_FOUND,
    MEMBERSHIP_DUPLICATE,
    MEMBERSHIP_FORBIDDEN,
    VALIDATION_ERROR,
    ApiError,
)
from app.internal import get_camareros_internal
from app.membresias import _add_or_reactivate_membership, _finalizar_aceptacion
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
)
from app.schemas import (
    CamareroSearchResponse,
    ErrorResponse,
    EstablecimientoCreateRequest,
    EstablecimientoResponse,
    InvitacionAcceptResponse,
    InvitacionCreateRequest,
    InvitacionResponse,
    LayoutResponse,
    LayoutUpdateRequest,
    MembresiaCreateRequest,
    MembresiaResponse,
    QrMemberRequest,
)
from app.security import (
    get_session_secret_env,
    protect_invitation_token,
)

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


def _invitation_response(invitation: Invitacion) -> InvitacionResponse:
    return InvitacionResponse(
        id=invitation.id,
        establecimiento_id=invitation.establecimiento_id,
        email=invitation.email_objetivo,
        rol=invitation.rol.value,
        estado=invitation.estado.value,
        expira_en=invitation.expira_en,
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
        cuenta_negocio_id=cuenta.id,
        data_origin=cuenta.data_origin,
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
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
def guardar_layout(
    establecimiento_id: uuid.UUID,
    payload: LayoutUpdateRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_negocio_db),
) -> LayoutEstablecimiento:
    """Copia de respaldo del layout del mapa. Solo la cuenta dueña."""
    _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    if len(payload.model_dump_json().encode("utf-8")) > 1_000_000:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=VALIDATION_ERROR,
            detail="El layout supera el tamaño máximo de 1 MB",
        )
    layout = db.get(LayoutEstablecimiento, establecimiento_id)
    if layout is None:
        layout = LayoutEstablecimiento(
            establecimiento_id=establecimiento_id,
            salas=payload.salas,
            mesas=payload.mesas,
            version=1,
        )
        db.add(layout)
    else:
        layout.salas = payload.salas
        layout.mesas = payload.mesas
        layout.version += 1
    db.commit()
    db.refresh(layout)
    return layout


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
) -> LayoutEstablecimiento:
    """Devuelve la copia de respaldo del layout del mapa. Solo la cuenta dueña."""
    _establecimiento_de_cuenta(establecimiento_id, cuenta, db)
    layout = db.get(LayoutEstablecimiento, establecimiento_id)
    if layout is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=LAYOUT_NOT_FOUND,
            detail="El establecimiento no tiene un layout respaldado",
        )
    return layout


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
                "INVITATION_URL_BASE", "http://localhost:8081/invitaciones"
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
