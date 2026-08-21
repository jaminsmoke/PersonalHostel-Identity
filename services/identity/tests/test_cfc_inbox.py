import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.cfc import HEARTBEAT_STALE
from app.db import NegocioSessionLocal
from app.models import JornadaCfc
from app.observability import redact_access_path


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _negocio(negocio_client) -> tuple[str, dict]:
    email = _email("cfc-inbox")
    resp = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Bar Inbox",
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
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    est = negocio_client.post(
        "/v1/establecimientos",
        headers=headers,
        json={"nombre": "Terraza"},
    )
    assert est.status_code == 201
    return est.json()["id"], headers


def _mesa(negocio_client, est_id: str, headers: dict) -> tuple[str, str]:
    mesa_uuid = str(uuid.uuid4())
    resp = negocio_client.put(
        f"/v1/establecimientos/{est_id}/mesas-cfc",
        headers=headers,
        json={"mesas": [{"mesa_uuid": mesa_uuid, "etiqueta": "B1"}]},
    )
    assert resp.status_code == 200
    token = resp.json()[0]["url_publica"].rsplit("/m/", 1)[1]
    return mesa_uuid, token


def _producto(negocio_client, est_id: str, headers: dict) -> str:
    product_id = str(uuid.uuid4())
    body = {
        "operation_id": str(uuid.uuid4()),
        "device_id": "bar-test",
        "aggregate_type": "producto",
        "aggregate_id": product_id,
        "action": "crear",
        "base_revision": 0,
        "base_snapshot": None,
        "client_created_at": datetime.now(UTC).isoformat(),
        "payload": {
            "nombre": "Caña",
            "categoria": "Cervezas",
            "destino": "barra",
            "precio_centimos": 200,
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
    return product_id


def _horario(negocio_client, est_id: str, headers: dict, *, abierto: bool) -> None:
    if abierto:
        dias = [
            {"dia_semana": d, "turnos": [{"abre": "00:00", "cierra": "23:59"}]} for d in range(7)
        ]
    else:
        dias = [{"dia_semana": d, "cerrado": True, "turnos": []} for d in range(7)]
    resp = negocio_client.patch(
        f"/v1/establecimientos/{est_id}/horario",
        headers=headers,
        json={"dias": dias},
    )
    assert resp.status_code == 200, resp.text


def _envejecer_heartbeat(est_id: str) -> None:
    with NegocioSessionLocal() as session:
        jornada = (
            session.query(JornadaCfc)
            .filter_by(establecimiento_id=uuid.UUID(est_id))
            .filter(JornadaCfc.cerrada_en.is_(None))
            .one()
        )
        jornada.ultimo_heartbeat = datetime.now(UTC) - HEARTBEAT_STALE - timedelta(seconds=5)
        session.commit()


def test_redact_mantiene_el_sufijo_de_carta():
    assert redact_access_path("/v1/cfc/mesa/secreto/carta") == "/v1/cfc/mesa/*/carta"
    assert redact_access_path("/v1/cfc/mesa/secreto") == "/v1/cfc/mesa/*"


def test_sin_jornada_el_post_queda_cerrado(db_ready, negocio_client):
    est_id, headers = _negocio(negocio_client)
    _producto(negocio_client, est_id, headers)
    _, token = _mesa(negocio_client, est_id, headers)
    ficha = negocio_client.get(f"/v1/cfc/mesa/{token}")
    assert ficha.status_code == 200
    assert ficha.json()["admite_pedidos"] is False
    pedido = negocio_client.post(
        f"/v1/cfc/mesa/{token}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": str(uuid.uuid4()), "cantidad": 1}],
        },
    )
    assert pedido.status_code == 409
    assert pedido.json()["code"] == "identity.cfc_cerrado"


def test_jornada_abierta_acepta_e_idempotente(db_ready, negocio_client):
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    mesa_uuid, token = _mesa(negocio_client, est_id, headers)
    abierta = negocio_client.post(
        f"/v1/establecimientos/{est_id}/cfc/jornada/abrir",
        headers=headers,
    )
    assert abierta.status_code == 200
    key = str(uuid.uuid4())
    body = {
        "idempotency_key": key,
        "lineas": [{"producto_id": producto_id, "cantidad": 2}],
    }
    first = negocio_client.post(f"/v1/cfc/mesa/{token}/pedidos", json=body)
    assert first.status_code in (200, 201)
    assert first.json()["total_centimos"] == 400
    assert first.json()["mesa_uuid"] == mesa_uuid
    assert first.json()["lineas"][0]["precio_centimos"] == 200
    second = negocio_client.post(f"/v1/cfc/mesa/{token}/pedidos", json=body)
    assert second.status_code in (200, 201)
    assert second.json()["id"] == first.json()["id"]

    cola = negocio_client.get(
        f"/v1/establecimientos/{est_id}/cfc/pedidos",
        headers=headers,
    )
    assert cola.status_code == 200
    assert len(cola.json()["pedidos"]) == 1
    ack = negocio_client.post(
        f"/v1/establecimientos/{est_id}/cfc/pedidos/{first.json()['id']}/ack",
        headers=headers,
        json={"decision": "aceptado"},
    )
    assert ack.status_code == 200
    assert ack.json()["estado"] == "aceptado"
    vacia = negocio_client.get(
        f"/v1/establecimientos/{est_id}/cfc/pedidos",
        headers=headers,
    )
    assert vacia.json()["pedidos"] == []


def test_outage_dentro_de_horario_encola(db_ready, negocio_client):
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    _, token = _mesa(negocio_client, est_id, headers)
    _horario(negocio_client, est_id, headers, abierto=True)
    negocio_client.post(f"/v1/establecimientos/{est_id}/cfc/jornada/abrir", headers=headers)
    _envejecer_heartbeat(est_id)
    ficha = negocio_client.get(f"/v1/cfc/mesa/{token}").json()
    assert ficha["admite_pedidos"] is True
    assert ficha["bar_en_linea"] is False
    pedido = negocio_client.post(
        f"/v1/cfc/mesa/{token}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert pedido.status_code in (200, 201)


def test_outage_fuera_de_horario_no_encola(db_ready, negocio_client):
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    _, token = _mesa(negocio_client, est_id, headers)
    _horario(negocio_client, est_id, headers, abierto=False)
    negocio_client.post(f"/v1/establecimientos/{est_id}/cfc/jornada/abrir", headers=headers)
    _envejecer_heartbeat(est_id)
    ficha = negocio_client.get(f"/v1/cfc/mesa/{token}").json()
    assert ficha["admite_pedidos"] is False
    pedido = negocio_client.post(
        f"/v1/cfc/mesa/{token}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert pedido.status_code == 409
    assert pedido.json()["code"] == "identity.cfc_cerrado"


def test_cerrar_jornada_caduca_pendientes(db_ready, negocio_client):
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    _, token = _mesa(negocio_client, est_id, headers)
    negocio_client.post(f"/v1/establecimientos/{est_id}/cfc/jornada/abrir", headers=headers)
    creado = negocio_client.post(
        f"/v1/cfc/mesa/{token}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert creado.status_code in (200, 201)
    cierre = negocio_client.post(
        f"/v1/establecimientos/{est_id}/cfc/jornada/cerrar",
        headers=headers,
    )
    assert cierre.status_code == 200
    cola = negocio_client.get(
        f"/v1/establecimientos/{est_id}/cfc/pedidos",
        headers=headers,
    )
    assert cola.json()["pedidos"] == []
    nuevo = negocio_client.post(
        f"/v1/cfc/mesa/{token}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 1}],
        },
    )
    assert nuevo.status_code == 409


def test_carta_incluye_id_y_cuenta_agrega(db_ready, negocio_client):
    est_id, headers = _negocio(negocio_client)
    producto_id = _producto(negocio_client, est_id, headers)
    _, token = _mesa(negocio_client, est_id, headers)
    negocio_client.post(f"/v1/establecimientos/{est_id}/cfc/jornada/abrir", headers=headers)
    carta = negocio_client.get(f"/v1/cfc/mesa/{token}/carta")
    assert carta.status_code == 200
    assert carta.json()["productos"][0]["id"] == producto_id
    negocio_client.post(
        f"/v1/cfc/mesa/{token}/pedidos",
        json={
            "idempotency_key": str(uuid.uuid4()),
            "lineas": [{"producto_id": producto_id, "cantidad": 3}],
        },
    )
    cuenta = negocio_client.get(f"/v1/cfc/mesa/{token}/cuenta")
    assert cuenta.status_code == 200
    assert cuenta.json()["total_centimos"] == 600
    assert cuenta.json()["lineas"][0]["cantidad"] == 3


def test_otra_cuenta_no_abre_jornada(db_ready, negocio_client):
    est_id, headers_a = _negocio(negocio_client)
    _, headers_b = _negocio(negocio_client)
    resp = negocio_client.post(
        f"/v1/establecimientos/{est_id}/cfc/jornada/abrir",
        headers=headers_b,
    )
    assert resp.status_code == 403
