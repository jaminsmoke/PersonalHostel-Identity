from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_credencial_activa,
    verify_password,
)
from app.db import get_camarero_db
from app.errors import (
    CREDENTIAL_REVOKED,
    INVALID_CREDENTIALS,
    ApiError,
)
from app.models import Camarero
from app.rate_limit import OPENAPI_RATE_LIMIT, enforce_login_limits
from app.schemas import ErrorResponse, LoginRequest, LoginResponse
from app.security import build_qr_payload, ficha_url, get_session_secret, get_signing_key

router = APIRouter(prefix="/v1/auth", tags=["auth"])

CLAVE_REVOCADA = "Clave revocada. Renueva la clave"

_LOGIN_401 = {
    "model": ErrorResponse,
    "description": "Email o contraseña incorrectos.",
}
_LOGIN_409 = {
    "model": ErrorResponse,
    "description": "Cuenta sin credencial activa (revocada).",
}
_LOGIN_422 = {
    "model": ErrorResponse,
    "description": "Cuerpo de la petición inválido.",
}


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _LOGIN_401,
        status.HTTP_409_CONFLICT: _LOGIN_409,
        status.HTTP_422_UNPROCESSABLE_CONTENT: _LOGIN_422,
        **OPENAPI_RATE_LIMIT,
    },
)
def login(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_camarero_db),
) -> LoginResponse:
    enforce_login_limits(request, payload.email)
    camarero = db.query(Camarero).filter_by(email=payload.email.lower()).one_or_none()

    if camarero is None or camarero.password_hash is None:
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_CREDENTIALS,
            detail="Email o contraseña incorrectos",
        )
    if not verify_password(payload.password, camarero.password_hash):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=INVALID_CREDENTIALS,
            detail="Email o contraseña incorrectos",
        )

    credencial = get_credencial_activa(db, camarero.id)
    if credencial is None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CREDENTIAL_REVOKED,
            detail=CLAVE_REVOCADA,
        )

    secret = get_session_secret(db)
    token = create_access_token(camarero.id, secret)
    qr = build_qr_payload(camarero.id, credencial.id, get_signing_key(db))
    return LoginResponse(token=token, camarero=camarero, qr=qr, ficha_url=ficha_url(qr))
