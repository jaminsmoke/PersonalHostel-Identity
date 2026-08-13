from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, verify_password
from app.db import get_db
from app.models import Camarero
from app.schemas import LoginRequest, LoginResponse
from app.security import build_qr_payload, get_session_secret, get_signing_key

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    camarero = db.query(Camarero).filter_by(email=payload.email.lower()).one_or_none()

    if camarero is None or camarero.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )
    if not verify_password(payload.password, camarero.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
        )

    secret = get_session_secret(db)
    token = create_access_token(camarero.id, secret)
    qr = build_qr_payload(camarero.id, get_signing_key(db))
    return LoginResponse(token=token, camarero=camarero, qr=qr)
