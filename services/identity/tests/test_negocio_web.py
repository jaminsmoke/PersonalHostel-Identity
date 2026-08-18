import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.db import NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _crear_negocio_establecimiento(negocio_client, nombre="Local Web") -> tuple[dict, str]:
    email = _email("web-negocio")
    reg = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Negocio Web",
            "email": email,
            "password": "negocio-12345678",
            "tipo_establecimiento": "restaurante",
        },
    )
    assert reg.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login", json={"email": email, "password": "negocio-12345678"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    est = negocio_client.post("/v1/establecimientos", headers=headers, json={"nombre": nombre})
    assert est.status_code == 201
    return headers, est.json()["id"]


def _crear_enlace(negocio_client, headers, est_id, tipo, slug) -> dict:
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": tipo, "slug": slug},
    )
    assert resp.status_code == 201
    return resp.json()


def _crear_producto(negocio_client, est_id, headers, nombre, categoria, precio):
    body = {
        "operation_id": str(uuid.uuid4()),
        "device_id": "web-test-01",
        "aggregate_type": "producto",
        "aggregate_id": str(uuid.uuid4()),
        "action": "crear",
        "base_revision": 0,
        "base_snapshot": None,
        "client_created_at": datetime.now(UTC).isoformat(),
        "payload": {
            "nombre": nombre,
            "categoria": categoria,
            "destino": "barra",
            "precio_centimos": precio,
            "moneda": "EUR",
            "disponible": True,
        },
    }
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/sync/operaciones",
        headers=headers,
        json=body,
    )
    assert resp.status_code == 200, resp.text


def test_web_negocio_resuelve_slug_de_ficha_y_devuelve_ficha_mas_carta(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-ficha-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)
    _crear_producto(negocio_client, est_id, headers, "Café solo", "Cafés", 150)
    _crear_producto(negocio_client, est_id, headers, "Tortilla", "Cocina", 450)

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["nombre"] == "Local Web"
    assert body["tipo_establecimiento"] == "restaurante"
    assert body["logo_url"] is None
    assert body["organizacion_nombre"] == "Negocio Web"
    assert body["categorias"] == [
        {
            "nombre": "Cafés",
            "productos": [{"nombre": "Café solo", "precio_centimos": 150, "moneda": "EUR"}],
        },
        {
            "nombre": "Cocina",
            "productos": [{"nombre": "Tortilla", "precio_centimos": 450, "moneda": "EUR"}],
        },
    ]
    assert "email" not in body
    assert resp.headers["cache-control"] == "public, max-age=300"


def test_web_negocio_resuelve_tambien_slug_de_carta(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-carta-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "carta", slug)

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 200
    assert resp.json()["establecimiento_id"] == est_id
    assert resp.json()["categorias"] == []


def test_web_negocio_logo_url_y_servido_por_cualquier_slug(db_ready, negocio_client):
    from io import BytesIO

    from PIL import Image

    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug_ficha = f"web-logo-f-{uuid.uuid4().hex[:8]}"
    slug_carta = f"web-logo-c-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug_ficha)
    _crear_enlace(negocio_client, headers, est_id, "carta", slug_carta)

    img = Image.new("RGB", (300, 200), (200, 80, 40))
    buf = BytesIO()
    img.save(buf, format="PNG")
    upload = negocio_client.post(
        "/v1/auth/negocio/me/logo",
        headers=headers,
        files={"logo": ("logo.png", buf.getvalue(), "image/png")},
    )
    assert upload.status_code == 200

    body = negocio_client.get("/v1/negocio/web", params={"slug": slug_ficha}).json()
    assert body["logo_url"] == f"/v1/negocio/web/logo?slug={slug_ficha}"

    for slug in (slug_ficha, slug_carta):
        logo = negocio_client.get("/v1/negocio/web/logo", params={"slug": slug})
        assert logo.status_code == 200
        assert logo.headers["content-type"] == "image/webp"
        assert logo.headers["cache-control"] == "public, max-age=86400"
        assert Image.open(BytesIO(logo.content)).format == "WEBP"


def test_web_negocio_slug_inexistente_404(db_ready, negocio_client):
    resp = negocio_client.get("/v1/negocio/web", params={"slug": "no-existe"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.enlace_no_encontrado"


def test_web_negocio_revocada_410(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"web-revocada-{uuid.uuid4().hex[:8]}"
    enlace = _crear_enlace(negocio_client, headers, est_id, "ficha_negocio", slug)

    revoke = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces/{enlace['id']}/revocar",
        headers=headers,
    )
    assert revoke.status_code == 200

    resp = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert resp.status_code == 410
    assert resp.json()["code"] == "identity.enlace_revocado"
