import uuid
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

from app.main import app  # noqa: E402
from app.storage import get_foto_storage  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    from app.db import CamareroSessionLocal

    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email() -> str:
    return f"foto-{uuid.uuid4()}@example.com"


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


def _png_bytes(color=(200, 30, 30)) -> bytes:
    img = Image.new("RGB", (300, 200), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_sin_foto_404(db_ready):
    email = _email()
    _crear(email)
    resp = client.get("/v1/camareros/me/foto", headers=_auth(email))
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.foto_inexistente"


def test_subir_servir_y_me(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("foto.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200
    assert resp.json()["foto_url"] == "/v1/camareros/me/foto"

    foto = client.get("/v1/camareros/me/foto", headers=headers)
    assert foto.status_code == 200
    assert foto.headers["content-type"] == "image/webp"
    assert foto.headers["etag"]
    img = Image.open(BytesIO(foto.content))
    assert img.format == "WEBP"
    assert img.size == (256, 256)

    me = client.get("/v1/camareros/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["foto_url"] == "/v1/camareros/me/foto"


def test_reemplazo_borra_anterior(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("a.png", _png_bytes((255, 0, 0)), "image/png")},
    )

    from app.db import CamareroSessionLocal
    from app.models import Camarero

    with CamareroSessionLocal() as session:
        cam = session.query(Camarero).filter_by(email=email).one()
        old_clave = cam.foto_clave
    assert old_clave is not None

    client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("b.png", _png_bytes((0, 0, 255)), "image/png")},
    )

    with CamareroSessionLocal() as session:
        cam = session.query(Camarero).filter_by(email=email).one()
        assert cam.foto_clave != old_clave

    assert get_foto_storage().leer(old_clave) is None


def test_borrar_foto(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("a.png", _png_bytes(), "image/png")},
    )

    resp = client.delete("/v1/camareros/me/foto", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["foto_url"] is None

    me = client.get("/v1/camareros/me", headers=headers)
    assert me.json()["foto_url"] is None
    assert client.get("/v1/camareros/me/foto", headers=headers).status_code == 404


def test_foto_invalida_formato(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    resp = client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("no-imagen.txt", b"esto no es una imagen", "text/plain")},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.foto_invalida"


def test_foto_demasiado_grande(db_ready):
    email = _email()
    _crear(email)
    headers = _auth(email)

    big = b"x" * (2 * 1024 * 1024 + 1)
    resp = client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("grande.bin", big, "application/octet-stream")},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "identity.foto_invalida"
    assert "tamaño" in resp.json()["detail"]
