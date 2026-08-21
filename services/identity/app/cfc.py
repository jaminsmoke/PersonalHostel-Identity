"""Admisión CFC: jornada de local, heartbeat y horario.

No confundir con las jornadas de oficio del camarero (BD profesionales).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.errors import (
    MESA_TOKEN_INVALIDO,
    MESA_TOKEN_REVOCADO,
    ApiError,
)
from app.models import EnlaceEstado, Establecimiento, JornadaCfc, MesaCfc, PedidoCfc
from app.routes.negocio_web import _abierto_ahora

HEARTBEAT_STALE = timedelta(seconds=90)
PEDIDO_PENDIENTE = "pendiente"
PEDIDO_ACEPTADO = "aceptado"
PEDIDO_RECHAZADO = "rechazado"
PEDIDO_EXPIRADO = "expirado"
NO_STORE = {"Cache-Control": "no-store"}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mesa_activa_por_token(db: Session, token: str) -> MesaCfc:
    mesa = db.query(MesaCfc).filter_by(token_hash=hash_token(token)).one_or_none()
    if mesa is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=MESA_TOKEN_INVALIDO,
            detail="El código de esta mesa no es válido",
            headers=NO_STORE,
        )
    if mesa.estado != EnlaceEstado.activo.value:
        raise ApiError(
            status_code=status.HTTP_410_GONE,
            code=MESA_TOKEN_REVOCADO,
            detail="El código de esta mesa ya no vale",
            headers=NO_STORE,
        )
    return mesa


def jornada_abierta(db: Session, establecimiento_id: uuid.UUID) -> JornadaCfc | None:
    return (
        db.query(JornadaCfc)
        .filter_by(establecimiento_id=establecimiento_id)
        .filter(JornadaCfc.cerrada_en.is_(None))
        .one_or_none()
    )


def heartbeat_fresco(jornada: JornadaCfc, ahora: datetime | None = None) -> bool:
    ahora = ahora or datetime.now(UTC)
    visto = jornada.ultimo_heartbeat
    if visto.tzinfo is None:
        visto = visto.replace(tzinfo=UTC)
    return ahora - visto <= HEARTBEAT_STALE


def horario_abierto(db: Session, establecimiento: Establecimiento) -> bool:
    perfil = establecimiento.perfil
    tz = (perfil.tz if perfil is not None and perfil.tz else None) or "Europe/Madrid"
    info = _abierto_ahora(db, establecimiento, SimpleNamespace(tz=tz))
    return bool(info and info.get("abierto"))


def admision_cfc(db: Session, establecimiento: Establecimiento) -> tuple[bool, bool]:
    """``(admite_pedidos, bar_en_linea)`` según jornada + heartbeat + horario."""
    jornada = jornada_abierta(db, establecimiento.id)
    if jornada is None:
        return False, False
    en_linea = heartbeat_fresco(jornada)
    if en_linea:
        return True, True
    if horario_abierto(db, establecimiento):
        return True, False
    return False, False


def siguiente_seq(db: Session, establecimiento_id: uuid.UUID) -> int:
    actual = (
        db.query(func.coalesce(func.max(PedidoCfc.seq), 0))
        .filter(PedidoCfc.establecimiento_id == establecimiento_id)
        .scalar()
    )
    return int(actual) + 1
