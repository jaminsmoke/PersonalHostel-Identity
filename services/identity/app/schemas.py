import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DataOrigin


class RegistroRequest(BaseModel):
    """Datos de alta de un camarero."""

    nombre: str = Field(..., min_length=1, max_length=100, examples=["Ana"])
    apellidos: str = Field(..., min_length=1, max_length=200, examples=["García"])
    email: EmailStr = Field(..., examples=["ana@example.com"])
    telefono: str | None = Field(default=None, max_length=32, examples=["+34600000000"])
    password: str = Field(..., min_length=8, max_length=128, examples=["contraseña-mín-8"])
    nick: str | None = Field(default=None, min_length=1, max_length=40, examples=["Anita"])
    data_origin: DataOrigin = Field(
        default=DataOrigin.real,
        description="Procedencia inmutable; test/demo requieren habilitación del entorno.",
    )


class RegistroResponse(BaseModel):
    """Resultado del alta: id del camarero y payload del QR permanente."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    qr: str = Field(..., examples=["phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"])
    ficha_url: str | None = Field(
        default=None, examples=["https://ficha.example/ficha?qr=phid1:..."]
    )
    data_origin: DataOrigin


class CamareroPerfil(BaseModel):
    """Perfil público del camarero para la sesión."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"])
    nombre: str = Field(..., examples=["Ana"])
    apellidos: str = Field(..., examples=["García"])
    email: str = Field(..., examples=["ana@example.com"])
    telefono: str | None = Field(default=None, examples=["+34600000000"])
    foto_url: str | None = Field(default=None, examples=["/v1/camareros/me/foto"])
    nick: str | None = Field(default=None, examples=["Anita"])
    data_origin: DataOrigin


class VisibilidadCamarero(BaseModel):
    """Visibilidad pública por campo (default: sensibles privados)."""

    nombre: bool = True
    apellidos: bool = True
    nick: bool = True
    email: bool = False
    telefono: bool = False
    foto: bool = False


class VisibilidadUpdateRequest(BaseModel):
    """Actualización parcial de visibilidad (solo los campos enviados)."""

    nombre: bool | None = None
    apellidos: bool | None = None
    nick: bool | None = None
    email: bool | None = None
    telefono: bool | None = None
    foto: bool | None = None


class CamareroFichaPublica(BaseModel):
    """Ficha pública del camarero: solo campos visibles (foto opt-in)."""

    camarero_id: uuid.UUID
    nombre: str
    apellidos: str
    nick: str | None = None
    email: str | None = None
    telefono: str | None = None
    foto_url: str | None = None


class PerfilUpdateRequest(BaseModel):
    """Campos editables de la cuenta desde Commander (no desde Bar)."""

    nick: str = Field(..., min_length=1, max_length=40, examples=["Anita"])


class LoginRequest(BaseModel):
    """Credenciales para recuperar la sesión y el QR tras reinstalar."""

    email: EmailStr = Field(..., examples=["ana@example.com"])
    password: str = Field(..., examples=["contraseña-mín-8"])


class LoginResponse(BaseModel):
    """Sesión JWT, perfil y QR de la credencial activa."""

    token: str = Field(..., examples=["<jwt>"])
    camarero: CamareroPerfil
    qr: str = Field(..., examples=["phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"])
    ficha_url: str | None = Field(
        default=None, examples=["https://ficha.example/ficha?qr=phid1:..."]
    )


class QrResponse(BaseModel):
    """Payload para pintar el QR permanente y su URL pública de ficha."""

    qr: str = Field(..., examples=["phid1:<camarero_id>:<credencial_id>:<firma-ed25519>"])
    ficha_url: str | None = Field(
        default=None, examples=["https://ficha.example/ficha?qr=phid1:..."]
    )


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
    tipo_establecimiento: str | None = None
    logo_url: str | None = None
    camarero_vinculado_id: uuid.UUID | None = None
    data_origin: DataOrigin


class RegistroNegocioRequest(BaseModel):
    nombre_mostrar: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    tipo_establecimiento: str | None = Field(
        default=None,
        pattern="^(bar|restaurante|cafeteria|pub|copas)$",
        description="Tipo de establecimiento del catálogo canónico.",
    )
    camarero_vinculado_id: uuid.UUID | None = None
    data_origin: DataOrigin = Field(
        default=DataOrigin.real,
        description="Procedencia inmutable; test/demo requieren habilitación del entorno.",
    )


class LogoNegocioResponse(BaseModel):
    logo_url: str | None


class RegistroNegocioResponse(BaseModel):
    id: uuid.UUID
    data_origin: DataOrigin


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
    data_origin: DataOrigin


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


class QrPublicKeyResponse(BaseModel):
    algorithm: str
    key_id: str
    public_key: str
    qr_prefix: str
    format: str


class QrMemberRequest(BaseModel):
    qr: str = Field(..., min_length=20, max_length=500)
    rol: str = Field(default="staff", pattern="^(dueno|staff)$")


class CamareroSearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    apellidos: str
    email: str
    nick: str | None = None
    data_origin: DataOrigin


class InvitacionCreateRequest(BaseModel):
    email: EmailStr
    rol: str = Field(default="staff", pattern="^(dueno|staff)$")


class InvitacionResponse(BaseModel):
    id: uuid.UUID
    establecimiento_id: uuid.UUID
    email: str
    rol: str
    estado: str
    expira_en: datetime
    creada_en: datetime


class InvitacionAcceptResponse(BaseModel):
    invitacion_id: uuid.UUID
    membresia: MembresiaResponse


class InvitacionCamareroResponse(BaseModel):
    """Invitación dirigida al camarero, con nombre del establecimiento."""

    id: uuid.UUID
    establecimiento_id: uuid.UUID
    establecimiento_nombre: str
    rol: str
    estado: str
    expira_en: datetime
    creada_en: datetime


class LayoutUpdateRequest(BaseModel):
    """Snapshot del layout que sube Bar: salas y mesas tal cual las serializa.
    Estructura interna no validada (copia de respaldo; Bar es la fuente)."""

    salas: list[Any] = Field(..., min_length=0)
    mesas: list[Any] = Field(..., min_length=0)


class LayoutResponse(BaseModel):
    """Copia de respaldo del layout de un establecimiento."""

    model_config = ConfigDict(from_attributes=True)

    establecimiento_id: uuid.UUID
    version: int
    salas: list[Any]
    mesas: list[Any]
    updated_at: datetime


class ProductoPayload(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    categoria: str = Field(..., min_length=1, max_length=100)
    destino: str = Field(..., pattern="^(barra|cocina)$")
    precio_centimos: int = Field(..., ge=0, le=2_147_483_647)
    moneda: str = Field(default="EUR", pattern="^[A-Z]{3}$")
    disponible: bool = True


class ProductoResponse(ProductoPayload):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    establecimiento_id: uuid.UUID
    data_origin: DataOrigin
    revision: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class CatalogoResponse(BaseModel):
    establecimiento_id: uuid.UUID
    revision: int
    server_time: datetime
    productos: list[ProductoResponse]


class OperacionSyncRequest(BaseModel):
    operation_id: uuid.UUID
    device_id: str = Field(..., min_length=1, max_length=200)
    aggregate_type: str = Field(default="producto", min_length=1, max_length=50)
    aggregate_id: uuid.UUID
    action: str = Field(..., pattern="^(crear|actualizar|archivar)$")
    base_revision: int = Field(default=0, ge=0)
    base_snapshot: dict[str, Any] | None = None
    payload: ProductoPayload | None = None
    client_created_at: datetime


class OperacionSyncResponse(BaseModel):
    operation_id: uuid.UUID
    estado: str
    aggregate_type: str
    aggregate_id: uuid.UUID
    action: str
    base_revision: int
    global_revision: int | None = None
    result_snapshot: dict[str, Any] | None = None
    conflict_id: uuid.UUID | None = None
    client_created_at: datetime
    server_received_at: datetime


class CambioSyncResponse(BaseModel):
    revision: int
    operation_id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    action: str
    snapshot: dict[str, Any]


class CambiosSyncResponse(BaseModel):
    establecimiento_id: uuid.UUID
    desde: int
    revision_actual: int
    cambios: list[CambioSyncResponse]


class ConflictoSyncResponse(BaseModel):
    id: uuid.UUID
    operation_id: uuid.UUID
    aggregate_type: str
    aggregate_id: uuid.UUID
    action: str
    base_revision: int
    canonical_revision: int
    base_snapshot: dict[str, Any] | None = None
    canonical_snapshot: dict[str, Any] | None = None
    proposed_snapshot: dict[str, Any] | None = None
    estado: str
    device_id: str
    client_created_at: datetime
    server_received_at: datetime
    created_at: datetime
    resolved_at: datetime | None = None


class ResolverConflictoRequest(BaseModel):
    decision: str = Field(..., pattern="^(aceptar|rechazar)$")
    expected_revision: int = Field(..., ge=0)


class NotificacionNegocioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    establecimiento_id: uuid.UUID
    conflicto_id: uuid.UUID | None = None
    tipo: str
    titulo: str
    mensaje: str
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None = None


class EnlacePublicoCreateRequest(BaseModel):
    """Alta de un enlace público para un establecimiento."""

    tipo: str = Field(..., pattern="^(ficha_negocio|carta)$")
    slug: str | None = Field(default=None, min_length=1, max_length=100, pattern="^[a-z0-9-]+$")


class EnlacePublicoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    establecimiento_id: uuid.UUID
    tipo: str
    slug: str
    estado: str
    expira_en: datetime | None = None


class EnlacePublicoResolucion(BaseModel):
    """Resolución pública de un enlace: tipo + destino (sin PII)."""

    tipo: str
    establecimiento_id: uuid.UUID


class EstablecimientoFichaPublica(BaseModel):
    """Establecimiento en la ficha pública del negocio (id + nombre)."""

    id: uuid.UUID
    nombre: str


class NegocioFichaPublica(BaseModel):
    """Ficha pública del negocio por enlace: solo campos públicos."""

    nombre: str
    tipo_establecimiento: str | None = None
    logo_url: str | None = None
    establecimientos: list[EstablecimientoFichaPublica]
