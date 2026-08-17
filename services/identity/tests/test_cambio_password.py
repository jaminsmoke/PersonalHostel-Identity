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


def _email() -> str:
    return f"cambiopass-{uuid.uuid4()}@example.com"


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


def _login(email: str, password: str = "pass-12345678"):
    return client.post(
        "/v1/auth/login",
        json={"email": email, "password": password},
    )


def _auth(email: str) -> dict:
    resp = _login(email)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _cambiar(headers: dict, password_actual: str, password_nueva: str):
    return client.post(
        "/v1/camareros/me/password",
        headers=headers,
        json={"password_actual": password_actual, "password_nueva": password_nueva},
    )


def test_cambiar_password_ok(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = _cambiar(headers, "pass-12345678", "nueva-87654321")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cambiada"

    # Login con la contraseña nueva funciona; con la antigua ya no.
    assert _login(email, "nueva-87654321").status_code == 200
    assert _login(email, "pass-12345678").status_code == 401


def test_cambiar_password_actual_incorrecta(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = _cambiar(headers, "incorrecta", "nueva-87654321")
    assert resp.status_code == 401
    assert resp.json()["code"] == "identity.password_incorrecta"

    # La contraseña original sigue valiendo.
    assert _login(email, "pass-12345678").status_code == 200


def test_cambiar_password_nueva_corta(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = _cambiar(headers, "pass-12345678", "corta")
    assert resp.status_code == 422


def test_cambiar_password_sin_token(db_ready):
    resp = client.post(
        "/v1/camareros/me/password",
        json={"password_actual": "pass-12345678", "password_nueva": "nueva-87654321"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "identity.token_invalido"