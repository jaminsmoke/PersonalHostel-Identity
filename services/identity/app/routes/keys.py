from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_camarero_db
from app.schemas import QrPublicKeyResponse
from app.security import qr_public_key_payload

router = APIRouter(prefix="/v1/keys", tags=["keys"])


@router.get("/qr", response_model=QrPublicKeyResponse)
def obtener_clave_publica_qr(db: Session = Depends(get_camarero_db)) -> dict[str, str]:
    return qr_public_key_payload(db)
