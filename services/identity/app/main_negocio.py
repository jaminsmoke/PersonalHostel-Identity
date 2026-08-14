import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import negocio_engine
from app.http import register_error_handlers
from app.routes.establecimientos import (
    invitations_router,
    router as establecimientos_router,
)
from app.routes.internal import negocio_internal_router
from app.routes.negocio_auth import router as negocio_auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    with negocio_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Personal Hostelería — Identity (negocio)",
    version="0.2.0",
    description="Cuentas de negocio, establecimientos, membresías e invitaciones.",
    lifespan=lifespan,
)

register_error_handlers(app)

_web_origins = [
    o.strip()
    for o in os.environ.get("IDENTITY_WEB_ORIGIN", "http://localhost:8081").split(",")
    if o.strip()
]
if _web_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_web_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        allow_credentials=False,
    )

app.include_router(negocio_auth_router)
app.include_router(establecimientos_router)
app.include_router(invitations_router)
app.include_router(negocio_internal_router)


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/v1/meta")
def meta() -> dict[str, str]:
    return {
        "service": "personal-hosteleria-identity-negocio",
        "role": "identity",
        "status": "schema",
    }
