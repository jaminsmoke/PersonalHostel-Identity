"""La ficha-credencial HTTP se retiró: la lectura pública es GET /v1/negocio/web."""

import uuid

import pytest
from sqlalchemy import text

from app.db import NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def test_ficha_http_ya_no_existe(db_ready, negocio_client):
    resp = negocio_client.get("/v1/negocio/ficha", params={"slug": "cualquier"})
    assert resp.status_code == 404
    logo = negocio_client.get("/v1/negocio/ficha/logo", params={"slug": "cualquier"})
    assert logo.status_code == 404


def test_alias_ficha_negocio_crea_web_y_sirve_por_web(db_ready, negocio_client):
    email = f"ficha-alias-{uuid.uuid4()}@example.com"
    assert (
        negocio_client.post(
            "/v1/auth/negocio/registro",
            json={
                "nombre_mostrar": "Negocio Alias",
                "email": email,
                "password": "negocio-12345678",
            },
        ).status_code
        == 201
    )
    token = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    est_id = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Local Alias"}
    ).json()["id"]
    slug = f"alias-{uuid.uuid4().hex[:8]}"
    enlace = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces",
        headers=headers,
        json={"tipo": "ficha_negocio", "slug": slug},
    )
    assert enlace.status_code == 201
    assert enlace.json()["tipo"] == "web"
    web = negocio_client.get("/v1/negocio/web", params={"slug": slug})
    assert web.status_code == 200
    assert web.json()["establecimiento_id"] == est_id
