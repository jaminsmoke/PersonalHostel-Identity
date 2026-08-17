import uuid
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import text

from app.db import NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _crear_negocio(negocio_client) -> tuple[str, str]:
    email = _email("ficha-negocio")
    resp = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Negocio Ficha",
            "email": email,
            "password": "negocio-12345678",
            "tipo_establecimiento": "bar",
        },
    )
    assert resp.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return resp.json()["id"], login.json()["token"]


def _crear_establecimiento(negocio_client, token: str, nombre: str = "Local Ficha") -> str:
    resp = negocio_client.post(
        "/v1/establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": nombre},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _crear_enlace(negocio_client, token, est_id, tipo, slug) -> dict:
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers={"Authorization": f"Bearer {token}"},
        json={"tipo": tipo, "slug": slug},
    )
    assert resp.status_code == 201
    return resp.json()


def _png_bytes(color=(20, 120, 200)) -> bytes:
    img = Image.new("RGB", (300, 200), color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ficha_publica_devuelve_campos_publicos(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    est_id = _crear_establecimiento(negocio_client, token)
    slug = f"ficha-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, token, est_id, "ficha_negocio", slug)

    resp = negocio_client.get("/v1/negocio/ficha", params={"slug": slug})
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["nombre"] == "Local Ficha"
    assert body["tipo_establecimiento"] == "bar"
    assert body["logo_url"] is None  # sin logo aún
    assert body["organizacion_nombre"] == "Negocio Ficha"
    assert "establecimientos" not in body
    assert "email" not in body
    assert resp.headers["cache-control"] == "public, max-age=300"


def test_ficha_no_filtra_otros_establecimientos_de_la_organizacion(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    primero = _crear_establecimiento(negocio_client, token, "Local Público")
    _crear_establecimiento(negocio_client, token, "Local Privado")
    slug = f"ficha-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, token, primero, "ficha_negocio", slug)

    body = negocio_client.get("/v1/negocio/ficha", params={"slug": slug}).json()
    assert body["establecimiento_id"] == primero
    assert body["nombre"] == "Local Público"
    assert "Local Privado" not in str(body)


def test_ficha_incluye_logo_url_y_sirve_logo_publico(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    est_id = _crear_establecimiento(negocio_client, token)
    slug = f"ficha-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, token, est_id, "ficha_negocio", slug)

    upload = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers={"Authorization": f"Bearer {token}"},
        files={"logo": ("logo.png", _png_bytes(), "image/png")},
    )
    assert upload.status_code == 200

    resp = negocio_client.get("/v1/negocio/ficha", params={"slug": slug})
    assert resp.status_code == 200
    assert resp.json()["logo_url"] == f"/v1/negocio/ficha/logo?slug={slug}"

    logo = negocio_client.get("/v1/negocio/ficha/logo", params={"slug": slug})
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/webp"
    assert logo.headers["cache-control"] == "public, max-age=86400"
    assert logo.headers["etag"]
    img = Image.open(BytesIO(logo.content))
    assert img.format == "WEBP"


def test_enlace_carta_no_sirve_ficha(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    est_id = _crear_establecimiento(negocio_client, token)
    slug = f"carta-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, token, est_id, "carta", slug)

    resp = negocio_client.get("/v1/negocio/ficha", params={"slug": slug})
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.enlace_no_encontrado"


def test_ficha_slug_inexistente_404(db_ready, negocio_client):
    resp = negocio_client.get("/v1/negocio/ficha", params={"slug": "no-existe"})
    assert resp.status_code == 404


def test_ficha_revocada_410(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    est_id = _crear_establecimiento(negocio_client, token)
    slug = f"ficha-{uuid.uuid4().hex[:8]}"
    enlace = _crear_enlace(negocio_client, token, est_id, "ficha_negocio", slug)

    revoke = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces/{enlace['id']}/revocar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revoke.status_code == 200

    resp = negocio_client.get("/v1/negocio/ficha", params={"slug": slug})
    assert resp.status_code == 410
    assert resp.json()["code"] == "identity.enlace_revocado"
