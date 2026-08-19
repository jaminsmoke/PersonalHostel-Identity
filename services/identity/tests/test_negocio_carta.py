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


def _crear_negocio_establecimiento(negocio_client) -> tuple[dict, str]:
    email = _email("carta-negocio")
    reg = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={"nombre_mostrar": "Negocio Carta", "email": email, "password": "negocio-12345678"},
    )
    assert reg.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login", json={"email": email, "password": "negocio-12345678"}
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    est = negocio_client.post("/v1/establecimientos", headers=headers, json={"nombre": "Bar Carta"})
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


def _producto(
    nombre: str,
    categoria: str,
    precio: int,
    disponible: bool = True,
) -> dict:
    body = {
        "operation_id": str(uuid.uuid4()),
        "device_id": "bar-tablet-01",
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
            "disponible": disponible,
        },
    }
    return body


def _post_producto(negocio_client, est_id, headers, body):
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/sync/operaciones",
        headers=headers,
        json=body,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_carta_publica_agrupada_con_precio(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"carta-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "carta", slug)

    _post_producto(negocio_client, est_id, headers, _producto("Café solo", "Cafés", 150))
    _post_producto(negocio_client, est_id, headers, _producto("Café doble", "Cafés", 200))
    _post_producto(negocio_client, est_id, headers, _producto("Tortilla", "Cocina", 450))
    _post_producto(
        negocio_client, est_id, headers, _producto("Agotado", "Cafés", 120, disponible=False)
    )

    resp = negocio_client.get("/v1/negocio/carta", params={"slug": slug})
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["nombre"] == "Bar Carta"
    assert resp.headers["cache-control"] == "public, max-age=300"

    categorias = {c["nombre"]: c["productos"] for c in body["categorias"]}
    assert list(categorias.keys()) == ["Cafés", "Cocina"]
    assert [p["nombre"] for p in categorias["Cafés"]] == ["Café doble", "Café solo"]
    assert categorias["Cafés"][0]["precio_centimos"] == 200
    assert categorias["Cafés"][0]["moneda"] == "EUR"
    assert [p["nombre"] for p in categorias["Cocina"]] == ["Tortilla"]
    # no disponible excluido
    assert "Agotado" not in [p["nombre"] for p in categorias["Cafés"]]
    # destino público para tabs Cocina/Barra; sin revisión ni procedencia
    assert categorias["Cafés"][0]["destino"] == "barra"
    assert "revision" not in categorias["Cafés"][0]
    assert "data_origin" not in categorias["Cafés"][0]


def test_carta_enlace_ficha_negocio_no_sirve(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"ficha-{uuid.uuid4().hex[:8]}"
    _crear_enlace(negocio_client, headers, est_id, "web", slug)

    resp = negocio_client.get("/v1/negocio/carta", params={"slug": slug})
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.enlace_no_encontrado"


def test_carta_slug_inexistente_404(db_ready, negocio_client):
    resp = negocio_client.get("/v1/negocio/carta", params={"slug": "no-existe"})
    assert resp.status_code == 404


def test_carta_revocada_410(db_ready, negocio_client):
    headers, est_id = _crear_negocio_establecimiento(negocio_client)
    slug = f"carta-{uuid.uuid4().hex[:8]}"
    enlace = _crear_enlace(negocio_client, headers, est_id, "carta", slug)

    revoke = negocio_client.post(
        f"/v1/establecimientos/{est_id}/enlaces/{enlace['id']}/revocar",
        headers=headers,
    )
    assert revoke.status_code == 200

    resp = negocio_client.get("/v1/negocio/carta", params={"slug": slug})
    assert resp.status_code == 410
    assert resp.json()["code"] == "identity.enlace_revocado"
