import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine

from app.data_audit import REDACTED, audit_data
from app.data_audit import main as audit_main
from app.db import camarero_engine, negocio_engine


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _register_waiter(client, *, origin=None, name="Ana"):
    payload = {
        "nombre": name,
        "apellidos": "García",
        "email": _email("origin-waiter"),
        "password": "password-123456",
    }
    if origin is not None:
        payload["data_origin"] = origin
    response = client.post("/v1/camareros/registro", json=payload)
    return response, payload


def _register_business(client, *, origin=None, name="Negocio"):
    payload = {
        "nombre_mostrar": name,
        "email": _email("origin-business"),
        "password": "password-123456",
    }
    if origin is not None:
        payload["data_origin"] = origin
    registration = client.post("/v1/auth/negocio/registro", json=payload)
    if registration.status_code != 201:
        return registration, payload, None
    login = client.post(
        "/v1/auth/negocio/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    return registration, payload, headers


def _create_product(client, establishment_id: str, headers: dict):
    product_id = str(uuid.uuid4())
    response = client.post(
        f"/v1/establecimientos/{establishment_id}/sync/operaciones",
        headers=headers,
        json={
            "operation_id": str(uuid.uuid4()),
            "device_id": "origin-test",
            "aggregate_type": "producto",
            "aggregate_id": product_id,
            "action": "crear",
            "base_revision": 0,
            "payload": {
                "nombre": "Café",
                "categoria": "Bebidas",
                "destino": "barra",
                "precio_centimos": 150,
                "moneda": "EUR",
                "disponible": True,
            },
            "client_created_at": datetime.now(UTC).isoformat(),
        },
    )
    return response, product_id


def test_default_real_es_compatible_en_ambos_servicios(camarero_client, negocio_client):
    waiter, waiter_payload = _register_waiter(camarero_client)
    assert waiter.status_code == 201, waiter.text
    assert waiter.json()["data_origin"] == "real"
    login = camarero_client.post(
        "/v1/auth/login",
        json={
            "email": waiter_payload["email"],
            "password": waiter_payload["password"],
        },
    )
    assert login.json()["camarero"]["data_origin"] == "real"

    business, _, headers = _register_business(negocio_client)
    assert business.status_code == 201, business.text
    assert business.json()["data_origin"] == "real"
    establishment = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Bar real"}
    )
    assert establishment.status_code == 201, establishment.text
    assert establishment.json()["data_origin"] == "real"
    operation, product_id = _create_product(negocio_client, establishment.json()["id"], headers)
    assert operation.status_code == 200, operation.text
    assert operation.json()["result_snapshot"]["data_origin"] == "real"
    catalog = negocio_client.get(
        f"/v1/establecimientos/{establishment.json()['id']}/catalogo",
        headers=headers,
    )
    product = next(p for p in catalog.json()["productos"] if p["id"] == product_id)
    assert product["data_origin"] == "real"


def test_test_y_demo_se_heredan_en_entidades_hijas(camarero_client, negocio_client):
    waiter, waiter_payload = _register_waiter(camarero_client, origin="test", name="AnaTest")
    assert waiter.status_code == 201, waiter.text
    assert waiter.json()["data_origin"] == "test"
    login = camarero_client.post(
        "/v1/auth/login",
        json={
            "email": waiter_payload["email"],
            "password": waiter_payload["password"],
        },
    )
    assert login.json()["camarero"]["data_origin"] == "test"

    business, _, headers = _register_business(negocio_client, origin="demo", name="Negocio demo")
    assert business.status_code == 201, business.text
    establishment = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Local demo"}
    )
    assert establishment.json()["data_origin"] == "demo"
    operation, _ = _create_product(negocio_client, establishment.json()["id"], headers)
    assert operation.status_code == 200, operation.text
    assert operation.json()["result_snapshot"]["data_origin"] == "demo"


def test_entorno_seguro_rechaza_procedencia_no_real(camarero_client, negocio_client, monkeypatch):
    monkeypatch.setenv("ALLOW_NON_REAL_DATA", "false")
    waiter, _ = _register_waiter(camarero_client, origin="test", name="BlockedTest")
    assert waiter.status_code == 422
    assert waiter.json()["code"] == "identity.procedencia_no_permitida"
    business, _, _ = _register_business(negocio_client, origin="demo", name="Blocked demo")
    assert business.status_code == 422
    assert business.json()["code"] == "identity.procedencia_no_permitida"


def test_no_permite_vinculos_cross_db_con_procedencia_distinta(camarero_client, negocio_client):
    waiter, _ = _register_waiter(camarero_client, origin="test", name="LinkTest")
    assert waiter.status_code == 201
    waiter_id = waiter.json()["id"]

    incompatible = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Cuenta real",
            "email": _email("mixed-linked"),
            "password": "password-123456",
            "camarero_vinculado_id": waiter_id,
        },
    )
    assert incompatible.status_code == 422
    assert incompatible.json()["code"] == "identity.procedencia_incompatible"

    business, _, headers = _register_business(negocio_client)
    assert business.status_code == 201
    establishment = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Local real"}
    )
    membership = negocio_client.post(
        f"/v1/establecimientos/{establishment.json()['id']}/miembros",
        headers=headers,
        json={"camarero_id": waiter_id, "rol": "staff"},
    )
    assert membership.status_code == 422
    assert membership.json()["code"] == "identity.procedencia_incompatible"


def test_auditor_reporta_y_redacta_pii(camarero_client, capsys):
    unique_name = f"Persona-{uuid.uuid4()}Test"
    response, _ = _register_waiter(camarero_client, name=unique_name)
    assert response.status_code == 201

    report = audit_data(camareros=camarero_engine, negocio=negocio_engine)
    serialized = json.dumps(report, ensure_ascii=False)
    assert report["detected"] is True
    assert report["pii_redacted"] is True
    assert unique_name not in serialized
    assert REDACTED in serialized
    assert any(
        finding.get("reason") == "sufijo_test_con_origen_real" for finding in report["findings"]
    )

    assert audit_main(["--format", "json", "--fail-on-detected"]) == 2
    output = capsys.readouterr().out
    assert unique_name not in output


def test_auditor_con_show_pii_es_solo_opt_in(camarero_client):
    unique_name = f"Visible-{uuid.uuid4()}Test"
    response, _ = _register_waiter(camarero_client, name=unique_name)
    assert response.status_code == 201
    report = audit_data(
        camareros=camarero_engine,
        negocio=negocio_engine,
        show_pii=True,
    )
    assert unique_name in json.dumps(report, ensure_ascii=False)


def test_auditor_rechaza_una_bd_inesperada_antes_de_conectar():
    unexpected = create_engine("postgresql+psycopg://hosteleria:devlocal@db:5432/produccion_ajena")
    with pytest.raises(ValueError, match="Base de datos inesperada"):
        audit_data(camareros=unexpected, negocio=negocio_engine)
    unexpected.dispose()
