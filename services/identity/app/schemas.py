import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegistroRequest(BaseModel):
    """Datos de alta de un camarero."""

    nombre: str = Field(..., min_length=1, max_length=100, examples=["Ana"])
    apellidos: str = Field(..., min_length=1, max_length=200, examples=["García"])
    email: EmailStr = Field(..., examples=["ana@example.com"])
    telefono: str | None = Field(default=None, max_length=32, examples=["+34600000000"])
    password: str = Field(..., min_length=8, max_length=128, examples=["contraseña-mín-8"])


class RegistroResponse(BaseModel):
    """Resultado del alta: id del camarero y payload del QR permanente."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    qr: str = Field(..., examples=["phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"])


class CamareroPerfil(BaseModel):
    """Perfil público del camarero para la sesión."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    nombre: str = Field(..., examples=["Ana"])
    apellidos: str = Field(..., examples=["García"])
    email: str = Field(..., examples=["ana@example.com"])
    telefono: str | None = Field(default=None, examples=["+34600000000"])
    foto_url: str | None = Field(default=None, examples=["/v1/camareros/me/foto"])


class LoginRequest(BaseModel):
    """Credenciales para recuperar la sesión y el QR tras reinstalar."""

    email: EmailStr = Field(..., examples=["ana@example.com"])
    password: str = Field(..., examples=["contraseña-mín-8"])


class LoginResponse(BaseModel):
    """Sesión JWT, perfil y QR de la credencial activa."""

    token: str = Field(..., examples=["<jwt>"])
    camarero: CamareroPerfil
    qr: str = Field(..., examples=["phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"])


class QrResponse(BaseModel):
    """Payload para pintar el QR permanente."""

    qr: str = Field(..., examples=["phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"])


class RevocarRequest(BaseModel):
    """Motivo opcional de la revocación."""

    motivo: str | None = Field(default=None, max_length=500, examples=["tablet perdido"])


class RevocarResponse(BaseModel):
    """Estado tras revocar la credencial activa."""

    status: str = Field(..., examples=["revocada"])


class ErrorResponse(BaseModel):
    """Respuesta de error con código estable y mensaje en español."""

    code: str = Field(..., examples=["identity.credential_revoked"])
    detail: str | list[str] = Field(..., examples=["Clave revocada. Renueva la clave"])


class FotoResponse(BaseModel):
    """Estado de la foto de perfil tras subirla o borrarla."""

    foto_url: str | None = Field(default=None, examples=["/v1/camareros/me/foto"])


class SupresionRequest(BaseModel):
    """Confirmación (password) para ejercer el derecho de supresión."""

    password: str = Field(..., examples=["contraseña-mín-8"])


class SupresionResponse(BaseModel):
    """Resultado del borrado de la cuenta."""

    status: str = Field(..., examples=["borrada"])


class CuentaNegocioPerfil(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre_mostrar: str
    camarero_vinculado_id: uuid.UUID | None = None


class RegistroNegocioRequest(BaseModel):
    nombre_mostrar: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    camarero_vinculado_id: uuid.UUID | None = None


class RegistroNegocioResponse(BaseModel):
    id: uuid.UUID


class LoginNegocioResponse(BaseModel):
    token: str
    cuenta: CuentaNegocioPerfil


class EstablecimientoCreateRequest(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)


class EstablecimientoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    cuenta_negocio_id: uuid.UUID


class EstablecimientoMembresiaResponse(EstablecimientoResponse):
    rol: str


class MembresiaCreateRequest(BaseModel):
    camarero_id: uuid.UUID
    rol: str = Field(default="staff", pattern="^(dueno|staff)$")


class MembresiaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    establecimiento_id: uuid.UUID
    camarero_id: uuid.UUID
    rol: str
    estado: str


class SupresionNegocioRequest(BaseModel):
    password: str
