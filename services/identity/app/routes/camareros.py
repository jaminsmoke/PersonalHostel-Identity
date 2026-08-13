from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
import secrets
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_credencial_activa, get_current_camarero, hash_password
from app.db import get_db
from app.errors import CREDENTIAL_REVOKED, EMAIL_ALREADY_REGISTERED, ApiError
from app.models import Camarero, Credencial, CredencialEstado
from app.schemas import (
    CamareroPerfil,
    ErrorResponse,
    QrResponse,
    RegistroRequest,
    RegistroResponse,
    RevocarRequest,
    RevocarResponse,
)
from app.security import build_qr_payload, get_signing_key

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
def registrar_camarero(payload: RegistroRequest, db: Session = Depends(get_db)) -> RegistroResponse:
    camarero = Camarero(
        nombre=payload.nombre.strip(),
        apellidos=payload.apellidos.strip(),
        email=payload.email.lower(),
        telefono=payload.telefono.strip() if payload.telefono else None,
        password_hash=hash_password(payload.password),
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
            )
        raise

    qr = build_qr_payload(camarero.id, credencial.id, signing_key)
    return RegistroResponse(id=camarero.id, qr=qr)


@router.get(
    "/me",
    response_model=CamareroPerfil,
    responses={status.HTTP_401_UNAUTHORIZED: _UNAUTHORIZED},
)
def me(camarero: Camarero = Depends(get_current_camarero)) -> Camarero:
    return camarero


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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
) -> QrResponse:
    now = datetime.now(timezone.utc)
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
    db: Session = Depends(get_db),
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
    credencial.revocada_en = datetime.now(timezone.utc)
    credencial.motivo_revocacion = motivo
    db.commit()
    return RevocarResponse(status="revocada")
