import os
import uuid
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("FICHA_URL_BASE", "http://ficha.test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity",
)

from app.main import app  # noqa: E402
from app.security import get_verify_key, verify_qr_payload  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    from app.db import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"fichaurl-{uuid.uuid4()}@example.com"


def _registro(email: str) -> dict:
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _token(email: str) -> str:
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert resp.status_code == 200
    return resp.json()["token"]


def _expected_url(qr: str) -> str:
    return f"http://ficha.test/camareros?qr={quote(qr)}"


def test_registro_incluye_ficha_url(db_ready):
    reg = _registro(_email())
    assert reg["ficha_url"] == _expected_url(reg["qr"])


def test_login_incluye_ficha_url(db_ready):
    email = _email()
    reg = _registro(email)
    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    assert login.json()["ficha_url"] == _expected_url(reg["qr"])


def test_me_qr_incluye_ficha_url(db_ready):
    email = _email()
    reg = _registro(email)
    token = _token(email)
    resp = client.get(
        "/v1/camareros/me/qr",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["qr"] == reg["qr"]
    assert body["ficha_url"] == _expected_url(reg["qr"])


def test_verificar_qr_acepta_forma_url(db_ready):
    reg = _registro(_email())
    url = reg["ficha_url"]
    from app.db import SessionLocal

    with SessionLocal() as session:
        vk = get_verify_key(session)
    assert verify_qr_payload(reg["qr"], vk)
    assert verify_qr_payload(url, vk)


def test_ficha_acepta_qr_como_url(db_ready):
    reg = _registro(_email())
    url = reg["ficha_url"]
    resp = client.get("/v1/camareros/ficha", params={"qr": url})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Ana"
