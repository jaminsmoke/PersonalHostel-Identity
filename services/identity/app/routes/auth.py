from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
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
    FOTO_INEXISTENTE,
    FOTO_INVALIDA,
    INVALID_CREDENTIALS,
    NEGOCIO_EMAIL_ALREADY_REGISTERED,
    NEGOCIO_INVALID_CREDENTIALS,
    ApiError,
)
from app.images import MAX_INPUT_BYTES, FotoInvalida, normalizar_foto
from app.models import Camarero, CuentaNegocio
from app.schemas import (
    CuentaNegocioPerfil,
    ErrorResponse,
    LoginNegocioResponse,
    LoginRequest,
    LoginResponse,
    LogoNegocioResponse,
    RegistroNegocioRequest,
    RegistroNegocioResponse,
    SupresionNegocioRequest,
    SupresionResponse,
)
from sqlalchemy.exc import IntegrityError
from app.security import build_qr_payload, get_session_secret, get_signing_key
from app.storage import get_foto_storage

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
        tipo_establecimiento=payload.tipo_establecimiento,
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
    logo_clave = cuenta.logo_clave
    if logo_clave:
        get_foto_storage().borrar(logo_clave)
    db.delete(cuenta)
    db.commit()
    return SupresionResponse(status="borrada")


@router.post(
    "/negocio/me/logo",
    response_model=LogoNegocioResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    },
)
async def subir_logo(
    logo: UploadFile = File(...),
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> LogoNegocioResponse:
    data = await logo.read(MAX_INPUT_BYTES + 1)
    try:
        payload, mimetype, size = normalizar_foto(data)
    except FotoInvalida as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=FOTO_INVALIDA,
            detail=str(exc),
        )

    storage = get_foto_storage()
    if cuenta.logo_clave:
        storage.borrar(cuenta.logo_clave)

    clave = storage.guardar(cuenta.id, payload, "webp")
    cuenta.logo_clave = clave
    cuenta.logo_mimetype = mimetype
    cuenta.logo_size = size
    cuenta.logo_actualizada_en = datetime.now(timezone.utc)
    db.commit()
    return LogoNegocioResponse(logo_url="/v1/auth/negocio/me/logo")


@router.get(
    "/negocio/me/logo",
    responses={
        status.HTTP_200_OK: {"content": {"image/webp": {}}},
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def obtener_logo(
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
) -> Response:
    if not cuenta.logo_clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El negocio no tiene logo",
        )
    data = get_foto_storage().leer(cuenta.logo_clave)
    if data is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El logo no está disponible",
        )
    return Response(
        content=data,
        media_type=cuenta.logo_mimetype or "image/webp",
        headers={
            "Cache-Control": "private, max-age=86400",
            "ETag": f'"{cuenta.logo_clave}"',
        },
    )


@router.delete(
    "/negocio/me/logo",
    response_model=LogoNegocioResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def borrar_logo(
    cuenta: CuentaNegocio = Depends(get_current_cuenta_negocio),
    db: Session = Depends(get_db),
) -> LogoNegocioResponse:
    if cuenta.logo_clave:
        get_foto_storage().borrar(cuenta.logo_clave)
    cuenta.logo_clave = None
    cuenta.logo_mimetype = None
    cuenta.logo_size = None
    cuenta.logo_actualizada_en = None
    db.commit()
    return LogoNegocioResponse(logo_url=None)
