import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import (
    INVALID_TOKEN,
    NEGOCIO_INVALID_TOKEN,
    ApiError,
)
from app.models import Camarero, CuentaNegocio, Credencial, CredencialEstado
from app.security import get_session_secret

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
    now = datetime.now(timezone.utc)
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


def get_current_camarero(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Camarero:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )
    camarero_id = decode_access_token(
        credentials.credentials, get_session_secret(db), expected_type="camarero"
    )
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


def create_business_access_token(cuenta_id: uuid.UUID, secret: str) -> str:
    return create_access_token(cuenta_id, secret, subject_type="negocio")


def get_current_cuenta_negocio(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CuentaNegocio:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=NEGOCIO_INVALID_TOKEN,
            detail="Token de cuenta de negocio inválido o caducado",
        )
    cuenta_id = decode_access_token(
        credentials.credentials, get_session_secret(db), expected_type="negocio"
    )
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
    db: Session = Depends(get_db),
) -> tuple[str, Camarero | CuentaNegocio]:
    """Resuelve un token de profesional o de cuenta de negocio."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_session_secret(db),
            algorithms=[ALGORITHM],
        )
        subject_id = uuid.UUID(payload["sub"])
        subject_type = payload.get("typ", "camarero")
    except (jwt.PyJWTError, KeyError, ValueError):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )

    if subject_type == "negocio":
        actor = db.get(CuentaNegocio, subject_id)
    else:
        subject_type = "camarero"
        actor = db.get(Camarero, subject_id)
    if actor is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_TOKEN,
            detail="Token de sesión inválido o caducado",
        )
    return subject_type, actor
