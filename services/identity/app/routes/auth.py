from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    create_business_access_token,
    get_credencial_activa,
    get_current_cuenta_negocio,
    verify_password,
    hash_password,
)
from app.db import get_db
from app.errors import (
    CAMARERO_NOT_FOUND,
    CREDENTIAL_REVOKED,
    INVALID_CREDENTIALS,
    NEGOCIO_EMAIL_ALREADY_REGISTERED,
    NEGOCIO_INVALID_CREDENTIALS,
    ApiError,
)
from app.models import Camarero, CuentaNegocio
from app.schemas import (
    CuentaNegocioPerfil,
    ErrorResponse,
    LoginNegocioResponse,
    LoginRequest,
    LoginResponse,
    RegistroNegocioRequest,
    RegistroNegocioResponse,
    SupresionNegocioRequest,
    SupresionResponse,
)
from sqlalchemy.exc import IntegrityError
from app.security import build_qr_payload, get_session_secret, get_signing_key

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
        status.HTTP_422_UNPROCESSABLE_ENTITY: _LOGIN_422,
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
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
    return LoginResponse(token=token, camarero=camarero, qr=qr)


@router.post(
    "/negocio/registro",
    response_model=RegistroNegocioResponse,
    status_code=status.HTTP_201_CREATED,
)
def registrar_negocio(
    payload: RegistroNegocioRequest, db: Session = Depends(get_db)
) -> RegistroNegocioResponse:
    if payload.camarero_vinculado_id is not None and db.get(
        Camarero, payload.camarero_vinculado_id
    ) is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=CAMARERO_NOT_FOUND,
            detail="Camarero no encontrado",
        )
    cuenta = CuentaNegocio(
        nombre_mostrar=payload.nombre_mostrar.strip(),
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        camarero_vinculado_id=payload.camarero_vinculado_id,
    )
    db.add(cuenta)
    try:
        db.commit()
        db.refresh(cuenta)
    except IntegrityError as exc:
        db.rollback()
        if "cuentas_negocio_email_key" in str(exc.orig):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=NEGOCIO_EMAIL_ALREADY_REGISTERED,
                detail="Ya existe una cuenta de negocio con ese email",
            )
        raise
    return RegistroNegocioResponse(id=cuenta.id)


@router.post("/negocio/login", response_model=LoginNegocioResponse)
def login_negocio(
    payload: LoginRequest, db: Session = Depends(get_db)
) -> LoginNegocioResponse:
    cuenta = db.query(CuentaNegocio).filter_by(email=payload.email.lower()).one_or_none()
    if cuenta is None or not verify_password(payload.password, cuenta.password_hash):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=NEGOCIO_INVALID_CREDENTIALS,
            detail="Email o contraseña de negocio incorrectos",
        )
    token = create_business_access_token(cuenta.id, get_session_secret(db))
    return LoginNegocioResponse(token=token, cuenta=cuenta)


@router.delete("/negocio/me", response_model=SupresionResponse)
def suprimir_negocio(
    payload: SupresionNegocioRequest,
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> SupresionResponse:
    if not verify_password(payload.password, cuenta.password_hash):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=NEGOCIO_INVALID_CREDENTIALS,
            detail="Contraseña de negocio incorrecta",
        )
    db.delete(cuenta)
    db.commit()
    return SupresionResponse(status="borrada")
