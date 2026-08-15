import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db import CamareroSessionLocal, NegocioSessionLocal
from app.models import Invitacion, InvitacionEstado


@pytest.fixture(scope="module")
def db_ready():
    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _camarero(camarero_client, prefix: str = "est-inv-cam") -> str:
    email = _email(prefix)
    registered = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Ana",
            "apellidos": "García",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert registered.status_code == 201
    return email


def _negocio(negocio_client, prefix: str = "est-inv-biz") -> str:
    email = _email(prefix)
    registered = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Bar Smoke",
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
        json={"nombre": "Bar Invitaciones"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _crear_invitacion(negocio_client, token: str, establecimiento_id: str, email: str) -> str:
    response = negocio_client.post(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": email, "rol": "staff"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _set_estado(invitacion_id: str, estado: InvitacionEstado) -> None:
    with NegocioSessionLocal() as session:
        invitation = session.get(Invitacion, uuid.UUID(invitacion_id))
        invitation.estado = estado
        if estado == InvitacionEstado.aceptada:
            invitation.aceptada_en = datetime.now(UTC)
        session.commit()


def test_listar_sin_token_401(negocio_client):
    response = negocio_client.get(f"/v1/establecimientos/{uuid.uuid4()}/invitaciones")
    assert response.status_code == 401


def test_listar_vacia(db_ready, camarero_client, negocio_client):
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    response = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {negocio_token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_listar_y_filtrar_por_estado(db_ready, camarero_client, negocio_client):
    email_a = _camarero(camarero_client, "est-inv-cam-a")
    email_b = _camarero(camarero_client, "est-inv-cam-b")
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    inv_a = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email_a)
    inv_b = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email_b)
    _set_estado(inv_a, InvitacionEstado.aceptada)

    headers = {"Authorization": f"Bearer {negocio_token}"}
    todo = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones", headers=headers
    )
    assert todo.status_code == 200
    assert len(todo.json()) == 2
    for item in todo.json():
        assert item["creada_en"] is not None
        assert "token" not in item

    aceptadas = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers=headers,
        params={"estado": "aceptada"},
    )
    assert aceptadas.status_code == 200
    assert [i["id"] for i in aceptadas.json()] == [inv_a]

    pendientes = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers=headers,
        params={"estado": "pendiente"},
    )
    assert pendientes.status_code == 200
    assert [i["id"] for i in pendientes.json()] == [inv_b]


def test_listar_expirada_derivada(db_ready, camarero_client, negocio_client):
    email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    inv_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    with NegocioSessionLocal() as session:
        invitation = session.get(Invitacion, uuid.UUID(inv_id))
        invitation.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    headers = {"Authorization": f"Bearer {negocio_token}"}
    todo = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones", headers=headers
    )
    assert todo.status_code == 200
    assert todo.json()[0]["estado"] == "expirada"

    expiradas = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers=headers,
        params={"estado": "expirada"},
    )
    assert [i["id"] for i in expiradas.json()] == [inv_id]

    pendientes = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers=headers,
        params={"estado": "pendiente"},
    )
    assert pendientes.json() == []


def test_listar_filtro_invalido_422(db_ready, camarero_client, negocio_client):
    email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    response = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {negocio_token}"},
        params={"estado": "no-existe"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "identity.validation_error"


def test_listar_establecimiento_ajeno_403(db_ready, camarero_client, negocio_client):
    email = _camarero(camarero_client)
    token_a = _negocio(negocio_client, "est-inv-biz-a")
    establecimiento_id = _establecimiento(negocio_client, token_a)
    _crear_invitacion(negocio_client, token_a, establecimiento_id, email)

    token_b = _negocio(negocio_client, "est-inv-biz-b")
    response = negocio_client.get(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "identity.membresia_prohibida"


def test_listar_establecimiento_inexistente_404(db_ready, negocio_client):
    token = _negocio(negocio_client)
    response = negocio_client.get(
        f"/v1/establecimientos/{uuid.uuid4()}/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "identity.establecimiento_no_encontrado"
