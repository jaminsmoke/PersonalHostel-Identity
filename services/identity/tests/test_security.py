import base64
import uuid

import nacl.signing
import pytest

from app.db import CamareroSessionLocal
from app.models import AppConfig
from app.security import (
    CONFIG_KEY_SESSION,
    CONFIG_KEY_SIGNING,
    SESSION_SECRET_ENV,
    SIGNING_KEY_ENV,
    get_session_secret,
    get_session_secret_env,
    get_signing_key,
    parse_and_verify_qr_payload,
)


@pytest.fixture
def clean_app_config():
    with CamareroSessionLocal() as session:
        for clave in (CONFIG_KEY_SIGNING, CONFIG_KEY_SESSION):
            row = session.get(AppConfig, clave)
            if row is not None:
                session.delete(row)
        session.commit()
        yield session


def test_get_signing_key_crea_fila_si_falta(monkeypatch, clean_app_config):
    monkeypatch.delenv(SIGNING_KEY_ENV, raising=False)
    clave = get_signing_key(clean_app_config)
    assert isinstance(clave, nacl.signing.SigningKey)
    guardada = clean_app_config.get(AppConfig, CONFIG_KEY_SIGNING)
    assert guardada is not None
    restaurada = nacl.signing.SigningKey(base64.b64decode(guardada.valor))
    assert bytes(restaurada) == bytes(clave)


def test_get_signing_key_recupera_fila_existente(monkeypatch, clean_app_config):
    monkeypatch.delenv(SIGNING_KEY_ENV, raising=False)
    semilla = nacl.signing.SigningKey.generate()
    clean_app_config.add(
        AppConfig(
            clave=CONFIG_KEY_SIGNING,
            valor=base64.b64encode(bytes(semilla)).decode("ascii"),
        )
    )
    clean_app_config.commit()
    clave = get_signing_key(clean_app_config)
    assert bytes(clave) == bytes(semilla)


def test_get_session_secret_crea_fila_y_reusa(monkeypatch, clean_app_config):
    monkeypatch.delenv(SESSION_SECRET_ENV, raising=False)
    secreto = get_session_secret(clean_app_config)
    assert isinstance(secreto, str) and len(secreto) > 20
    guardada = clean_app_config.get(AppConfig, CONFIG_KEY_SESSION)
    assert guardada is not None
    assert guardada.valor == secreto
    assert get_session_secret(clean_app_config) == secreto


def test_get_session_secret_env_requiere_variable(monkeypatch):
    monkeypatch.delenv(SESSION_SECRET_ENV, raising=False)
    with pytest.raises(RuntimeError):
        get_session_secret_env()


def test_verify_qr_rechaza_prefijo_no_soportado():
    payload = f"otro:{uuid.uuid4()}:{uuid.uuid4()}:ZmlybWE="
    assert (
        parse_and_verify_qr_payload(payload, nacl.signing.SigningKey.generate().verify_key) is None
    )
