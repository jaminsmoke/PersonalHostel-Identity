"""Handlers de error compartidos por los dos servicios FastAPI."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import VALIDATION_ERROR, ApiError

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


def register_error_handlers(app: FastAPI) -> None:
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
