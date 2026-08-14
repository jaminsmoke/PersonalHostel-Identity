from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import camarero_engine
from app.http import register_error_handlers
from app.routes.auth import router as auth_router
from app.routes.camareros import router as camareros_router
from app.routes.internal import camareros_internal_router
from app.routes.keys import router as keys_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    with camarero_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Personal Hostelería — Identity (profesionales)",
    version="0.2.0",
    description="Identidad profesional (camareros) y credenciales/QR: ver AGENTS.md.",
    lifespan=lifespan,
)

register_error_handlers(app)

app.include_router(camareros_router)
app.include_router(auth_router)
app.include_router(keys_router)
app.include_router(camareros_internal_router)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/v1/meta")
def meta() -> dict[str, str]:
    return {
        "service": "personal-hosteleria-identity-camareros",
        "role": "identity",
        "status": "schema",
    }
