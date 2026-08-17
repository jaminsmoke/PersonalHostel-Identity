import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity",
)

from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    from app.db import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _crear(email: str, password: str = "pass-12345678") -> dict:
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Pepe",
            "apellidos": "López",
            "email": email,
            "password": password,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _email() -> str:
    return f"login-{uuid.uuid4()}@example.com"


def test_login_devuelve_misma_identidad_y_qr(db_ready):
    email = _email()
    reg = _crear(email)
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["camarero"]["id"] == reg["id"]
    assert body["camarero"]["email"] == email
    assert body["camarero"]["nick"] is None
    assert body["qr"] == reg["qr"]


def test_login_incluye_nick_si_se_registro(db_ready):
    email = _email()
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Pepe",
            "apellidos": "López",
            "email": email,
            "password": "pass-12345678",
            "nick": "Pepi",
        },
    )
    assert resp.status_code == 201
    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    assert login.json()["camarero"]["nick"] == "Pepi"


def test_patch_me_actualiza_nick(db_ready):
    email = _email()
    _crear(email)
    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    token = login.json()["token"]
    resp = client.patch(
        "/v1/camareros/me",
        json={"nick": "Pepi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["nick"] == "Pepi"
    me = client.get("/v1/camareros/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["nick"] == "Pepi"


def test_patch_me_actualiza_direccion_ciudad(db_ready):
    email = _email()
    _crear(email)
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    ).json()["token"]
    resp = client.patch(
        "/v1/camareros/me",
        json={"direccion": "Calle Mayor 1", "ciudad": "Madrid"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["direccion"] == "Calle Mayor 1"
    assert resp.json()["ciudad"] == "Madrid"
    me = client.get("/v1/camareros/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["direccion"] == "Calle Mayor 1"
    assert me.json()["ciudad"] == "Madrid"


def test_patch_me_vacio_422(db_ready):
    email = _email()
    _crear(email)
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    ).json()["token"]
    resp = client.patch(
        "/v1/camareros/me",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_login_password_incorrecta_401(db_ready):
    email = _email()
    _crear(email)
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-incorrecta"},
    )
    assert resp.status_code == 401
    assert "incorrectos" in resp.json()["detail"]


def test_login_email_inexistente_401(db_ready):
    resp = client.post(
        "/v1/auth/login",
        json={"email": "no-existe@example.com", "password": "pass-12345678"},
    )
    assert resp.status_code == 401
    assert "incorrectos" in resp.json()["detail"]


def test_login_camarero_sin_password_401(db_ready):
    email = _email()
    reg = _crear(email)
    from app.db import SessionLocal
    from app.models import Camarero

    with SessionLocal() as session:
        cam = session.get(Camarero, uuid.UUID(reg["id"]))
        cam.password_hash = None
        session.commit()
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert resp.status_code == 401


def test_me_con_token_ok(db_ready):
    email = _email()
    reg = _crear(email)
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    ).json()["token"]
    resp = client.get("/v1/camareros/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == reg["id"]
    assert body["email"] == email


def test_me_sin_token_401(db_ready):
    resp = client.get("/v1/camareros/me")
    assert resp.status_code == 401


def test_me_token_invalido_401(db_ready):
    resp = client.get(
        "/v1/camareros/me",
        headers={"Authorization": "Bearer token-invalido"},
    )
    assert resp.status_code == 401
    assert "inválido" in resp.json()["detail"]


def test_me_qr_igual_al_registro(db_ready):
    email = _email()
    reg = _crear(email)
    token = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    ).json()["token"]
    resp = client.get("/v1/camareros/me/qr", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["qr"] == reg["qr"]


def test_registro_sin_password_422(db_ready):
    resp = client.post(
        "/v1/camareros/registro",
        json={"nombre": "Ana", "apellidos": "García", "email": _email()},
    )
    assert resp.status_code == 422
    detail = " ".join(resp.json()["detail"])
    assert "contraseña" in detail


def test_registro_password_corta_422(db_ready):
    resp = client.post(
        "/v1/camareros/registro",
        json={"nombre": "Ana", "apellidos": "García", "email": _email(), "password": "corta"},
    )
    assert resp.status_code == 422


def test_password_no_se_devuelve(db_ready):
    email = _email()
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Pepe",
            "apellidos": "López",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert resp.status_code == 201
    assert "password" not in resp.json()
    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert "password" not in login.json()
