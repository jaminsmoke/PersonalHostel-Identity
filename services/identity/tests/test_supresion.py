import os
import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity",
)

from app.main import app  # noqa: E402
from app.storage import get_foto_storage  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    from app.db import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"supresion-{uuid.uuid4()}@example.com"


def _crear(email: str, password: str = "pass-12345678") -> dict:
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": email,
            "password": password,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _login(email: str, password: str = "pass-12345678") -> dict:
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )
    return resp


def _auth(email: str) -> dict:
    resp = _login(email)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _png_bytes(color=(200, 30, 30)) -> bytes:
    img = Image.new("RGB", (300, 200), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_suprimir_cuenta_ok(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = client.request(
        "DELETE", "/v1/camareros/me", headers=headers, json={"password": "pass-12345678"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "borrada"

    # El token viejo ya no resuelve → 401
    assert client.get("/v1/camareros/me", headers=headers).status_code == 401
    # El login ya no encuentra la cuenta → 401
    assert _login(email).status_code == 401


def test_suprimir_borra_foto_y_credenciales(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("foto.png", _png_bytes(), "image/png")},
    )

    from app.db import SessionLocal
    from app.models import Camarero, Credencial

    with SessionLocal() as session:
        cam = session.query(Camarero).filter_by(email=email).one()
        foto_clave = cam.foto_clave
        assert foto_clave is not None
        assert session.query(Credencial).filter_by(camarero_id=cam.id).count() >= 1

    resp = client.request(
        "DELETE", "/v1/camareros/me", headers=headers, json={"password": "pass-12345678"}
    )
    assert resp.status_code == 200

    # La foto desaparece del volumen
    assert get_foto_storage().leer(foto_clave) is None

    # La cuenta y sus credenciales desaparecen de la DB
    with SessionLocal() as session:
        assert session.query(Camarero).filter_by(email=email).one_or_none() is None


def test_suprimir_password_incorrecta(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = client.request(
        "DELETE", "/v1/camareros/me", headers=headers, json={"password": "incorrecta"}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "identity.password_incorrecta"

    # La cuenta sigue intacta: login sigue funcionando
    assert _login(email).status_code == 200


def test_suprimir_sin_token_401(db_ready):
    resp = client.request("DELETE", "/v1/camareros/me", json={"password": "pass-12345678"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "identity.token_invalido"
