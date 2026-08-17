import uuid

import pytest
from sqlalchemy import text

from app.db import NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"cambiopass-{uuid.uuid4()}@example.com"


def _crear_negocio(negocio_client, email: str) -> dict:
    resp = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Negocio Cambio Password",
            "email": email,
            "password": "negocio-12345678",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _login(negocio_client, email: str, password: str = "negocio-12345678"):
    return negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": password},
    )


def _auth(negocio_client, email: str) -> dict:
    resp = _login(negocio_client, email)
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _cambiar(negocio_client, headers: dict, password_actual: str, password_nueva: str):
    return negocio_client.post(
        "/v1/auth/negocio/me/password",
        headers=headers,
        json={"password_actual": password_actual, "password_nueva": password_nueva},
    )


def test_cambiar_password_negocio_ok(db_ready, negocio_client):
    email = _email()
    _crear_negocio(negocio_client, email)
    headers = _auth(negocio_client, email)

    resp = _cambiar(negocio_client, headers, "negocio-12345678", "nueva-87654321")
    assert resp.status_code == 200
    assert resp.json()["status"] == "cambiada"

    assert _login(negocio_client, email, "nueva-87654321").status_code == 200
    assert _login(negocio_client, email, "negocio-12345678").status_code == 401


def test_cambiar_password_negocio_actual_incorrecta(db_ready, negocio_client):
    email = _email()
    _crear_negocio(negocio_client, email)
    headers = _auth(negocio_client, email)

    resp = _cambiar(negocio_client, headers, "incorrecta", "nueva-87654321")
    assert resp.status_code == 401
    assert resp.json()["code"] == "identity.negocio_credenciales_invalidas"

    assert _login(negocio_client, email, "negocio-12345678").status_code == 200


def test_cambiar_password_negocio_nueva_corta(db_ready, negocio_client):
    email = _email()
    _crear_negocio(negocio_client, email)
    headers = _auth(negocio_client, email)

    resp = _cambiar(negocio_client, headers, "negocio-12345678", "corta")
    assert resp.status_code == 422


def test_cambiar_password_negocio_sin_token(db_ready, negocio_client):
    resp = negocio_client.post(
        "/v1/auth/negocio/me/password",
        json={"password_actual": "negocio-12345678", "password_nueva": "nueva-87654321"},
    )
    assert resp.status_code == 401