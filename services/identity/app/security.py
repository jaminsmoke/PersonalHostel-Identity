import base64
import os
import uuid

import nacl.signing
from sqlalchemy.orm import Session

from app.models import AppConfig

QR_PREFIX = "phid1"
CONFIG_KEY_SIGNING = "qr_signing_key_ed25519"

SIGNING_KEY_ENV = "QR_SIGNING_KEY"


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


def build_qr_payload(camarero_id: uuid.UUID, signing_key: nacl.signing.SigningKey) -> str:
    message = f"{QR_PREFIX}:{camarero_id}".encode("utf-8")
    signature = signing_key.sign(message).signature
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{QR_PREFIX}:{camarero_id}:{sig_b64}"


def verify_qr_payload(payload: str, verify_key: nacl.signing.VerifyKey) -> bool:
    try:
        prefix, camarero_id, sig_b64 = payload.split(":")
        if prefix != QR_PREFIX:
            return False
        signature = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
        message = f"{prefix}:{camarero_id}".encode("utf-8")
        verify_key.verify(message, signature)
        return True
    except Exception:
        return False
