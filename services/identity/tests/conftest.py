import os
from urllib.parse import urlparse, urlunparse

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
os.environ.setdefault("ALLOW_NON_REAL_DATA", "true")


# Los tests NO tocan las BD de desarrollo: usan BD de prueba separadas.
# Se deriva el nombre de la BD del URL base para funcionar en Docker y en host.
def _test_url(base_url: str) -> str:
    parts = urlparse(base_url)
    db_name = parts.path.rsplit("/", 1)[-1] + "_test"
    return urlunparse(parts._replace(path="/" + db_name))


os.environ["CAMAREROS_DATABASE_URL"] = _test_url(os.environ["CAMAREROS_DATABASE_URL"])
os.environ["NEGOCIO_DATABASE_URL"] = _test_url(os.environ["NEGOCIO_DATABASE_URL"])

# Transporte interno en proceso: los tests cruzan servicios dentro del mismo
# proceso (TestClient), sin depender del contenedor hermano.
os.environ["INTERNAL_TRANSPORT"] = "direct"


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    import app.models  # noqa: F401  (registra los modelos en sus bases)
    from app.db import CamareroBase, NegocioBase, camarero_engine, negocio_engine

    CamareroBase.metadata.drop_all(camarero_engine)
    CamareroBase.metadata.create_all(camarero_engine)
    NegocioBase.metadata.drop_all(negocio_engine)
    NegocioBase.metadata.create_all(negocio_engine)
    yield


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
