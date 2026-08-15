import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    get_credencial_activa,
    get_current_camarero,
    hash_password,
    verify_password,
)
from app.data_origin import ensure_data_origin_allowed
from app.db import get_camarero_db
from app.errors import (
    CREDENTIAL_REVOKED,
    EMAIL_ALREADY_REGISTERED,
    FOTO_INEXISTENTE,
    FOTO_INVALIDA,
    PASSWORD_INCORRECTA,
    ApiError,
)
from app.images import MAX_INPUT_BYTES, FotoInvalida, normalizar_foto
from app.internal import get_negocio_internal
from app.models import (
    Camarero,
    Credencial,
    CredencialEstado,
)
from app.schemas import (
    CamareroPerfil,
    ErrorResponse,
    EstablecimientoMembresiaResponse,
    FotoResponse,
    InvitacionAcceptResponse,
    InvitacionCamareroResponse,
    PerfilUpdateRequest,
    QrResponse,
    RegistroRequest,
    RegistroResponse,
    RevocarRequest,
    RevocarResponse,
    SupresionRequest,
    SupresionResponse,
)
from app.security import build_qr_payload, get_signing_key
from app.storage import get_foto_storage

router = APIRouter(prefix="/v1/camareros", tags=["camareros"])

CLAVE_REVOCADA = "Clave revocada. Renueva la clave"

_UNAUTHORIZED = {
    "model": ErrorResponse,
    "description": "Token de sesión inválido o caducado.",
}
_CONFLICT = {
    "model": ErrorResponse,
    "description": "Cuenta sin credencial activa (revocada).",
}
_VALIDATION = {
    "model": ErrorResponse,
    "description": "Cuerpo de la petición inválido.",
}


@router.post(
    "/registro",
    response_model=RegistroResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Ya existe un camarero con ese email.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: _VALIDATION,
    },
)
def registrar_camarero(
    payload: RegistroRequest, db: Session = Depends(get_camarero_db)
) -> RegistroResponse:
    ensure_data_origin_allowed(payload.data_origin)
    camarero = Camarero(
        nombre=payload.nombre.strip(),
        apellidos=payload.apellidos.strip(),
        nick=payload.nick.strip() if payload.nick else None,
        email=payload.email.lower(),
        telefono=payload.telefono.strip() if payload.telefono else None,
        password_hash=hash_password(payload.password),
        data_origin=payload.data_origin,
    )
    credencial = Credencial(
        secreto=secrets.token_urlsafe(32),
        estado=CredencialEstado.activa,
    )

    signing_key = get_signing_key(db)

    try:
        db.add(camarero)
        db.flush()
        credencial.camarero_id = camarero.id
        db.add(credencial)
        db.commit()
        db.refresh(credencial)
    except IntegrityError as exc:
        db.rollback()
        if "camareros_email_key" in str(exc.orig):
            raise ApiError(
                status_code=status.HTTP_409_CONFLICT,
                code=EMAIL_ALREADY_REGISTERED,
                detail="Ya existe un camarero con ese email",
            ) from exc
        raise

    qr = build_qr_payload(camarero.id, credencial.id, signing_key)
    return RegistroResponse(id=camarero.id, qr=qr, data_origin=camarero.data_origin)


@router.get(
    "/me",
    response_model=CamareroPerfil,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def me(camarero: Camarero = Depends(get_current_camarero)) -> Camarero:
    return camarero


@router.patch(
    "/me",
    response_model=CamareroPerfil,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def actualizar_me(
    payload: PerfilUpdateRequest,
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> Camarero:
    camarero.nick = payload.nick.strip()
    db.commit()
    db.refresh(camarero)
    return camarero


@router.get(
    "/me/establecimientos",
    response_model=list[EstablecimientoMembresiaResponse],
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def mis_establecimientos(
    camarero: Camarero = Depends(get_current_camarero),
) -> list[dict]:
    return get_negocio_internal().establecimientos_de(camarero.id)


@router.get(
    "/me/invitaciones",
    response_model=list[InvitacionCamareroResponse],
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def mis_invitaciones(
    camarero: Camarero = Depends(get_current_camarero),
) -> list[dict]:
    return get_negocio_internal().invitaciones_de(camarero.id)


@router.post(
    "/me/invitaciones/{invitacion_id}/aceptar",
    response_model=InvitacionAcceptResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_410_GONE: {"model": ErrorResponse},
    },
)
def aceptar_invitacion_me(
    invitacion_id: uuid.UUID,
    camarero: Camarero = Depends(get_current_camarero),
) -> dict:
    return get_negocio_internal().aceptar_invitacion(invitacion_id, camarero.id)


@router.get(
    "/me/qr",
    response_model=QrResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_409_CONFLICT: _CONFLICT,
    },
)
def me_qr(
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> QrResponse:
    credencial = get_credencial_activa(db, camarero.id)
    if credencial is None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CREDENTIAL_REVOKED,
            detail=CLAVE_REVOCADA,
        )
    qr = build_qr_payload(camarero.id, credencial.id, get_signing_key(db))
    return QrResponse(qr=qr)


@router.post(
    "/me/renovar",
    response_model=QrResponse,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def renovar(
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> QrResponse:
    now = datetime.now(UTC)
    activas = (
        db.query(Credencial)
        .filter_by(camarero_id=camarero.id, estado=CredencialEstado.activa)
        .all()
    )
    for cred in activas:
        cred.estado = CredencialEstado.revocada
        cred.revocada_en = now
        cred.motivo_revocacion = "renovada"

    nueva = Credencial(
        camarero_id=camarero.id,
        secreto=secrets.token_urlsafe(32),
        estado=CredencialEstado.activa,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)

    qr = build_qr_payload(camarero.id, nueva.id, get_signing_key(db))
    return QrResponse(qr=qr)


@router.post(
    "/me/revocar",
    response_model=RevocarResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_409_CONFLICT: _CONFLICT,
        status.HTTP_422_UNPROCESSABLE_ENTITY: _VALIDATION,
    },
)
def revocar(
    payload: RevocarRequest | None = None,
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> RevocarResponse:
    credencial = get_credencial_activa(db, camarero.id)
    if credencial is None:
        raise ApiError(
            status_code=status.HTTP_409_CONFLICT,
            code=CREDENTIAL_REVOKED,
            detail=CLAVE_REVOCADA,
        )

    motivo = "revocada"
    if payload is not None and payload.motivo:
        motivo = payload.motivo.strip() or "revocada"

    credencial.estado = CredencialEstado.revocada
    credencial.revocada_en = datetime.now(UTC)
    credencial.motivo_revocacion = motivo
    db.commit()
    return RevocarResponse(status="revocada")


_FOTO_200 = {
    "description": "Imagen de perfil (WebP).",
    "content": {"image/webp": {}},
}
_NOT_FOUND = {
    "model": ErrorResponse,
    "description": "El camarero no tiene foto de perfil.",
}


@router.post(
    "/me/foto",
    response_model=FotoResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_ENTITY: _VALIDATION,
    },
)
async def subir_foto(
    foto: UploadFile = File(...),
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> FotoResponse:
    data = await foto.read(MAX_INPUT_BYTES + 1)
    try:
        payload, mimetype, size = normalizar_foto(data)
    except FotoInvalida as exc:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code=FOTO_INVALIDA,
            detail=str(exc),
        ) from exc

    storage = get_foto_storage()
    if camarero.foto_clave:
        storage.borrar(camarero.foto_clave)

    clave = storage.guardar(camarero.id, payload, "webp")
    camarero.foto_clave = clave
    camarero.foto_mimetype = mimetype
    camarero.foto_size = size
    camarero.foto_actualizada_en = datetime.now(UTC)
    db.commit()
    return FotoResponse(foto_url="/v1/camareros/me/foto")


@router.get(
    "/me/foto",
    responses={
        status.HTTP_200_OK: _FOTO_200,
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_404_NOT_FOUND: _NOT_FOUND,
    },
)
def obtener_foto(camarero: Camarero = Depends(get_current_camarero)) -> Response:
    if not camarero.foto_clave:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="El camarero no tiene foto de perfil",
        )
    data = get_foto_storage().leer(camarero.foto_clave)
    if data is None:
        raise ApiError(
            status_code=status.HTTP_404_NOT_FOUND,
            code=FOTO_INEXISTENTE,
            detail="La foto no está disponible",
        )
    return Response(
        content=data,
        media_type=camarero.foto_mimetype or "image/webp",
        headers={
            "Cache-Control": "private, max-age=86400",
            "ETag": f'"{camarero.foto_clave}"',
        },
    )


@router.delete(
    "/me/foto",
    response_model=FotoResponse,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def borrar_foto(
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> FotoResponse:
    if camarero.foto_clave:
        get_foto_storage().borrar(camarero.foto_clave)
    camarero.foto_clave = None
    camarero.foto_mimetype = None
    camarero.foto_size = None
    camarero.foto_actualizada_en = None
    db.commit()
    return FotoResponse(foto_url=None)


@router.delete(
    "/me",
    response_model=SupresionResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED,
        status.HTTP_422_UNPROCESSABLE_ENTITY: _VALIDATION,
    },
)
def suprimir_cuenta(
    payload: SupresionRequest,
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_camarero_db),
) -> SupresionResponse:
    if camarero.password_hash is None or not verify_password(
        payload.password, camarero.password_hash
    ):
        raise ApiError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=PASSWORD_INCORRECTA,
            detail="Contraseña incorrecta",
        )

    foto_clave = camarero.foto_clave
    if foto_clave:
        get_foto_storage().borrar(foto_clave)

    db.delete(camarero)
    db.commit()
    return SupresionResponse(status="borrada")
