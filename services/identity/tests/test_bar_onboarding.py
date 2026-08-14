import base64
import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import nacl.signing
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity",
)

from app.auth import create_access_token  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import EmailOutbox, Invitacion  # noqa: E402
from app.security import get_session_secret, unprotect_invitation_token, verify_qr_payload  # noqa: E402

client = TestClient(app)


@pytest.fixture(scope="module")
def db_ready():
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))
    yield


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}@example.com"


def _camarero() -> tuple[str, str, str, str]:
    email = _email("onboarding-cam")
    registered = client.post(
        "/v1/camareros/registro",
        json={
            "nombre": "Bar",
            "apellidos": "Camarero",
            "email": email,
            "password": "pass-12345678",
        },
    )
    assert registered.status_code == 201
    login = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "pass-12345678"},
    )
    assert login.status_code == 200
    return registered.json()["id"], email, registered.json()["qr"], login.json()["token"]


def _negocio() -> str:
    email = _email("onboarding-biz")
    registered = client.post(
        "/v1/auth/negocio/registro",
        json={
            "nombre_mostrar": "Bar Smoke",
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
        json={"nombre": "Bar Onboarding"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_clave_publica_y_alta_por_qr(db_ready):
    camarero_id, _, qr, _ = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    public = client.get("/v1/keys/qr")
    assert public.status_code == 200
    body = public.json()
    verify_key = nacl.signing.VerifyKey(
        base64.urlsafe_b64decode(body["public_key"] + "=" * (-len(body["public_key"]) % 4))
    )
    assert verify_qr_payload(qr, verify_key)
    added = client.post(
        f"/v1/establecimientos/{establecimiento_id}/miembros/qr",
        headers={"Authorization": f"Bearer {negocio_token}"},
        json={"qr": qr, "rol": "staff"},
    )
    assert added.status_code == 201
    assert added.json()["camarero_id"] == camarero_id


def test_qr_revocado_no_se_puede_anadir(db_ready):
    _, _, qr, camarero_token = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    revoked = client.post(
        "/v1/camareros/me/revocar",
        headers={"Authorization": f"Bearer {camarero_token}"},
        json={"motivo": "prueba"},
    )
    assert revoked.status_code == 200
    response = client.post(
        f"/v1/establecimientos/{establecimiento_id}/miembros/qr",
        headers={"Authorization": f"Bearer {negocio_token}"},
        json={"qr": qr},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "identity.credencial_inactiva"


def test_busqueda_invitacion_outbox_y_aceptacion(db_ready):
    camarero_id, email, _, camarero_token = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    headers = {"Authorization": f"Bearer {negocio_token}"}
    found = client.get(
        f"/v1/establecimientos/{establecimiento_id}/camareros/buscar",
        headers=headers,
        params={"email": email},
    )
    assert found.status_code == 200
    assert found.json()["id"] == camarero_id

    invitation = client.post(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers=headers,
        json={"email": email, "rol": "staff"},
    )
    assert invitation.status_code == 201
    invitation_id = invitation.json()["id"]
    with SessionLocal() as session:
        row = session.get(Invitacion, uuid.UUID(invitation_id))
        outbox = (
            session.query(EmailOutbox)
            .filter_by(invitacion_id=uuid.UUID(invitation_id))
            .one()
        )
        assert "token" not in outbox.payload
        assert outbox.payload["token_encrypted"]
        token = unprotect_invitation_token(
            outbox.payload["token_encrypted"], get_session_secret(session)
        )
        assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()

    accepted = client.post(
        f"/v1/invitaciones/{token}/aceptar",
        headers={"Authorization": f"Bearer {camarero_token}"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["membresia"]["camarero_id"] == camarero_id
    used = client.post(
        f"/v1/invitaciones/{token}/aceptar",
        headers={"Authorization": f"Bearer {camarero_token}"},
    )
    assert used.status_code == 409


def test_invitacion_expirada(db_ready):
    _, email, _, camarero_token = _camarero()
    negocio_token = _negocio()
    establecimiento_id = _establecimiento(negocio_token)
    invitation = client.post(
        f"/v1/establecimientos/{establecimiento_id}/invitaciones",
        headers={"Authorization": f"Bearer {negocio_token}"},
        json={"email": email},
    )
    assert invitation.status_code == 201
    invitation_id = uuid.UUID(invitation.json()["id"])
    with SessionLocal() as session:
        row = session.get(Invitacion, invitation_id)
        row.expira_en = datetime.now(timezone.utc) - timedelta(minutes=1)
        outbox = session.query(EmailOutbox).filter_by(invitacion_id=invitation_id).one()
        token = unprotect_invitation_token(
            outbox.payload["token_encrypted"], get_session_secret(session)
        )
        session.commit()
    expired = client.post(
        f"/v1/invitaciones/{token}/aceptar",
        headers={"Authorization": f"Bearer {camarero_token}"},
    )
    assert expired.status_code == 410
    assert expired.json()["code"] == "identity.invitacion_expirada"
