import json
import logging
import os
import uuid

import pytest
from sqlalchemy import text

from app.db import NegocioSessionLocal
from app.observability import access_logger, redact_access_path


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _crear_negocio(negocio_client, prefix: str = "mesa-cfc") -> tuple[str, str]:
    email = _email(prefix)
    resp = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Negocio Mesas CFC",
            "email": email,
            "password": "negocio-12345678",
        },
    )
    assert resp.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return resp.json()["id"], login.json()["token"]


def _crear_establecimiento(negocio_client, token: str, nombre: str = "Casa CFC") -> str:
    resp = negocio_client.post(
        "/v1/establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": nombre},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _token_de_url(url: str) -> str:
    return url.rsplit("/m/", 1)[1]


def test_redact_access_path_sustituye_el_secreto():
    assert redact_access_path("/v1/cfc/mesa/abcXYZ-_123") == "/v1/cfc/mesa/*"
    assert redact_access_path("/v1/establecimientos/x/mesas-cfc") == (
        "/v1/establecimientos/x/mesas-cfc"
    )


def test_put_emite_tokens_y_es_idempotente(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token, "El Local")
    mesa_a = str(uuid.uuid4())
    mesa_b = str(uuid.uuid4())

    first = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={
            "mesas": [
                {"mesa_uuid": mesa_a, "etiqueta": "B1"},
                {"mesa_uuid": mesa_b, "etiqueta": "T3"},
            ]
        },
    )
    assert first.status_code == 200
    body = first.json()
    assert {row["etiqueta"] for row in body} == {"B1", "T3"}
    urls = {row["etiqueta"]: row["url_publica"] for row in body}
    assert urls["B1"].startswith(f"{os.environ['WEB_CFC_URL_BASE']}/m/")
    assert urls["T3"].startswith(f"{os.environ['WEB_CFC_URL_BASE']}/m/")

    second = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={
            "mesas": [
                {"mesa_uuid": mesa_a, "etiqueta": "B1"},
                {"mesa_uuid": mesa_b, "etiqueta": "T3"},
            ]
        },
    )
    assert second.status_code == 200
    assert {row["url_publica"] for row in second.json()} == set(urls.values())


def test_cambiar_etiqueta_no_rota_el_token(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)
    mesa_uuid = str(uuid.uuid4())
    first = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    ).json()
    renamed = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "Barra 1"}]},
    ).json()
    assert renamed[0]["etiqueta"] == "Barra 1"
    assert renamed[0]["url_publica"] == first[0]["url_publica"]


def test_baja_revoca_y_realta_emite_token_nuevo(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)
    mesa_uuid = str(uuid.uuid4())
    first = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    ).json()
    old_token = _token_de_url(first[0]["url_publica"])

    empty = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": []},
    )
    assert empty.status_code == 200
    assert empty.json() == []
    gone = negocio_client.get(f"/v1/cfc/mesa/{old_token}")
    assert gone.status_code == 410
    assert gone.json()["code"] == "identity.mesa_token_revocado"
    assert gone.headers.get("cache-control") == "no-store"

    reborn = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    ).json()
    new_url = reborn[0]["url_publica"]
    assert new_url != first[0]["url_publica"]
    still_gone = negocio_client.get(f"/v1/cfc/mesa/{old_token}")
    assert still_gone.status_code == 410
    ok = negocio_client.get(f"/v1/cfc/mesa/{_token_de_url(new_url)}")
    assert ok.status_code == 200
    assert ok.json()["etiqueta"] == "B1"
    assert ok.json()["mesa_uuid"] == mesa_uuid


def test_rotar_invalida_el_token_anterior(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)
    mesa_uuid = str(uuid.uuid4())
    created = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "T2"}]},
    ).json()
    old_token = _token_de_url(created[0]["url_publica"])

    rotated = negocio_client.post(
        f"/v1/establecimientos/{est_id}/mesas-cfc/{mesa_uuid}/rotar",
        headers=headers,
    )
    assert rotated.status_code == 201
    new_url = rotated.json()["url_publica"]
    assert new_url != created[0]["url_publica"]
    assert negocio_client.get(f"/v1/cfc/mesa/{old_token}").status_code == 410
    assert negocio_client.get(f"/v1/cfc/mesa/{_token_de_url(new_url)}").status_code == 200


def test_get_publico_404_y_no_store(db_ready, negocio_client):
    resp = negocio_client.get("/v1/cfc/mesa/token-que-no-existe")
    assert resp.status_code == 404
    assert resp.json()["code"] == "identity.mesa_token_invalido"
    assert resp.headers.get("cache-control") == "no-store"


def test_get_publico_devuelve_ficha_sin_carta(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token, "Taberna Luz")
    mesa_uuid = str(uuid.uuid4())
    created = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    ).json()
    raw = _token_de_url(created[0]["url_publica"])
    resp = negocio_client.get(f"/v1/cfc/mesa/{raw}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["establecimiento_id"] == est_id
    assert body["establecimiento_nombre"] == "Taberna Luz"
    assert body["mesa_uuid"] == mesa_uuid
    assert body["etiqueta"] == "B1"
    assert "carta" not in body
    assert "url_publica" not in body
    assert resp.headers.get("cache-control") == "no-store"


def test_otra_cuenta_no_puede_gestionar(db_ready, negocio_client):
    _, token_a = _crear_negocio(negocio_client, "mesa-a")
    _, token_b = _crear_negocio(negocio_client, "mesa-b")
    est_id = _crear_establecimiento(negocio_client, token_a)
    mesa_uuid = str(uuid.uuid4())
    negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    )
    forbidden = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    )
    assert forbidden.status_code == 403
    listed = negocio_client.get(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert listed.status_code == 403
    unauth = negocio_client.get(f"/v1/establecimientos/{est_id}/mesas-cfc")
    assert unauth.status_code == 401


def test_duplicados_y_etiqueta_b1_como_id_422(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)
    mesa_uuid = str(uuid.uuid4())
    dup = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={
            "mesas": [
                {"mesa_uuid": mesa_uuid, "etiqueta": "B1"},
                {"mesa_uuid": mesa_uuid, "etiqueta": "B2"},
            ]
        },
    )
    assert dup.status_code == 422
    label_as_id = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": "B1", "etiqueta": "B1"}]},
    )
    assert label_as_id.status_code == 422


def test_tope_500_mesas(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)
    mesas = [{"mesa_uuid": str(uuid.uuid4()), "etiqueta": f"M{i}"} for i in range(501)]
    resp = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": mesas},
    )
    assert resp.status_code == 422


def test_get_lista_solo_activas_con_url(db_ready, negocio_client):
    _, token = _crear_negocio(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    est_id = _crear_establecimiento(negocio_client, token)
    keep = str(uuid.uuid4())
    drop = str(uuid.uuid4())
    negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={
            "mesas": [
                {"mesa_uuid": keep, "etiqueta": "Keep"},
                {"mesa_uuid": drop, "etiqueta": "Drop"},
            ]
        },
    )
    negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": keep, "etiqueta": "Keep"}]},
    )
    listed = negocio_client.get(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
    )
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["mesa_uuid"] == keep
    assert body[0]["url_publica"].startswith(f"{os.environ['WEB_CFC_URL_BASE']}/m/")


def test_access_log_no_incluye_el_token_de_mesa(db_ready, negocio_client):
    registros = []

    class _Capture(logging.Handler):
        def emit(self, record):
            registros.append(record.getMessage())

    handler = _Capture()
    access_logger.addHandler(handler)
    try:
        negocio_client.get("/v1/cfc/mesa/secreto-de-mesa-xyz")
    finally:
        access_logger.removeHandler(handler)

    assert registros
    payload = json.loads(registros[-1])
    assert payload["path"] == "/v1/cfc/mesa/*"
    assert "secreto-de-mesa-xyz" not in registros[-1]
