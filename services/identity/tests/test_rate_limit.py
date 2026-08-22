"""Cuotas de abuso (Redis): 429 por bucket y 503 si el contador cae."""

from __future__ import annotations

import uuid
from io import BytesIO

import pytest
import redis
from PIL import Image
from sqlalchemy import text
from tests.test_cfc_inbox import _mesa, _negocio, _producto

from app.rate_limit import DETAIL_LIMITED, DETAIL_UNAVAILABLE, reset_redis_client


@pytest.fixture(scope="module")
def db_ready():
    from app.db import CamareroSessionLocal, NegocioSessionLocal

    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _isolate(monkeypatch, **limits: str) -> None:
    reset_redis_client()
    monkeypatch.setenv("RATE_LIMIT_PREFIX", f"t-{uuid.uuid4()}")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP", "10000")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_EMAIL", "10000")
    monkeypatch.setenv("RATE_LIMIT_REGISTRO_IP", "10000")
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_CUENTA", "10000")
    monkeypatch.setenv("RATE_LIMIT_CFC_MESA", "10000")
    for name, value in limits.items():
        monkeypatch.setenv(name, value)


def _png() -> bytes:
    img = Image.new("RGB", (64, 64), (10, 20, 30))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _registro_payload(email: str) -> dict:
    return {
        "nombre": "Ana",
        "apellidos": "García",
        "email": email,
        "password": "pass-12345678",
    }


def test_login_por_ip_devuelve_429(db_ready, camarero_client, monkeypatch):
    _isolate(monkeypatch, RATE_LIMIT_LOGIN_IP="2")
    monkeypatch.setattr("app.rate_limit.client_ip", lambda request: "203.0.113.10")
    body = {"email": f"lim-{uuid.uuid4()}@example.com", "password": "pass-12345678"}
    assert camarero_client.post("/v1/auth/login", json=body).status_code == 401
    assert camarero_client.post("/v1/auth/login", json=body).status_code == 401
    third = camarero_client.post("/v1/auth/login", json=body)
    assert third.status_code == 429
    assert third.json()["code"] == "identity.rate_limited"
    assert third.json()["detail"] == DETAIL_LIMITED
    assert int(third.headers["Retry-After"]) >= 1


def test_login_email_independiente_de_ip(db_ready, camarero_client, monkeypatch):
    _isolate(monkeypatch, RATE_LIMIT_LOGIN_EMAIL="2", RATE_LIMIT_LOGIN_IP="1000")
    monkeypatch.setattr("app.rate_limit.client_ip", lambda request: "203.0.113.11")
    email_a = f"a-{uuid.uuid4()}@example.com"
    email_b = f"b-{uuid.uuid4()}@example.com"
    for _ in range(2):
        assert (
            camarero_client.post(
                "/v1/auth/login", json={"email": email_a, "password": "x"}
            ).status_code
            == 401
        )
    blocked = camarero_client.post("/v1/auth/login", json={"email": email_a, "password": "x"})
    assert blocked.status_code == 429
    other = camarero_client.post("/v1/auth/login", json={"email": email_b, "password": "x"})
    assert other.status_code == 401


def test_registro_por_ip_devuelve_429(db_ready, camarero_client, monkeypatch):
    _isolate(monkeypatch, RATE_LIMIT_REGISTRO_IP="2")
    monkeypatch.setattr("app.rate_limit.client_ip", lambda request: "203.0.113.12")
    assert (
        camarero_client.post(
            "/v1/camareros/registro",
            json=_registro_payload(f"r1-{uuid.uuid4()}@example.com"),
        ).status_code
        == 201
    )
    assert (
        camarero_client.post(
            "/v1/camareros/registro",
            json=_registro_payload(f"r2-{uuid.uuid4()}@example.com"),
        ).status_code
        == 201
    )
    third = camarero_client.post(
        "/v1/camareros/registro",
        json=_registro_payload(f"r3-{uuid.uuid4()}@example.com"),
    )
    assert third.status_code == 429
    assert third.json()["code"] == "identity.rate_limited"


def test_foto_por_cuenta_devuelve_429(db_ready, camarero_client, monkeypatch):
    _isolate(monkeypatch, RATE_LIMIT_UPLOAD_CUENTA="1")
    email = f"foto-rl-{uuid.uuid4()}@example.com"
    assert (
        camarero_client.post("/v1/camareros/registro", json=_registro_payload(email)).status_code
        == 201
    )
    login = camarero_client.post(
        "/v1/auth/login", json={"email": email, "password": "pass-12345678"}
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    first = camarero_client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("foto.png", _png(), "image/png")},
    )
    assert first.status_code == 200
    second = camarero_client.post(
        "/v1/camareros/me/foto",
        headers=headers,
        files={"foto": ("foto.png", _png(), "image/png")},
    )
    assert second.status_code == 429
    assert second.json()["code"] == "identity.rate_limited"


def test_cfc_por_mesa_no_comparte_ip(db_ready, negocio_client, monkeypatch):
    _isolate(monkeypatch, RATE_LIMIT_CFC_MESA="1")
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    listed = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={
            "mesas": [
                {"mesa_uuid": str(uuid.uuid4()), "etiqueta": "A"},
                {"mesa_uuid": str(uuid.uuid4()), "etiqueta": "B"},
            ]
        },
    )
    assert listed.status_code == 200
    tokens = {row["etiqueta"]: row["url_publica"].rsplit("/m/", 1)[1] for row in listed.json()}
    abierta = negocio_client.post(
        f"/v1/establecimientos/{est_id}/cfc/jornada/abrir",
        headers=headers,
    )
    assert abierta.status_code == 200
    ok_a = negocio_client.post(
        f"/v1/cfc/mesa/{tokens['A']}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert ok_a.status_code in (200, 201)
    blocked = negocio_client.post(
        f"/v1/cfc/mesa/{tokens['A']}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert blocked.status_code == 429
    ok_b = negocio_client.post(
        f"/v1/cfc/mesa/{tokens['B']}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert ok_b.status_code in (200, 201)


def test_cfc_replay_idempotente_no_consume_cuota(db_ready, negocio_client, monkeypatch):
    _isolate(monkeypatch, RATE_LIMIT_CFC_MESA="1")
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    _, token = _mesa(negocio_client, est_id, headers)
    assert (
        negocio_client.post(
            f"/v1/establecimientos/{est_id}/cfc/jornada/abrir",
            headers=headers,
        ).status_code
        == 200
    )
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "lineas": [{"producto_id": producto_id, "cantidad": 1}],
    }
    first = negocio_client.post(f"/v1/cfc/mesa/{token}/pedidos", json=body)
    assert first.status_code in (200, 201)
    replay = negocio_client.post(f"/v1/cfc/mesa/{token}/pedidos", json=body)
    assert replay.status_code in (200, 201)
    assert replay.json()["id"] == first.json()["id"]


def test_redis_caido_503_en_login_y_health_sigue(db_ready, camarero_client, monkeypatch):
    _isolate(monkeypatch)

    def boom() -> redis.Redis:
        raise redis.ConnectionError("down")

    monkeypatch.setattr("app.rate_limit.get_redis", boom)
    resp = camarero_client.post(
        "/v1/auth/login",
        json={"email": f"down-{uuid.uuid4()}@example.com", "password": "pass-12345678"},
    )
    assert resp.status_code == 503
    assert resp.json()["code"] == "identity.rate_limit_unavailable"
    assert resp.json()["detail"] == DETAIL_UNAVAILABLE
    assert camarero_client.get("/health").status_code == 200
    assert camarero_client.get("/v1/meta").status_code == 200


def test_openapi_login_documenta_429(camarero_client):
    spec = camarero_client.get("/openapi.json").json()
    login = spec["paths"]["/v1/auth/login"]["post"]["responses"]
    assert "429" in login
    assert "503" in login


def test_openapi_cfc_documenta_429(negocio_client):
    spec = negocio_client.get("/openapi.json").json()
    pedidos = spec["paths"]["/v1/cfc/mesa/{token}/pedidos"]["post"]["responses"]
    assert "429" in pedidos
    assert "503" in pedidos
