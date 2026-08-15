"""Transiciones compartidas de membresía e invitación entre los dos servicios.

Las invitaciones viven en la BD de negocio, pero el servicio de profesionales
(``:8080``) necesita listarlas y aceptarlas para la bandeja de Commander. Esta
lógica la comparten:

- las rutas públicas de negocio (``routes/establecimientos.py``),
- las rutas internas (``routes/internal.py``) y
- el transporte ``direct`` del cliente interno (``app.internal.py``).

``app.internal`` importa estas funciones de forma diferida dentro de sus métodos
(para evitar un ciclo): este módulo, en cambio, importa ``get_camareros_internal``
arriba porque el dominio depende del cliente interno para resolver perfiles.
"""

import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.orm import Session

from app.db import NegocioSessionLocal
from app.errors import (
    CAMARERO_NOT_FOUND,
    DATA_ORIGIN_MISMATCH,
    INVITACION_EXPIRED,
    INVITACION_NOT_FOUND,
    INVITACION_UNAUTHORIZED,
    INVITACION_USED,
    MEMBERSHIP_DUPLICATE,
    ApiError,
)
from app.internal import get_camareros_internal
from app.models import (
    Establecimiento,
    Invitacion,
    InvitacionEstado,
    Membresia,
    MembresiaEstado,
    MembresiaRol,
)


def _add_or_reactivate_membership(
    db: Session,
    establecimiento: Establecimiento,
    camarero_id: uuid.UUID,
    rol: str,
    allow_existing: bool = False,
) -> Membresia:
    waiter = get_camareros_internal().perfil(camarero_id)
    if waiter is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=CAMARERO_NOT_FOUND,
            detail="Camarero no encontrado",
        )
    if waiter["data_origin"] != establecimiento.data_origin.value:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=DATA_ORIGIN_MISMATCH,
            detail="El camarero y el establecimiento deben tener la misma procedencia",
        )
    existing = (
        db.query(Membresia)
        .filter_by(establecimiento_id=establecimiento.id, camarero_id=camarero_id)
        .one_or_none()
    )
    if existing is not None:
        if existing.estado == MembresiaEstado.revocada:
            existing.estado = MembresiaEstado.activa
            existing.revocada_en = None
            existing.rol = MembresiaRol(rol)
            return existing
        if allow_existing:
            return existing
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=MEMBERSHIP_DUPLICATE,
            detail="El camarero ya pertenece a este establecimiento",
        )
    membership = Membresia(
        establecimiento_id=establecimiento.id,
        camarero_id=camarero_id,
        rol=MembresiaRol(rol),
        estado=MembresiaEstado.activa,
    )
    db.add(membership)
    return membership


def _finalizar_aceptacion(db: Session, invitation: Invitacion, camarero_id: uuid.UUID) -> Membresia:
    """Valida la invitación y materializa la membresía; commitea la sesión."""
    perfil = get_camareros_internal().perfil(camarero_id)
    if perfil is None or perfil["email"].lower() != invitation.email_objetivo:
        raise ApiError(
            status_code=status.HTTP_403_FORBIDDEN,
            code=INVITACION_UNAUTHORIZED,
            detail="La invitación no corresponde a este camarero",
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
    establecimiento = db.get(Establecimiento, invitation.establecimiento_id)
    membership = _add_or_reactivate_membership(
        db, establecimiento, camarero_id, invitation.rol.value, allow_existing=True
    )
    invitation.estado = InvitacionEstado.aceptada
    invitation.aceptada_en = now
    db.commit()
    db.refresh(membership)
    return membership


def _membresia_dict(membership: Membresia) -> dict:
    return {
        "id": str(membership.id),
        "establecimiento_id": str(membership.establecimiento_id),
        "camarero_id": str(membership.camarero_id),
        "rol": membership.rol.value,
        "estado": membership.estado.value,
    }


def listar_invitaciones(camarero_id: uuid.UUID) -> list[dict]:
    """Invitaciones dirigidas al email del camarero, con nombre del establecimiento."""
    perfil = get_camareros_internal().perfil(camarero_id)
    if perfil is None:
        return []
    email = perfil["email"].lower()
    with NegocioSessionLocal() as db:
        rows = (
            db.query(Invitacion, Establecimiento.nombre)
            .join(Establecimiento, Establecimiento.id == Invitacion.establecimiento_id)
            .filter(Invitacion.email_objetivo == email)
            .order_by(Invitacion.creada_en.desc())
            .all()
        )
    return [
        {
            "id": str(inv.id),
            "establecimiento_id": str(inv.establecimiento_id),
            "establecimiento_nombre": nombre,
            "rol": inv.rol.value,
            "estado": inv.estado.value,
            "expira_en": inv.expira_en.isoformat(),
            "creada_en": inv.creada_en.isoformat(),
        }
        for inv, nombre in rows
    ]


def aceptar_invitacion_por_id(camarero_id: uuid.UUID, invitacion_id: uuid.UUID) -> dict:
    """Acepta una invitación por id (sin token) verificando que sea del camarero."""
    with NegocioSessionLocal() as db:
        invitation = db.get(Invitacion, invitacion_id)
        if invitation is None:
            raise ApiError(
                status_code=status.HTTP_404_NOT_FOUND,
                code=INVITACION_NOT_FOUND,
                detail="Invitación no encontrada",
            )
        membership = _finalizar_aceptacion(db, invitation, camarero_id)
        return {
            "invitacion_id": str(invitation.id),
            "membresia": _membresia_dict(membership),
        }
