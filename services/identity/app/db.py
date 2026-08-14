import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_CAMAREROS_DEFAULT = "postgresql+psycopg://hosteleria:devlocal@db:5432/identity_camareros"
_NEGOCIO_DEFAULT = "postgresql+psycopg://hosteleria:devlocal@db:5432/identity_negocio"

# `DATABASE_URL` se mantiene como fallback del servicio de profesionales para
# no romper los tests locales que ya lo usan como default.
CAMAREROS_DATABASE_URL = os.environ.get(
    "CAMAREROS_DATABASE_URL",
    os.environ.get("DATABASE_URL", _CAMAREROS_DEFAULT),
)
NEGOCIO_DATABASE_URL = os.environ.get("NEGOCIO_DATABASE_URL", _NEGOCIO_DEFAULT)

camarero_engine = create_engine(CAMAREROS_DATABASE_URL)
negocio_engine = create_engine(NEGOCIO_DATABASE_URL)

CamareroSessionLocal = sessionmaker(
    bind=camarero_engine, autoflush=False, autocommit=False
)
NegocioSessionLocal = sessionmaker(
    bind=negocio_engine, autoflush=False, autocommit=False
)


class CamareroBase(DeclarativeBase):
    """Metadata de la BD de profesionales (camareros, credenciales, app_config)."""


class NegocioBase(DeclarativeBase):
    """Metadata de la BD de negocio (cuentas, establecimientos, membresías...)."""


# Back-compat: el servicio de profesionales es el "principal" histórico.
Base = CamareroBase
engine = camarero_engine
SessionLocal = CamareroSessionLocal


def get_camarero_db():
    db: Session = CamareroSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_negocio_db():
    db: Session = NegocioSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db():
    """Alias back-compat del dependency de profesionales."""
    yield from get_camarero_db()
