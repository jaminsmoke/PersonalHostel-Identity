import uuid

import pytest
from sqlalchemy import text

from app.db import CamareroSessionLocal, camarero_engine  # noqa: E402
from app.models import Camarero, Credencial, CredencialEstado, DataOrigin  # noqa: E402


@pytest.fixture(scope="module")
def db_ready():
    with camarero_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


def test_ping(db_ready):
    with camarero_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_credencial_insert_select(db_ready):
    with CamareroSessionLocal() as session:
        camarero = Camarero(
            nombre="Prueba",
            apellidos="Test",
            email=f"prueba-{uuid.uuid4()}@example.com",
        )
        session.add(camarero)
        session.flush()

        credencial = Credencial(
            camarero_id=camarero.id,
            secreto=str(uuid.uuid4()),
            estado=CredencialEstado.activa,
        )
        session.add(credencial)
        session.commit()

        cred_id = credencial.id

        fetched = session.get(Credencial, cred_id)
        assert fetched is not None
        assert fetched.estado == CredencialEstado.activa
        assert fetched.camarero.data_origin == DataOrigin.real

        session.delete(camarero)
        session.commit()

        assert session.get(Credencial, cred_id) is None
