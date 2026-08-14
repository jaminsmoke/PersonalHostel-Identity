import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity",
)

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EmailOutbox, Invitacion  # noqa: E402
from app.security import get_session_secret, unprotect_invitation_token  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _camarero() -> tuple[str, str]:
    email = _email("web-cam")
    registered = client.post(
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


def _negocio() -> str:
    email = _email("web-biz")
    registered = client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Web Smoke",
            "email": email,
            "password": "negocio-12345678",
        },
    )
    assert registered.status_code == 201
    login = client.post(
        "/v1/auth/negocio/login",
        json={"email": email, "password": "negocio-12345678"},
    )
    assert login.status_code == 200
    return login.json()["token"]


def _establecimiento(token: str) -> str:
    response = client.post(
        "/v1/establecimientos",
        headers={"Authorization": f"Bearer {token}"},
        json={"nombre": "Web Onboarding"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _crear_invitacion(negocio_token: str, establecimiento_id: str, email: str) -> str:
    invitation = client.post(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {negocio_token}"},
        json={"email": email},
    )
    assert invitation.status_code == 201
    invitation_id = uuid.UUID(invitation.json()["id"])
    with SessionLocal() as session:
        outbox = session.query(EmailOutbox).filter_by(invitacion_id=invitation_id).one()
        token = unprotect_invitation_token(
            outbox.payload["token_encrypted"], get_session_secret(session)
        )
    return token


def test_aceptar_por_magic_link_sin_jwt(db_ready):
    camarero_id, email = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    token = _crear_invitacion(negocio_token, establecimiento_id, email)

    accepted = client.post(f"/v1/invitaciones/{token}/aceptar")
    assert accepted.status_code == 200
    assert accepted.json()["membresia"]["camarero_id"] == camarero_id

    used = client.post(f"/v1/invitaciones/{token}/aceptar")
    assert used.status_code == 409
    assert used.json()["code"] == "identity.invitacion_ya_usada"


def test_aceptar_magic_link_sin_cuenta(db_ready):
    camarero_id, email = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    token = _crear_invitacion(negocio_token, establecimiento_id, email)

    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    suppressed = client.request(
        "DELETE",
        "/v1/camareros/me",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
        json={"password": "pass-12345678"},
    )
    assert suppressed.status_code == 200

    response = client.post(f"/v1/invitaciones/{token}/aceptar")
    assert response.status_code == 404
    assert response.json()["code"] == "identity.camarero_no_encontrado"


def test_aceptar_magic_link_expirada(db_ready):
    _, email = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    token = _crear_invitacion(negocio_token, establecimiento_id, email)
    with SessionLocal() as session:
        invitation = (
            session.query(Invitacion)
            .filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest())
            .one()
        )
        invitation.expira_en = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()
    expired = client.post(f"/v1/invitaciones/{token}/aceptar")
    assert expired.status_code == 410
    assert expired.json()["code"] == "identity.invitacion_expirada"


def test_cors_origen_permitido(db_ready):
    response = client.options(
        "/v1/invitaciones/dummy/aceptar",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:8081"


def test_cors_origen_no_permitido(db_ready):
    response = client.options(
        "/v1/invitaciones/dummy/aceptar",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
