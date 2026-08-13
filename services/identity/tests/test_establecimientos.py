import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity",
)

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _crear_camarero() -> tuple[str, str, str]:
    email = _email("org-camarero")
    response = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert response.status_code == 201
    data = response.json()
    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    return data["id"], email, login.json()["token"]


def _crear_negocio(vinculado: str | None = None) -> tuple[str, str]:
    email = _email("org-negocio")
    payload = {
        "nombre_mostrar": "Restaurante Prueba",
        "email": email,
        "password": "negocio-12345678",
    }
    if vinculado:
        payload["camarero_vinculado_id"] = vinculado
    response = client.post("/v1/auth/negocio/registro", json=payload)
    assert response.status_code == 201
    data = response.json()
    login = client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return data["id"], login.json()["token"]


def test_negocio_crea_establecimiento_y_membresia(db_ready):
    camarero_id, _, camarero_token = _crear_camarero()
    cuenta_id, negocio_token = _crear_negocio(camarero_id)
    negocio_headers = {"Authorization": f"Bearer {negocio_token}"}
    camarero_headers = {"Authorization": f"Bearer {camarero_token}"}

    created = client.post(
        "/v1/establecimientos",
        headers=negocio_headers,
        json={"nombre": "Casa de Prueba"},
    )
    assert created.status_code == 201
    establecimiento = created.json()
    establecimiento_id = establecimiento["id"]
    assert establecimiento["cuenta_negocio_id"] == cuenta_id

    listed = client.get("/v1/establecimientos/mios", headers=negocio_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == establecimiento_id

    member = client.get(
        f"/v1/establecimientos/{establecimiento_id}/miembros",
        headers=negocio_headers,
    )
    assert member.status_code == 200
    assert member.json()[0]["camarero_id"] == camarero_id
    assert member.json()[0]["rol"] == "dueno"

    mine = client.get(
        "/v1/camareros/me/establecimientos", headers=camarero_headers
    )
    assert mine.status_code == 200
    assert mine.json()[0]["id"] == establecimiento_id
    assert mine.json()[0]["rol"] == "dueno"


def test_tokens_de_profesional_y_negocio_no_se_intercambian(db_ready):
    camarero_id, _, camarero_token = _crear_camarero()
    _, negocio_token = _crear_negocio(camarero_id)

    negocio_on_camarero = client.get(
        "/v1/camareros/me",
        headers={"Authorization": f"Bearer {negocio_token}"},
    )
    camarero_on_negocio = client.get(
        "/v1/establecimientos/mios",
        headers={"Authorization": f"Bearer {camarero_token}"},
    )
    assert negocio_on_camarero.status_code == 401
    assert camarero_on_negocio.status_code == 401


def test_revocar_membresia_y_borrado_independiente(db_ready):
    camarero_id, _, camarero_token = _crear_camarero()
    _, negocio_token = _crear_negocio()
    negocio_headers = {"Authorization": f"Bearer {negocio_token}"}
    camarero_headers = {"Authorization": f"Bearer {camarero_token}"}
    created = client.post(
        "/v1/establecimientos",
        headers=negocio_headers,
        json={"nombre": "Local Independiente"},
    )
    establecimiento_id = created.json()["id"]
    added = client.post(
        f"/v1/establecimientos/{establecimiento_id}/miembros",
        headers=negocio_headers,
        json={"camarero_id": camarero_id, "rol": "staff"},
    )
    assert added.status_code == 201

    revoked = client.delete(
        f"/v1/establecimientos/{establecimiento_id}/miembros/{camarero_id}",
        headers=negocio_headers,
    )
    assert revoked.status_code == 200
    assert revoked.json()["estado"] == "revocada"
    assert client.get(
        f"/v1/establecimientos/{establecimiento_id}", headers=camarero_headers
    ).status_code == 403

    deleted = client.request(
        "DELETE",
        "/v1/auth/negocio/me",
        headers=negocio_headers,
        json={"password": "negocio-12345678"},
    )
    assert deleted.status_code == 200
    assert client.get(
        "/v1/camareros/me", headers=camarero_headers
    ).status_code == 200
