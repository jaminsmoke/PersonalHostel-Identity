import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import NegocioSessionLocal
from app.schemas import LayoutResponse, layout_response_from_row

_LAYOUT_SALAS = [
    {"id": "sala-barra", "nombre": "Barra", "orden": 1},
    {"id": "sala-terraza", "nombre": "Terraza", "orden": 2},
]
_LAYOUT_MESAS = [
    {
        "id": "mesa-b1",
        "salaId": "sala-barra",
        "indiceZona": 1,
        "numero": 1,
        "alias": None,
        "forma": "CUADRADA",
        "capacidad": 4,
        "posX": 0.0,
        "posY": 0.0,
        "girada": False,
        "bloqueada": False,
        "reservaActivaId": None,
    }
]
_LAYOUT_ZONAS = [
    {
        "id": "zona-barra-alta",
        "salaId": "sala-barra",
        "nombre": "Barra alta",
        "posX": 40.0,
        "posY": 80.0,
        "ancho": 400.0,
        "alto": 240.0,
        "color": "AZUL",
        "camareroId": "camarero-ana",
    }
]


@pytest.fixture(scope="module")
def db_ready():
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def test_layout_response_proyecta_extras_y_metadatos_ganan():
    ahora = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    establecimiento_id = uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    respuesta = layout_response_from_row(
        establecimiento_id,
        version=4,
        updated_at=ahora,
        documento={
            "salas": _LAYOUT_SALAS,
            "mesas": _LAYOUT_MESAS,
            "zonas": _LAYOUT_ZONAS,
            "version": 1,
            "establecimiento_id": "ignorar",
        },
    )
    dumped = respuesta.model_dump(mode="json")
    assert dumped["establecimiento_id"] == str(establecimiento_id)
    assert dumped["version"] == 4
    assert dumped["salas"] == _LAYOUT_SALAS
    assert dumped["mesas"] == _LAYOUT_MESAS
    assert dumped["zonas"] == _LAYOUT_ZONAS

    mini = FastAPI()

    @mini.get("/layout", response_model=LayoutResponse)
    def _get() -> LayoutResponse:
        return respuesta

    encoded = TestClient(mini).get("/layout").json()
    assert encoded["zonas"] == _LAYOUT_ZONAS
    assert encoded["version"] == 4


def _crear_negocio_con_establecimiento(negocio_client) -> tuple[str, str, str, str]:
    email = _email("layout-negocio")
    response = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Bar Layout",
            "email": email,
            "password": "negocio-12345678",
        },
    )
    assert response.status_code == 201
    negocio_id = response.json()["id"]
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    token = login.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    created = negocio_client.post(
        "/v1/establecimientos", headers=headers, json={"nombre": "Bar Layout"}
    )
    assert created.status_code == 201
    establecimiento_id = created.json()["id"]
    return negocio_id, token, establecimiento_id, email


def _crear_camarero(camarero_client) -> tuple[str, str]:
    email = _email("layout-camarero")
    response = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert response.status_code == 201
    login = camarero_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    return login.json()["token"], email


def test_put_layout_crea_y_get_devuelve_fiel(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS},
    )
    assert put.status_code == 200
    put_data = put.json()
    assert put_data["establecimiento_id"] == establecimiento_id
    assert put_data["version"] == 1
    assert put_data["salas"] == _LAYOUT_SALAS
    assert put_data["mesas"] == _LAYOUT_MESAS
    assert put_data["updated_at"]

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert get.status_code == 200
    get_data = get.json()
    assert get_data["establecimiento_id"] == establecimiento_id
    assert get_data["version"] == 1
    assert get_data["salas"] == _LAYOUT_SALAS
    assert get_data["mesas"] == _LAYOUT_MESAS


def test_put_layout_sobrescribe_con_version_incremental(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    first = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS},
    )
    assert first.status_code == 200
    assert first.json()["version"] == 1

    nuevo_mesas = [
        {**_LAYOUT_MESAS[0], "capacidad": 6, "posX": 3.0},
        {
            "id": "mesa-b2",
            "salaId": "sala-barra",
            "indiceZona": 2,
            "numero": 2,
            "alias": None,
            "forma": "RECTANGULAR",
            "capacidad": 6,
            "posX": 3.0,
            "posY": 0.0,
            "girada": True,
            "bloqueada": False,
            "reservaActivaId": None,
        },
    ]
    second = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": nuevo_mesas},
    )
    assert second.status_code == 200
    assert second.json()["version"] == 2
    assert second.json()["mesas"] == nuevo_mesas

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert get.json()["version"] == 2
    assert get.json()["mesas"] == nuevo_mesas


def test_get_layout_sin_snapshot_404(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert get.status_code == 404
    assert get.json()["code"] == "identity.layout_no_encontrado"


def test_put_layout_payload_invalido_422(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    sin_salas = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"mesas": _LAYOUT_MESAS},
    )
    assert sin_salas.status_code == 422
    assert sin_salas.json()["code"] == "identity.validation_error"

    no_listas = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": {"no": "es lista"}, "mesas": _LAYOUT_MESAS},
    )
    assert no_listas.status_code == 422
    assert no_listas.json()["code"] == "identity.validation_error"

    gigante = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": [{"relleno": "x" * 1_200_000}], "mesas": []},
    )
    assert gigante.status_code == 422
    assert gigante.json()["code"] == "identity.validation_error"


def test_layout_requiere_cuenta_negocio(db_ready, camarero_client, negocio_client):
    _, _, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    payload = {"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS}

    sin_token = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout", json=payload
    )
    assert sin_token.status_code == 401

    camarero_token, _ = _crear_camarero(camarero_client)
    camarero_headers = {"Authorization": f"Bearer {camarero_token}"}
    camarero_put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=camarero_headers,
        json=payload,
    )
    assert camarero_put.status_code == 401

    _, otra_token, otro_establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    otra_headers = {"Authorization": f"Bearer {otra_token}"}
    otro_put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=otra_headers,
        json=payload,
    )
    assert otro_put.status_code == 403
    otro_get = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=otra_headers,
    )
    assert otro_get.status_code == 403


def test_layout_de_otro_negocio_no_se_ve(db_ready, negocio_client):
    _, token_a, establecimiento_a, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers_a = {"Authorization": f"Bearer {token_a}"}
    negocio_client.put(
        f"/v1/establecimientos/{establecimiento_a}/layout",
        headers=headers_a,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS},
    )
    _, token_b, _, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers_b = {"Authorization": f"Bearer {token_b}"}
    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_a}/layout", headers=headers_b)
    assert get.status_code == 403


def test_put_layout_con_zonas_round_trip(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS, "zonas": _LAYOUT_ZONAS}

    put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json=payload,
    )
    assert put.status_code == 200
    assert put.json()["salas"] == _LAYOUT_SALAS
    assert put.json()["mesas"] == _LAYOUT_MESAS
    assert put.json()["zonas"] == _LAYOUT_ZONAS

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert get.status_code == 200
    assert get.json()["zonas"] == _LAYOUT_ZONAS


def test_put_layout_clave_extra_opaca_round_trip(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}
    decoracion = [{"id": "neon-1", "tipo": "rotulo"}]

    put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS, "decoracion": decoracion},
    )
    assert put.status_code == 200
    assert put.json()["decoracion"] == decoracion

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert get.json()["decoracion"] == decoracion


def test_put_layout_sin_zonas_no_inventa_la_clave(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS},
    )
    assert put.status_code == 200
    assert "zonas" not in put.json()

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert "zonas" not in get.json()


def test_put_layout_sin_extras_sustituye_el_documento(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    first = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS, "zonas": _LAYOUT_ZONAS},
    )
    assert first.status_code == 200
    assert first.json()["zonas"] == _LAYOUT_ZONAS

    second = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={"salas": _LAYOUT_SALAS, "mesas": _LAYOUT_MESAS},
    )
    assert second.status_code == 200
    assert "zonas" not in second.json()

    get = negocio_client.get(f"/v1/establecimientos/{establecimiento_id}/layout", headers=headers)
    assert "zonas" not in get.json()


def test_put_layout_metadatos_reservados_422(db_ready, negocio_client):
    _, token, establecimiento_id, _ = _crear_negocio_con_establecimiento(negocio_client)
    headers = {"Authorization": f"Bearer {token}"}

    put = negocio_client.put(
        f"/v1/establecimientos/{establecimiento_id}/layout",
        headers=headers,
        json={
            "salas": _LAYOUT_SALAS,
            "mesas": _LAYOUT_MESAS,
            "establecimiento_id": establecimiento_id,
            "version": 99,
        },
    )
    assert put.status_code == 422
    assert put.json()["code"] == "identity.validation_error"
