import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db import CamareroSessionLocal, NegocioSessionLocal
from app.models import EmailOutbox, Invitacion
from app.security import get_session_secret_env, unprotect_invitation_token


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
    email = _email("web-cam")
    registered = camarero_client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Web",
            "apellidos": "Camarero",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert registered.status_code == 201
    return registered.json()["id"], email


def _negocio(negocio_client) -> str:
    email = _email("web-biz")
    registered = negocio_client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Web Smoke",
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
        json={"nombre": "Web Onboarding"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _crear_invitacion(
    negocio_client, negocio_token: str, establecimiento_id: str, email: str
) -> str:
    invitation = negocio_client.post(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {negocio_token}"},
        json={"email": email},
    )
    assert invitation.status_code == 201
    invitation_id = uuid.UUID(invitation.json()["id"])
    with NegocioSessionLocal() as session:
        outbox = session.query(EmailOutbox).filter_by(invitacion_id=invitation_id).one()
        token = unprotect_invitation_token(
            outbox.payload["token_encrypted"], get_session_secret_env()
        )
    return token


def test_aceptar_por_magic_link_sin_jwt(db_ready, camarero_client, negocio_client):
    camarero_id, email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    token = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    accepted = negocio_client.post(f"/v1/invitaciones/{token}/aceptar")
    assert accepted.status_code == 200
    assert accepted.json()["membresia"]["camarero_id"] == camarero_id

    used = negocio_client.post(f"/v1/invitaciones/{token}/aceptar")
    assert used.status_code == 409
    assert used.json()["code"] == "identity.invitacion_ya_usada"


def test_aceptar_magic_link_sin_cuenta(db_ready, camarero_client, negocio_client):
    camarero_id, email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    token = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    login = camarero_client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    suppressed = camarero_client.request(
        "DELETE",
        "/v1/camareros/me",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
        json={"password": "pass-12345678"},
    )
    assert suppressed.status_code == 200

    response = negocio_client.post(f"/v1/invitaciones/{token}/aceptar")
    assert response.status_code == 404
    assert response.json()["code"] == "identity.camarero_no_encontrado"


def test_aceptar_magic_link_expirada(db_ready, camarero_client, negocio_client):
    _, email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    token = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    with NegocioSessionLocal() as session:
        invitation = (
            session.query(Invitacion)
            .filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest())
            .one()
        )
        invitation.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    expired = negocio_client.post(f"/v1/invitaciones/{token}/aceptar")
    assert expired.status_code == 410
    assert expired.json()["code"] == "identity.invitacion_expirada"


def test_cors_origen_permitido(db_ready, negocio_client):
    response = negocio_client.options(
        "/v1/invitaciones/dummy/aceptar",
        headers={
            "Origin": "http://localhost:8083",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8083"


def test_cors_origen_no_permitido(db_ready, negocio_client):
    response = negocio_client.options(
        "/v1/invitaciones/dummy/aceptar",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_camareros_origen_permitido(db_ready, camarero_client):
    response = camarero_client.options(
        "/v1/camareros/ficha",
        headers={
            "Origin": "http://localhost:8084",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8084"


def test_cors_web_camareros_origen_permitido(db_ready, camarero_client):
    response = camarero_client.options(
        "/v1/camareros/ficha",
        headers={
            "Origin": "https://web.camareros.siberia.solutions",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://web.camareros.siberia.solutions"
    )


def test_cors_camareros_origen_no_permitido(db_ready, camarero_client):
    response = camarero_client.options(
        "/v1/camareros/ficha",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_rechazar_por_magic_link_sin_jwt(db_ready, camarero_client, negocio_client):
    _, email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    token = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)

    rejected = negocio_client.post(f"/v1/invitaciones/{token}/rechazar")
    assert rejected.status_code == 200
    assert rejected.json()["estado"] == "rechazada"

    again = negocio_client.post(f"/v1/invitaciones/{token}/rechazar")
    assert again.status_code == 409
    assert again.json()["code"] == "identity.invitacion_ya_usada"


def test_rechazar_magic_link_expirada(db_ready, camarero_client, negocio_client):
    _, email = _camarero(camarero_client)
    negocio_token = _negocio(negocio_client)
    establecimiento_id = _establecimiento(negocio_client, negocio_token)
    token = _crear_invitacion(negocio_client, negocio_token, establecimiento_id, email)
    with NegocioSessionLocal() as session:
        invitation = (
            session.query(Invitacion)
            .filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest())
            .one()
        )
        invitation.expira_en = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()
    expired = negocio_client.post(f"/v1/invitaciones/{token}/rechazar")
    assert expired.status_code == 410
    assert expired.json()["code"] == "identity.invitacion_expirada"


def test_rechazar_magic_link_no_encontrada(db_ready, negocio_client):
    response = negocio_client.post("/v1/invitaciones/token-inexistente/rechazar")
    assert response.status_code == 404
    assert response.json()["code"] == "identity.invitacion_no_encontrada"


def test_cors_negocio_web_camareros_origen_permitido(db_ready, negocio_client):
    response = negocio_client.options(
        "/v1/invitaciones/dummy/aceptar",
        headers={
            "Origin": "https://web.camareros.siberia.solutions",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "https://web.camareros.siberia.solutions"
    )
