import base64
import hashlib
import os
import secrets
import uuid

import nacl.secret
import nacl.signing
from sqlalchemy.orm import Session

from app.models import AppConfig

QR_PREFIX = "phid1"
CONFIG_KEY_SIGNING = "qr_signing_key_ed25519"
CONFIG_KEY_SESSION = "session_secret"

SIGNING_KEY_ENV = "QR_SIGNING_KEY"
SESSION_SECRET_ENV = "SESSION_SECRET"


def _load_signing_key(encoded: str) -> nacl.signing.SigningKey:
    return nacl.signing.SigningKey(base64.b64decode(encoded))


def get_signing_key(db: Session) -> nacl.signing.SigningKey:
    env = os.environ.get(SIGNING_KEY_ENV)
    if env:
        return _load_signing_key(env)

    row = db.get(AppConfig, CONFIG_KEY_SIGNING)
    if row is not None:
        return _load_signing_key(row.valor)

    sk = nacl.signing.SigningKey.generate()
    db.add(
        AppConfig(
            clave=CONFIG_KEY_SIGNING,
            valor=base64.b64encode(bytes(sk)).decode("ascii"),
        )
    )
    db.commit()
    return sk


def get_verify_key(db: Session) -> nacl.signing.VerifyKey:
    return get_signing_key(db).verify_key


def get_session_secret(db: Session) -> str:
    env = os.environ.get(SESSION_SECRET_ENV)
    if env:
        return env

    row = db.get(AppConfig, CONFIG_KEY_SESSION)
    if row is not None:
        return row.valor

    secret = secrets.token_urlsafe(48)
    db.add(AppConfig(clave=CONFIG_KEY_SESSION, valor=secret))
    db.commit()
    return secret


def get_session_secret_env() -> str:
    """Secreto de sesión compartido entre los dos servicios.

    El servicio de negocio no tiene tabla ``app_config`` propia; depende del
    secreto inyectado por la orquestación (Docker Compose / VPS).
    """
    secret = os.environ.get(SESSION_SECRET_ENV)
    if not secret:
        raise RuntimeError(f"{SESSION_SECRET_ENV} debe estar definido")
    return secret


def build_qr_payload(
    camarero_id: uuid.UUID,
    credencial_id: uuid.UUID,
    signing_key: nacl.signing.SigningKey,
) -> str:
    message = f"{QR_PREFIX}:{camarero_id}:{credencial_id}".encode("utf-8")
    signature = signing_key.sign(message).signature
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{QR_PREFIX}:{camarero_id}:{credencial_id}:{sig_b64}"


def verify_qr_payload(payload: str, verify_key: nacl.signing.VerifyKey) -> bool:
    return parse_and_verify_qr_payload(payload, verify_key) is not None


def parse_and_verify_qr_payload(
    payload: str, verify_key: nacl.signing.VerifyKey
) -> tuple[uuid.UUID, uuid.UUID] | None:
    try:
        parts = payload.split(":")
        if len(parts) != 4:
            return None
        prefix, camarero_id, credencial_id, sig_b64 = parts
        if prefix != QR_PREFIX:
            return None
        signature = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        message = f"{prefix}:{camarero_id}:{credencial_id}".encode("utf-8")
        verify_key.verify(message, signature)
        return uuid.UUID(camarero_id), uuid.UUID(credencial_id)
    except Exception:
        return None


def qr_public_key_payload(db: Session) -> dict[str, str]:
    verify_key = get_verify_key(db)
    return {
        "algorithm": "Ed25519",
        "key_id": "ed25519-v1",
        "public_key": base64.urlsafe_b64encode(bytes(verify_key)).rstrip(b"=").decode("ascii"),
        "qr_prefix": QR_PREFIX,
        "format": "phid1:<camarero_id>:<credencial_id>:<firma>",
    }


def protect_invitation_token(token: str, session_secret: str) -> str:
    key = hashlib.sha256(session_secret.encode("utf-8")).digest()
    box = nacl.secret.SecretBox(key)
    encrypted = box.encrypt(token.encode("utf-8"))
    return base64.urlsafe_b64encode(encrypted).rstrip(b"=").decode("ascii")


def unprotect_invitation_token(value: str, session_secret: str) -> str:
    key = hashlib.sha256(session_secret.encode("utf-8")).digest()
    box = nacl.secret.SecretBox(key)
    encrypted = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    return box.decrypt(encrypted).decode("utf-8")
