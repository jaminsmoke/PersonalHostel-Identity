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
from app.security import get_verify_key, verify_qr_payload  # noqa: E402

from app.db import SessionLocal  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"prueba-{uuid.uuid4()}@example.com"


def test_registro_ok(db_ready):
    email = _email()
    resp = client.post(
        "/v1/camareros/registro",
        json={"nombre": "Ana", "apellidos": "García", "email": email},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    uuid.UUID(body["id"])
    assert body["qr"].startswith("phid1:")

    with SessionLocal() as session:
        from app.models import Camarero, Credencial

        cam = session.get(Camarero, uuid.UUID(body["id"]))
        assert cam is not None
        assert cam.email == email
        creds = session.query(Credencial).filter_by(camarero_id=cam.id).all()
        assert len(creds) == 1
        assert creds[0].estado.value == "activa"


def test_registro_qr_verifica(db_ready):
    email = _email()
    resp = client.post(
        "/v1/camareros/registro",
        json={"nombre": "Luis", "apellidos": "Pérez", "email": email},
    )
    assert resp.status_code == 201
    qr = resp.json()["qr"]
    with SessionLocal() as session:
        vk = get_verify_key(session)
    assert verify_qr_payload(qr, vk)


def test_registro_email_duplicado(db_ready):
    email = _email()
    data = {"nombre": "Ana", "apellidos": "García", "email": email}
    assert client.post("/v1/camareros/registro", json=data).status_code == 201
    resp = client.post("/v1/camareros/registro", json=data)
    assert resp.status_code == 409
    assert "Ya existe" in resp.json()["detail"]


def test_registro_email_invalido(db_ready):
    resp = client.post(
        "/v1/camareros/registro",
        json={"nombre": "Ana", "apellidos": "García", "email": "no-es-email"},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, list)
    assert "email" in " ".join(detail)


def test_qr_rechaza_firma_manipulada(db_ready):
    email = _email()
    resp = client.post(
        "/v1/camareros/registro",
        json={"nombre": "Carlos", "apellidos": "Ruiz", "email": email},
    )
    qr = resp.json()["qr"]
    with SessionLocal() as session:
        vk = get_verify_key(session)

    partes = qr.split(":")
    sig = partes[2]
    primer_char = "A" if sig[0] != "A" else "B"
    manipulada = f"{partes[0]}:{partes[1]}:{primer_char}{sig[1:]}"
    assert not verify_qr_payload(manipulada, vk)
