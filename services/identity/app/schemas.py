import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegistroRequest(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    apellidos: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    telefono: str | None = Field(default=None, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)


class RegistroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    qr: str


class CamareroPerfil(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    apellidos: str
    email: str
    telefono: str | None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    token: str
    camarero: CamareroPerfil
    qr: str


class QrResponse(BaseModel):
    qr: str


class RevocarRequest(BaseModel):
    motivo: str | None = Field(default=None, max_length=500)


class RevocarResponse(BaseModel):
    status: str
