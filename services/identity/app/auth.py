import os
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_camarero_db, get_negocio_db
from app.errors import (
    INVALID_TOKEN,
    NEGOCIO_INVALID_TOKEN,
    ApiError,
)
from app.internal import get_camareros_internal
from app.models import Camarero, Credencial, CredencialEstado, CuentaNegocio
from app.security import get_session_secret, get_session_secret_env

TTL_DAYS_ENV = "SESSION_TTL_DAYS"
DEFAULT_TTL_DAYS = 30

ALGORITHM = "HS256"

_hasher = PasswordHasher()
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, TypeError, ValueError):
        return False


def _ttl_days() -> int:
    raw = os.environ.get(TTL_DAYS_ENV)
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return DEFAULT_TTL_DAYS


def create_access_token(subject_id: uuid.UUID, secret: str, subject_type: str = "camarero") -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject_id),
        "typ": subject_type,
        "iat": now,
        "exp": now + timedelta(days=_ttl_days()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(
    token: str, secret: str, expected_type: str = "camarero"
) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        token_type = payload.get("typ", "camarero")
        if token_type != expected_type:
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def get_credencial_activa(db: Session, camarero_id: uuid.UUID) -> Credencial | None:
    return (
        db.query(Credencial)
        .filter_by(camarero_id=camarero_id, estado=CredencialEstado.activa)
        .order_by(Credencial.creada_en.desc())
        .first()
    )


def _bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )
    return credentials.credentials


# ── Servicio de profesionales ──────────────────────────────────────────────


def get_current_camarero(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_camarero_db),
) -> Camarero:
    token = _bearer_token(credentials)
    camarero_id = decode_access_token(token, get_session_secret(db), expected_type="camarero")
    if camarero_id is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )
    camarero = db.get(Camarero, camarero_id)
    if camarero is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )
    return camarero


def get_current_camarero_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_camarero_db),
) -> Camarero | None:
    """Resuelve el camarero si hay bearer válido; si no, devuelve None (magic-link)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    camarero_id = decode_access_token(
        credentials.credentials, get_session_secret(db), expected_type="camarero"
    )
    if camarero_id is None:
        return None
    return db.get(Camarero, camarero_id)


# ── Servicio de negocio ────────────────────────────────────────────────────


def create_business_access_token(cuenta_id: uuid.UUID, secret: str) -> str:
    return create_access_token(cuenta_id, secret, subject_type="negocio")


def get_current_cuenta_negocio(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_negocio_db),
) -> CuentaNegocio:
    token = _bearer_token(credentials)
    cuenta_id = decode_access_token(token, get_session_secret_env(), expected_type="negocio")
    cuenta = db.get(CuentaNegocio, cuenta_id) if cuenta_id else None
    if cuenta is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=NEGOCIO_INVALID_TOKEN,
            detail="Token de cuenta de negocio inválido o caducado",
        )
    return cuenta


def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_negocio_db),
) -> tuple[str, uuid.UUID]:
    """Resuelve un token de profesional o de cuenta de negocio.

    Devuelve ``(tipo, subject_id)``. El camarero no se carga (vive en la otra
    BD): solo se valida su existencia mediante el cliente interno.
    """
    token = _bearer_token(credentials)
    try:
        payload = jwt.decode(token, get_session_secret_env(), algorithms=[ALGORITHM])
        subject_id = uuid.UUID(payload["sub"])
        subject_type = payload.get("typ", "camarero")
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        ) from exc

    if subject_type == "negocio":
        if db.get(CuentaNegocio, subject_id) is None:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code=INVALID_TOKEN,
                detail="Token de sesión inválido o caducado",
            )
    else:
        subject_type = "camarero"
        if get_camareros_internal().perfil(subject_id) is None:
            raise ApiError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code=INVALID_TOKEN,
                detail="Token de sesión inválido o caducado",
            )
    return subject_type, subject_id


def get_current_camarero_id_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID | None:
    """Resuelve el ``camarero_id`` del bearer (servicio de negocio) o ``None``.

    El negocio no carga el ORM del camarero (vive en la otra BD); devuelve solo
    el id para cruzar con ``membresias`` o para consultar el perfil interno.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return decode_access_token(
        credentials.credentials, get_session_secret_env(), expected_type="camarero"
    )
