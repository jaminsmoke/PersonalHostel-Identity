from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import engine
from app.errors import VALIDATION_ERROR, ApiError
from app.routes.auth import router as auth_router
from app.routes.camareros import router as camareros_router
from app.routes.establecimientos import (
    invitations_router,
    keys_router,
    router as establecimientos_router,
)

CAMPOS_LEGIBLES = {
    "nombre": "nombre",
    "apellidos": "apellidos",
    "email": "email",
    "telefono": "telefono",
    "password": "contraseña",
    "body": "cuerpo de la petición",
}


def _msg_espanol(err: dict) -> str:
    loc = err.get("loc", [])
    campo = str(loc[-1]) if loc else "?"
    campo = CAMPOS_LEGIBLES.get(campo, campo)
    tipo = err.get("type", "")
    if tipo == "missing":
        return f"El campo '{campo}' es obligatorio"
    if tipo == "string_too_short":
        return f"El campo '{campo}' no puede estar vacío"
    if tipo == "string_too_long":
        return f"El campo '{campo}' es demasiado largo"
    if tipo == "value_error" or "email" in tipo:
        return f"El campo '{campo}' no es un email válido"
    return f"Valor inválido en el campo '{campo}'"


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title="Personal Hostelería — Identity",
    version="0.2.0",
    description="Identidad profesional y cuentas de negocio: ver AGENTS.md.",
    lifespan=lifespan,
)

app.include_router(camareros_router)
app.include_router(auth_router)
app.include_router(establecimientos_router)
app.include_router(keys_router)
app.include_router(invitations_router)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    mensajes = [_msg_espanol(err) for err in exc.errors()]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": mensajes, "code": VALIDATION_ERROR},
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/v1/meta")
def meta() -> dict[str, str]:
    return {
        "service": "personal-hosteleria-identity",
        "role": "identity",
        "status": "schema",
    }
