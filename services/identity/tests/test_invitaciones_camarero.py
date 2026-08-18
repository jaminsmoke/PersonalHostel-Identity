import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db import CamareroSessionLocal, NegocioSessionLocal
from app.models import Invitacion


@pytest.fixture(scope="module")
def db_ready():
    with CamareroSessionLocal() as session:
        session.execute(text("SELECT 1"))
    with NegocioSessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _camarero(camarero_client, prefix: str = "inv-cam") -> tuple[str, str, str]:
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
    login = camarero_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    return registered.json()["id"], email, login.json()["token"]


def _negocio(negocio_client) -> str:
    email = _email("inv-biz")
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
        json={"nombre": "Bar Test Invitaciones"},
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


def test_listar_invitaciones_sin_token_401(camarero_client):
    response = camarero_client.get("/v1/camareros/me/invitaciones")
    assert response.status_code == 401


def test_listar_invitaciones_vacia(db_ready, camarero_client):
    _, _, token = _camarero(camarero_client)
    response = camarero_client.get(
        "/v1/camareros/me/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_listar_invitaciones_pendiente(db_ready, camarero_client, negocio_client):
    _, email, token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    response = camarero_client.get(
        "/v1/camareros/me/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == invitation_id
    assert item["establecimiento_id"] == establecimiento_id
    assert item["estado"] == "pendiente"
    assert item["rol"] == "staff"
    assert item["establecimiento_nombre"] == "Bar Test Invitaciones"
    assert "token" not in item


def test_listar_no_expone_invitaciones_ajenas(db_ready, camarero_client, negocio_client):
    _, email, _ = _camarero(camarero_client, prefix="inv-cam-a")
    _, _, token_b = _camarero(camarero_client, prefix="inv-cam-b")
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    response = camarero_client.get(
        "/v1/camareros/me/invitaciones",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_aceptar_invitacion_por_id(db_ready, camarero_client, negocio_client):
    camarero_id, email, token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    accepted = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/aceptar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["invitacion_id"] == invitation_id
    assert body["membresia"]["camarero_id"] == camarero_id
    assert body["membresia"]["establecimiento_id"] == establecimiento_id
    assert body["membresia"]["estado"] == "activa"

    listed = camarero_client.get(
        "/v1/camareros/me/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["estado"] == "aceptada"

    again = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/aceptar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "identity.invitacion_ya_usada"


def test_aceptar_invitacion_por_id_ajena_403(db_ready, camarero_client, negocio_client):
    _, email, _ = _camarero(camarero_client, prefix="inv-cam-a")
    _, _, token_b = _camarero(camarero_client, prefix="inv-cam-b")
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    response = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/aceptar",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "identity.invitacion_no_autorizada"


def test_aceptar_invitacion_por_id_expirada_410(db_ready, camarero_client, negocio_client):
    _, email, token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    with NegocioSessionLocal() as session:
        invitation = session.get(Invitacion, uuid.UUID(invitation_id))
        invitation.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    response = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/aceptar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 410
    assert response.json()["code"] == "identity.invitacion_expirada"


def test_aceptar_invitacion_por_id_no_encontrada_404(db_ready, camarero_client):
    _, _, token = _camarero(camarero_client)
    response = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{uuid.uuid4()}/aceptar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "identity.invitacion_no_encontrada"


def test_rechazar_invitacion_por_id(db_ready, camarero_client, negocio_client):
    _, email, token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    rejected = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/rechazar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rejected.status_code == 200
    body = rejected.json()
    assert body["invitacion_id"] == invitation_id
    assert body["estado"] == "rechazada"

    listed = camarero_client.get(
        "/v1/camareros/me/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["estado"] == "rechazada"

    again = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/rechazar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "identity.invitacion_ya_usada"


def test_rechazar_invitacion_ajena_403(db_ready, camarero_client, negocio_client):
    _, email, _ = _camarero(camarero_client, prefix="inv-cam-a")
    _, _, token_b = _camarero(camarero_client, prefix="inv-cam-b")
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    response = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/rechazar",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "identity.invitacion_no_autorizada"


def test_rechazar_invitacion_expirada_410(db_ready, camarero_client, negocio_client):
    _, email, token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    with NegocioSessionLocal() as session:
        invitation = session.get(Invitacion, uuid.UUID(invitation_id))
        invitation.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    response = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{invitation_id}/rechazar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 410
    assert response.json()["code"] == "identity.invitacion_expirada"


def test_rechazar_invitacion_no_encontrada_404(db_ready, camarero_client):
    _, _, token = _camarero(camarero_client)
    response = camarero_client.post(
        f"/v1/camareros/me/invitaciones/{uuid.uuid4()}/rechazar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "identity.invitacion_no_encontrada"


def test_listar_invitaciones_expirada_derivada(db_ready, camarero_client, negocio_client):
    _, email, token = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    invitation_id = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    with NegocioSessionLocal() as session:
        invitation = session.get(Invitacion, uuid.UUID(invitation_id))
        invitation.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()

    response = camarero_client.get(
        "/v1/camareros/me/invitaciones",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()[0]["estado"] == "expirada"
