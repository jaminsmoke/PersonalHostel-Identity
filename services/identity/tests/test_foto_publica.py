import uuid
from io import BytesIO
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from PIL import Image
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
    return f"fotopub-{uuid.uuid4()}@example.com"


def _crear(email: str) -> dict:
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


def _auth(email: str) -> dict:
    resp = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _png_bytes() -> bytes:
    img = Image.new("RGB", (300, 200), (20, 120, 240))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _subir_foto(headers: dict) -> None:
    resp = client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("foto.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200


def _hacer_visible(headers: dict) -> None:
    resp = client.put(
        "/v1/camareros/me/visibilidad",
        headers=headers,
        json={"foto": True},
    )
    assert resp.status_code == 200
    assert resp.json()["foto"] is True


def test_ficha_incluye_foto_url_si_visible(db_ready):
    email = _email()
    reg = _crear(email)
    headers = _auth(email)
    _subir_foto(headers)
    _hacer_visible(headers)

    ficha = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert ficha.status_code == 200
    assert ficha.json()["foto_url"] == f"/v1/camareros/ficha/foto?qr={quote(reg['qr'])}"

    foto = client.get("/v1/camareros/ficha/foto", params={"qr": reg["qr"]})
    assert foto.status_code == 200
    assert foto.headers["content-type"] == "image/webp"
    assert "public" in foto.headers["cache-control"]
    assert foto.headers["etag"]
    img = Image.open(BytesIO(foto.content))
    assert img.format == "WEBP"
    assert img.size == (256, 256)


def test_foto_no_visible_sin_opt_in(db_ready):
    email = _email()
    reg = _crear(email)
    headers = _auth(email)
    _subir_foto(headers)  # foto=false por defecto

    ficha = client.get("/v1/camareros/ficha", params={"qr": reg["qr"]})
    assert ficha.status_code == 200
    assert "foto_url" not in ficha.json()

    foto = client.get("/v1/camareros/ficha/foto", params={"qr": reg["qr"]})
    assert foto.status_code == 404
    assert foto.json()["code"] == "identity.foto_inexistente"


def test_foto_publica_sin_foto_404(db_ready):
    email = _email()
    reg = _crear(email)
    headers = _auth(email)
    _hacer_visible(headers)  # visible pero sin foto subida

    foto = client.get("/v1/camareros/ficha/foto", params={"qr": reg["qr"]})
    assert foto.status_code == 404
    assert foto.json()["code"] == "identity.foto_inexistente"


def test_foto_publica_qr_invalido_422(db_ready):
    resp = client.get("/v1/camareros/ficha/foto", params={"qr": "phid1:basura"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.qr_invalido"


def test_foto_publica_qr_revocado_409(db_ready):
    email = _email()
    reg = _crear(email)
    headers = _auth(email)
    _subir_foto(headers)
    _hacer_visible(headers)
    client.post("/v1/camareros/me/revocar", headers=headers)

    foto = client.get("/v1/camareros/ficha/foto", params={"qr": reg["qr"]})
    assert foto.status_code == 409
    assert foto.json()["code"] == "identity.credencial_inactiva"
