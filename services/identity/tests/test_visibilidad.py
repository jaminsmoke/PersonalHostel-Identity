import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    from app.db import CamareroSessionLocal

    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"visibilidad-{uuid.uuid4()}@example.com"


def _crear(
    email: str,
    telefono: str | None = None,
    direccion: str | None = None,
    ciudad: str | None = None,
) -> dict:
    if telefono is None:
        # el teléfono es único en BD; genera uno distinto por cuenta de test
        telefono = f"+34{uuid.uuid4().hex[:9]}"
    payload = {
        "nombre": "Marta",
        "apellidos": "Sánchez",
        "email": email,
        "password": "pass-12345678",
        "nick": "Marti",
        "telefono": telefono,
    }
    if direccion is not None:
        payload["direccion"] = direccion
    if ciudad is not None:
        payload["ciudad"] = ciudad
    resp = client.post("/v1/camareros/registro", json=payload)
    assert resp.status_code == 201
    return resp.json()


def _login(email: str) -> dict:
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert resp.status_code == 200
    return resp.json()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_visibilidad_default(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]
    resp = client.get("/v1/camareros/me/visibilidad", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "nombre": True,
        "apellidos": True,
        "nick": True,
        "email": False,
        "telefono": False,
        "direccion": False,
        "ciudad": False,
        "foto": False,
    }


def test_visibilidad_update_parcial(db_ready):
    email = _email()
    _crear(email)
    token = _login(email)["token"]
    resp = client.put(
        "/v1/camareros/me/visibilidad",
        headers=_auth(token),
        json={"email": True, "telefono": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] is True
    assert body["telefono"] is True
    # el resto queda como estaba
    assert body["nombre"] is True
    assert body["nick"] is True
    assert body["foto"] is False

    # persiste entre peticiones
    again = client.get("/v1/camareros/me/visibilidad", headers=_auth(token))
    assert again.json()["email"] is True


def test_visibilidad_sin_token_401(db_ready):
    assert client.get("/v1/camareros/me/visibilidad").status_code == 401
    assert client.put("/v1/camareros/me/visibilidad", json={"email": True}).status_code == 401


def test_ficha_publica_por_qr_solo_campos_visibles(db_ready):
    email = _email()
    reg = _crear(email)
    resp = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["camarero_id"] == reg["id"]
    assert body["nombre"] == "Marta"
    assert body["apellidos"] == "Sánchez"
    assert body["nick"] == "Marti"
    # sensibles no visibles por defecto
    assert "email" not in body
    assert "telefono" not in body
    assert "foto" not in body


def test_ficha_publica_muestra_email_si_visible(db_ready):
    email = _email()
    telefono = f"+34{uuid.uuid4().hex[:9]}"
    reg = _crear(email, telefono=telefono)
    token = _login(email)["token"]
    client.put(
        "/v1/camareros/me/visibilidad",
        headers=_auth(token),
        json={"email": True, "telefono": True},
    )
    resp = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert body["telefono"] == telefono


def test_ficha_qr_invalido_422(db_ready):
    resp = client.get("/v1/camareros/ficha", params={"qr": "phid1:basura"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.qr_invalido"


def test_ficha_qr_revocado_409(db_ready):
    email = _email()
    reg = _crear(email)
    token = _login(email)["token"]
    client.post("/v1/camareros/me/revocar", headers=_auth(token))
    resp = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert resp.status_code == 409
    assert resp.json()["code"] == "identity.credencial_inactiva"


def test_ficha_sin_nick_omite_campo(db_ready):
    email = _email()
    resp = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Luis",
            "apellidos": "Pérez",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert resp.status_code == 201
    ficha = client.get("/v1/camareros/ficha", params={"qr": resp.json()["qr"]})
    assert ficha.status_code == 200
    assert "nick" not in ficha.json()


def test_ficha_publica_no_expone_direccion_ciudad_por_defecto(db_ready):
    email = _email()
    reg = _crear(email, direccion="Calle Mayor 1", ciudad="Madrid")
    resp = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert resp.status_code == 200
    body = resp.json()
    assert "direccion" not in body
    assert "ciudad" not in body


def test_ficha_publica_muestra_direccion_ciudad_si_visible(db_ready):
    email = _email()
    reg = _crear(email, direccion="Calle Mayor 1", ciudad="Madrid")
    token = _login(email)["token"]
    client.put(
        "/v1/camareros/me/visibilidad",
        headers=_auth(token),
        json={"direccion": True, "ciudad": True},
    )
    resp = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["direccion"] == "Calle Mayor 1"
    assert body["ciudad"] == "Madrid"
