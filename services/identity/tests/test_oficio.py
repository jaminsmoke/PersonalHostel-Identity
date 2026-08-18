import uuid

import pytest
from sqlalchemy import text

from app.db import CamareroSessionLocal, NegocioSessionLocal


@pytest.fixture(scope="module")
def db_ready():
    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _camarero(camarero_client) -> tuple[str, str]:
    """Registra y loguea un camarero; devuelve (id, token)."""
    email = _email("oficio-cam")
    registered = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Oficio",
            "apellidos": "CamareroTest",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert registered.status_code == 201
    login = camarero_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    return registered.json()["id"], login.json()["token"]


def _negocio(negocio_client) -> str:
    email = _email("oficio-biz")
    registered = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Oficio NegocioTest",
            "email": email,
            "password": "negocio-12345678",
        },
    )
    assert registered.status_code == 201
    login = negocio_client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return login.json()["token"]


def _establecimiento(negocio_client, token: str) -> str:
    response = negocio_client.post(
        "/v1/establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": "Oficio EstablecimientoTest"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _miembro(negocio_client, token: str, establecimiento_id: str, camarero_id: str) -> None:
    response = negocio_client.post(
        f"/v1/establecimientos/{establecimiento_id}/miembros",
        headers={"Authorization": f"Bearer {token}"},
        json={"camarero_id": camarero_id, "rol": "staff"},
    )
    assert response.status_code == 201


def test_jornada_iniciar_y_cortar(db_ready, camarero_client, negocio_client):
    camarero_id, camarero_token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    _miembro(negocio_client, negocio_token, establecimiento_id, camarero_id)

    headers = {"Authorization": f"Bearer {camarero_token}"}

    iniciada = camarero_client.post(
        "/v1/camareros/me/jornadas/iniciar",
        headers=headers,
        json={"establecimiento_id": establecimiento_id},
    )
    assert iniciada.status_code == 201
    assert iniciada.json()["establecimiento_id"] == establecimiento_id
    assert iniciada.json()["fin"] is None

    duplicada = camarero_client.post(
        "/v1/camareros/me/jornadas/iniciar",
        headers=headers,
        json={"establecimiento_id": establecimiento_id},
    )
    assert duplicada.status_code == 409
    assert duplicada.json()["code"] == "identity.jornada_ya_abierta"

    cortada = camarero_client.post("/v1/camareros/me/jornadas/cortar", headers=headers)
    assert cortada.status_code == 200
    assert cortada.json()["fin"] is not None

    sin_abierta = camarero_client.post("/v1/camareros/me/jornadas/cortar", headers=headers)
    assert sin_abierta.status_code == 404
    assert sin_abierta.json()["code"] == "identity.jornada_no_abierta"


def test_jornada_sin_membresia(db_ready, camarero_client, negocio_client):
    camarero_id, camarero_token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)

    iniciada = camarero_client.post(
        "/v1/camareros/me/jornadas/iniciar",
        headers={"Authorization": f"Bearer {camarero_token}"},
        json={"establecimiento_id": establecimiento_id},
    )
    assert iniciada.status_code == 403
    assert iniciada.json()["code"] == "identity.membresia_prohibida"


def test_registro_servicio_idempotente(db_ready, camarero_client, negocio_client):
    camarero_id, _ = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    _miembro(negocio_client, negocio_token, establecimiento_id, camarero_id)

    headers = {"Authorization": f"Bearer {negocio_token}"}
    evento = f"evt-{uuid.uuid4()}"
    body = {
        "establecimiento_id": establecimiento_id,
        "camarero_id": camarero_id,
        "evento_id": evento,
        "tipo": "mesa_servida",
        "cantidad": 1,
    }

    creado = negocio_client.post("/v1/negocio/estadisticas/servicio", headers=headers, json=body)
    assert creado.status_code == 200
    assert creado.json()["duplicado"] is False
    assert creado.json()["cantidad"] == 1

    repetido = negocio_client.post("/v1/negocio/estadisticas/servicio", headers=headers, json=body)
    assert repetido.status_code == 200
    assert repetido.json()["duplicado"] is True


def test_registro_servicio_sin_membresia(db_ready, camarero_client, negocio_client):
    camarero_id, _ = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)

    response = negocio_client.post(
        "/v1/negocio/estadisticas/servicio",
        headers={"Authorization": f"Bearer {negocio_token}"},
        json={
            "establecimiento_id": establecimiento_id,
            "camarero_id": camarero_id,
            "evento_id": f"evt-{uuid.uuid4()}",
            "tipo": "mesa_servida",
            "cantidad": 1,
        },
    )
    assert response.status_code == 403
    assert response.json()["code"] == "identity.membresia_prohibida"


def test_resumen_horas_y_mesas(db_ready, camarero_client, negocio_client):
    camarero_id, camarero_token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    _miembro(negocio_client, negocio_token, establecimiento_id, camarero_id)

    cam_headers = {"Authorization": f"Bearer {camarero_token}"}
    neg_headers = {"Authorization": f"Bearer {negocio_token}"}

    iniciada = camarero_client.post(
        "/v1/camareros/me/jornadas/iniciar",
        headers=cam_headers,
        json={"establecimiento_id": establecimiento_id},
    )
    assert iniciada.status_code == 201

    servicio = negocio_client.post(
        "/v1/negocio/estadisticas/servicio",
        headers=neg_headers,
        json={
            "establecimiento_id": establecimiento_id,
            "camarero_id": camarero_id,
            "evento_id": f"evt-{uuid.uuid4()}",
            "tipo": "mesa_servida",
            "cantidad": 3,
        },
    )
    assert servicio.status_code == 200

    resumen = camarero_client.get("/v1/camareros/me/resumen", headers=cam_headers)
    assert resumen.status_code == 200
    body = resumen.json()
    assert body["mesas_servidas"] == 3
    assert body["horas_segundos"] >= 0
    assert len(body["por_establecimiento"]) == 1
    assert body["por_establecimiento"][0]["mesas_servidas"] == 3
    assert body["por_establecimiento"][0]["establecimiento_id"] == establecimiento_id
