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

RUTAS = [
    "/v1/camareros/registro",
    "/v1/auth/login",
    "/v1/camareros/me",
    "/v1/camareros/me/qr",
    "/v1/camareros/me/renovar",
    "/v1/camareros/me/revocar",
]


@pytest.fixture(scope="module")
def db_ready():
    from app.db import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def test_openapi_documenta_rutas_y_version():
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert spec["info"]["version"] == "0.2.0"
    paths = spec["paths"]
    for ruta in RUTAS:
        assert ruta in paths, f"Falta {ruta} en el spec"
    schemas = spec["components"]["schemas"]
    assert "ErrorResponse" in schemas


def test_openapi_es_determinista():
    assert app.openapi() == app.openapi()


def test_validacion_devuelve_code():
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": "no-es-email",
            "password": "pass-12345678",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "identity.validation_error"
    assert isinstance(body["detail"], list)


def test_login_inexistente_devuelve_code(db_ready):
    resp = client.post(
        "/v1/auth/login",
        json={"email": f"no-existe-{uuid.uuid4()}@example.com", "password": "pass-12345678"},
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["code"] == "identity.credenciales_invalidas"
    assert "incorrectos" in body["detail"]
