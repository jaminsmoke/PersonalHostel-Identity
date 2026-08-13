from fastapi import APIRouter, Depends, HTTPException, status
import secrets
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_camarero, hash_password
from app.db import get_db
from app.models import Camarero, Credencial, CredencialEstado
from app.schemas import (
    CamareroPerfil,
    QrResponse,
    RegistroRequest,
    RegistroResponse,
)
from app.security import build_qr_payload, get_signing_key

router = APIRouter(prefix="/v1/camareros", tags=["camareros"])


@router.post(
    "/registro",
    response_model=RegistroResponse,
    status_code=status.HTTP_201_CREATED,
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
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un camarero con ese email",
            )
        raise

    qr = build_qr_payload(camarero.id, signing_key)
    return RegistroResponse(id=camarero.id, qr=qr)


@router.get("/me", response_model=CamareroPerfil)
def me(camarero: Camarero = Depends(get_current_camarero)) -> Camarero:
    return camarero


@router.get("/me/qr", response_model=QrResponse)
def me_qr(
    camarero: Camarero = Depends(get_current_camarero),
    db: Session = Depends(get_db),
) -> QrResponse:
    qr = build_qr_payload(camarero.id, get_signing_key(db))
    return QrResponse(qr=qr)
