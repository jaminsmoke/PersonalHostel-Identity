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

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    from app.db import SessionLocal

    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"revocar-{uuid.uuid4()}@example.com"


def _crear(email: str, password: str = "pass-12345678") -> dict:
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Luis",
            "apellidos": "Pérez",
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
    assert resp.status_code == 200
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_renovar_cambia_qr_mantiene_id(db_ready):
    email = _email()
    reg = _crear(email)
    login = _login(email)
    token = login["token"]
    assert login["qr"] == reg["qr"]

    resp = client.post("/v1/camareros/me/renovar", headers=_auth(token))
    assert resp.status_code == 200
    nuevo_qr = resp.json()["qr"]
    assert nuevo_qr != reg["qr"]
    assert nuevo_qr.startswith("phid1:")
    assert len(nuevo_qr.split(":")) == 4

    login2 = _login(email)
    assert login2["camarero"]["id"] == reg["id"]
    assert login2["qr"] == nuevo_qr
    assert login2["qr"] != reg["qr"]


def test_renovar_qr_verifica(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]
    qr = client.post("/v1/camareros/me/renovar", headers=_auth(token)).json()["qr"]
    from app.db import SessionLocal

    with SessionLocal() as session:
        vk = get_verify_key(session)
    assert verify_qr_payload(qr, vk)


def test_revocar_me_qr_409(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]

    resp = client.post("/v1/camareros/me/revocar", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "revocada"

    me_qr = client.get("/v1/camareros/me/qr", headers=_auth(token))
    assert me_qr.status_code == 409
    assert "Clave revocada" in me_qr.json()["detail"]


def test_revocar_login_409(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]
    client.post("/v1/camareros/me/revocar", headers=_auth(token))

    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert resp.status_code == 409
    assert "Clave revocada" in resp.json()["detail"]


def test_renovar_tras_revocar(db_ready):
    email = _email()
    reg = _crear(email)
    token = _login(email)["token"]
    client.post("/v1/camareros/me/revocar", headers=_auth(token))

    resp = client.post("/v1/camareros/me/renovar", headers=_auth(token))
    assert resp.status_code == 200
    nuevo_qr = resp.json()["qr"]
    assert nuevo_qr != reg["qr"]

    login = _login(email)
    assert login["qr"] == nuevo_qr
    assert login["camarero"]["id"] == reg["id"]


def test_revocar_sin_activa_409(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]
    assert client.post("/v1/camareros/me/revocar", headers=_auth(token)).status_code == 200
    resp = client.post("/v1/camareros/me/revocar", headers=_auth(token))
    assert resp.status_code == 409
    assert "Clave revocada" in resp.json()["detail"]


def test_revocar_con_motivo(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]
    resp = client.post(
        "/v1/camareros/me/revocar",
        headers=_auth(token),
        json={"motivo": "tablet perdido"},
    )
    assert resp.status_code == 200

    from app.db import SessionLocal
    from app.models import Credencial, CredencialEstado

    with SessionLocal() as session:
        creds = (
            session.query(Credencial)
            .filter_by(estado=CredencialEstado.revocada)
            .order_by(Credencial.revocada_en.desc())
            .all()
        )
        assert any(c.motivo_revocacion == "tablet perdido" for c in creds)


def test_verify_formato_antiguo_false(db_ready):
    email = _email()
    reg = _crear(email)
    partes = reg["qr"].split(":")
    assert len(partes) == 4
    antiguo = f"{partes[0]}:{partes[1]}:{partes[3]}"
    from app.db import SessionLocal

    with SessionLocal() as session:
        vk = get_verify_key(session)
    assert not verify_qr_payload(antiguo, vk)


def test_renovar_sin_token_401(db_ready):
    resp = client.post("/v1/camareros/me/renovar")
    assert resp.status_code == 401


def test_revocar_sin_token_401(db_ready):
    resp = client.post("/v1/camareros/me/revocar")
    assert resp.status_code == 401
