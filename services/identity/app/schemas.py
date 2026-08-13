import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegistroRequest(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    apellidos: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    telefono: str | None = Field(default=None, max_length=32)


class RegistroResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    qr: str
