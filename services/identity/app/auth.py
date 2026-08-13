import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Camarero, Credencial, CredencialEstado
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


def create_access_token(camarero_id: uuid.UUID, secret: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(camarero_id),
        "iat": now,
        "exp": now + timedelta(days=_ttl_days()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sesión inválido o caducado",
        )
    camarero_id = decode_access_token(credentials.credentials, get_session_secret(db))
    if camarero_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sesión inválido o caducado",
        )
    camarero = db.get(Camarero, camarero_id)
    if camarero is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sesión inválido o caducado",
        )
    return camarero
