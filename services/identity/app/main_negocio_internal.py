"""Listener interno de negocio: `/internal/*` y `/metrics`.

No se publica por Caddy. Prometheus y el servicio de camareros lo alcanzan
en `:8081` por la red Docker.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import negocio_engine
from app.http import register_error_handlers
from app.observability import mount_access_log, mount_metrics
from app.routes.internal import negocio_internal_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    with negocio_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Personal Hostelería — Identity (negocio, interno)",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

register_error_handlers(app)
mount_metrics(app)
mount_access_log(app)
app.include_router(negocio_internal_router)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
