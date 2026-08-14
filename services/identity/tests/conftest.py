import os

import pytest
from fastapi.testclient import TestClient

# Secretos compartidos: ambos servicios deben firmar/verificar con la misma
# clave para que el cruce de QR y de JWT funcione. En Docker ya vienen de
# compose; estos defaults cubren la ejecución local en el host.
os.environ.setdefault(
    "SESSION_SECRET",
    "test-session-secret-shared-between-services-0123456789abcdef",
)
os.environ.setdefault(
    "QR_SIGNING_KEY",
    "osYIdBW7fkucKVqY9St5yQKpLpDuAzJ4PeRaFMXbtDI=",
)
os.environ.setdefault(
    "CAMAREROS_DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity_camareros",
)
os.environ.setdefault(
    "NEGOCIO_DATABASE_URL",
    "postgresql+psycopg://hosteleria:devlocal@localhost:5432/identity_negocio",
)
# Transporte interno en proceso: los tests cruzan servicios dentro del mismo
# proceso (TestClient), sin depender del contenedor hermano.
os.environ["INTERNAL_TRANSPORT"] = "direct"


@pytest.fixture(scope="session")
def camarero_client() -> TestClient:
    from app.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def negocio_client() -> TestClient:
    from app.main_negocio import app

    with TestClient(app) as client:
        yield client
