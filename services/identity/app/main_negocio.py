import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import negocio_engine
from app.http import register_error_handlers
from app.observability import mount_access_log, mount_metrics
from app.routes.catalogo import router as catalogo_router
from app.routes.enlaces import public_router as enlaces_public_router
from app.routes.enlaces import router as enlaces_router
from app.routes.establecimientos import (
    invitations_router,
)
from app.routes.establecimientos import (
    router as establecimientos_router,
)
from app.routes.fondos import router as fondos_router
from app.routes.horario import router as horario_router
from app.routes.internal import negocio_internal_router
from app.routes.mesas_cfc import public_router as mesas_cfc_public_router
from app.routes.mesas_cfc import router as mesas_cfc_router
from app.routes.negocio_auth import router as negocio_auth_router
from app.routes.negocio_carta import router as negocio_carta_router
from app.routes.negocio_web import router as negocio_web_router
from app.routes.oficio_negocio import router as oficio_negocio_router
from app.routes.perfil_web import router as perfil_web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    with negocio_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Personal Hostelería — Identity (negocio)",
    version="0.2.0",
    description=(
        "Cuentas de negocio, establecimientos, catálogo canónico, "
        "sincronización offline, membresías e invitaciones."
    ),
    lifespan=lifespan,
)

register_error_handlers(app)
mount_metrics(app)
mount_access_log(app)

_web_origins = [
    o.strip()
    for o in os.environ.get(
        "IDENTITY_WEB_ORIGIN",
        "http://localhost:8083,http://localhost:8084,http://localhost:8085,https://web.negocio.siberia.solutions,https://web.camareros.siberia.solutions,https://web.mesa.siberia.solutions",
    ).split(",")
    if o.strip()
]
if _web_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_web_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
        allow_credentials=False,
    )

app.include_router(negocio_auth_router)
app.include_router(negocio_carta_router)
app.include_router(negocio_web_router)
app.include_router(establecimientos_router)
app.include_router(catalogo_router)
app.include_router(enlaces_router)
app.include_router(enlaces_public_router)
app.include_router(mesas_cfc_router)
app.include_router(mesas_cfc_public_router)
app.include_router(invitations_router)
app.include_router(oficio_negocio_router)
app.include_router(horario_router)
app.include_router(perfil_web_router)
app.include_router(fondos_router)
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
