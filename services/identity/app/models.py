import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import CamareroBase, NegocioBase


class CredencialEstado(str, enum.Enum):
    activa = "activa"
    revocada = "revocada"


class MembresiaRol(str, enum.Enum):
    dueno = "dueno"
    staff = "staff"


class MembresiaEstado(str, enum.Enum):
    activa = "activa"
    revocada = "revocada"


class InvitacionEstado(str, enum.Enum):
    pendiente = "pendiente"
    aceptada = "aceptada"
    revocada = "revocada"
    expirada = "expirada"


TIPOS_ESTABLECIMIENTO = ("bar", "restaurante", "cafeteria", "pub", "copas")


class EmailOutboxEstado(str, enum.Enum):
    pendiente = "pendiente"
    enviando = "enviando"
    enviado = "enviado"
    fallido = "fallido"


class ProductoDestino(str, enum.Enum):
    barra = "barra"
    cocina = "cocina"


class SyncAccion(str, enum.Enum):
    crear = "crear"
    actualizar = "actualizar"
    archivar = "archivar"


class SyncEstado(str, enum.Enum):
    aplicada = "aplicada"
    conflicto = "conflicto"
    rechazada = "rechazada"


class ConflictoEstado(str, enum.Enum):
    pendiente = "pendiente"
    aceptado = "aceptado"
    rechazado = "rechazado"


class DataOrigin(str, enum.Enum):
    """Procedencia inmutable de una entidad canónica."""

    real = "real"
    test = "test"
    demo = "demo"


# ── BD de profesionales ────────────────────────────────────────────────────


class AppConfig(CamareroBase):
    __tablename__ = "app_config"

    clave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Camarero(CamareroBase):
    __tablename__ = "camareros"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(200), nullable=False)
    nick: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(32), unique=True)
    data_origin: Mapped[DataOrigin] = mapped_column(
        Enum(DataOrigin, name="data_origin"),
        nullable=False,
        default=DataOrigin.real,
        server_default=DataOrigin.real.value,
        index=True,
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))
    foto_clave: Mapped[str | None] = mapped_column(String(255))
    foto_mimetype: Mapped[str | None] = mapped_column(String(64))
    foto_size: Mapped[int | None] = mapped_column(Integer)
    foto_actualizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credenciales: Mapped[list["Credencial"]] = relationship(
        back_populates="camarero", cascade="all, delete-orphan"
    )

    @property
    def foto_url(self) -> str | None:
        """URL relativa de la foto de perfil, o None si no hay."""
        if not self.foto_clave:
            return None
        return "/v1/camareros/me/foto"


class Credencial(CamareroBase):
    __tablename__ = "credenciales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    camarero_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("camareros.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    secreto: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    estado: Mapped[CredencialEstado] = mapped_column(
        Enum(CredencialEstado, name="credencial_estado"), nullable=False
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_revocacion: Mapped[str | None] = mapped_column(String(500))

    camarero: Mapped[Camarero] = relationship(back_populates="credenciales")


# ── BD de negocio ──────────────────────────────────────────────────────────


class CuentaNegocio(NegocioBase):
    __tablename__ = "cuentas_negocio"
    __table_args__ = (
        CheckConstraint(
            "tipo_establecimiento IS NULL OR tipo_establecimiento IN "
            "('bar', 'restaurante', 'cafeteria', 'pub', 'copas')",
            name="ck_cuentas_tipo_establecimiento",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_mostrar: Mapped[str] = mapped_column(String(200), nullable=False)
    data_origin: Mapped[DataOrigin] = mapped_column(
        Enum(DataOrigin, name="data_origin"),
        nullable=False,
        default=DataOrigin.real,
        server_default=DataOrigin.real.value,
        index=True,
    )
    tipo_establecimiento: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logo_clave: Mapped[str | None] = mapped_column(String(255))
    logo_mimetype: Mapped[str | None] = mapped_column(String(64))
    logo_size: Mapped[int | None] = mapped_column(Integer)
    logo_actualizada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # UUID plano: la FK real apunta a la BD de profesionales (otro servicio).
    camarero_vinculado_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    establecimientos: Mapped[list["Establecimiento"]] = relationship(
        back_populates="cuenta_negocio", cascade="all, delete-orphan"
    )
    invitaciones: Mapped[list["Invitacion"]] = relationship(
        back_populates="cuenta_negocio", cascade="all, delete-orphan"
    )

    @property
    def logo_url(self) -> str | None:
        """URL relativa del logo del negocio, o None si no hay."""
        if not self.logo_clave:
            return None
        return "/v1/auth/negocio/me/logo"


class Establecimiento(NegocioBase):
    __tablename__ = "establecimientos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    data_origin: Mapped[DataOrigin] = mapped_column(
        Enum(DataOrigin, name="data_origin"),
        nullable=False,
        default=DataOrigin.real,
        server_default=DataOrigin.real.value,
        index=True,
    )
    cuenta_negocio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cuentas_negocio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sync_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )

    cuenta_negocio: Mapped[CuentaNegocio] = relationship(back_populates="establecimientos")
    membresias: Mapped[list["Membresia"]] = relationship(
        back_populates="establecimiento", cascade="all, delete-orphan"
    )
    invitaciones: Mapped[list["Invitacion"]] = relationship(
        back_populates="establecimiento", cascade="all, delete-orphan"
    )
    layout: Mapped["LayoutEstablecimiento | None"] = relationship(
        back_populates="establecimiento", cascade="all, delete-orphan"
    )
    productos: Mapped[list["ProductoCatalogo"]] = relationship(
        back_populates="establecimiento", cascade="all, delete-orphan"
    )


class ProductoCatalogo(NegocioBase):
    __tablename__ = "productos_catalogo"
    __table_args__ = (
        CheckConstraint("precio_centimos >= 0", name="ck_producto_precio_no_negativo"),
        CheckConstraint("revision > 0", name="ck_producto_revision_positiva"),
        Index(
            "ix_productos_catalogo_activos",
            "establecimiento_id",
            "destino",
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    data_origin: Mapped[DataOrigin] = mapped_column(
        Enum(DataOrigin, name="data_origin"),
        nullable=False,
        default=DataOrigin.real,
        server_default=DataOrigin.real.value,
        index=True,
    )
    categoria: Mapped[str] = mapped_column(String(100), nullable=False)
    destino: Mapped[ProductoDestino] = mapped_column(
        Enum(ProductoDestino, name="producto_destino"), nullable=False
    )
    precio_centimos: Mapped[int] = mapped_column(Integer, nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    disponible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    establecimiento: Mapped[Establecimiento] = relationship(back_populates="productos")


class OperacionSync(NegocioBase):
    __tablename__ = "operaciones_sync"
    __table_args__ = (
        Index(
            "ix_operaciones_sync_change_feed",
            "establecimiento_id",
            "global_revision",
            postgresql_where=text("global_revision IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[SyncAccion] = mapped_column(
        Enum(SyncAccion, name="sync_accion"), nullable=False
    )
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    client_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    estado: Mapped[SyncEstado] = mapped_column(
        Enum(SyncEstado, name="sync_estado"), nullable=False
    )
    global_revision: Mapped[int | None] = mapped_column(BigInteger)
    result_snapshot: Mapped[dict | None] = mapped_column(JSONB)


class ConflictoSync(NegocioBase):
    __tablename__ = "conflictos_sync"
    __table_args__ = (
        Index(
            "ix_conflictos_sync_pendientes",
            "establecimiento_id",
            "created_at",
            postgresql_where=text("estado = 'pendiente'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    operacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operaciones_sync.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    canonical_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    canonical_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    proposed_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    estado: Mapped[ConflictoEstado] = mapped_column(
        Enum(ConflictoEstado, name="conflicto_estado"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class NotificacionNegocio(NegocioBase):
    __tablename__ = "notificaciones_negocio"
    __table_args__ = (
        Index(
            "ix_notificaciones_negocio_no_leidas",
            "establecimiento_id",
            "created_at",
            postgresql_where=text("read_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conflicto_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conflictos_sync.id", ondelete="SET NULL")
    )
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LayoutEstablecimiento(NegocioBase):
    """Copia de respaldo (DR) del layout del mapa: salas y mesas tal cual las
    serializa Bar. Identity no interpreta el layout; solo lo guarda y lo devuelve.
    Fuente de verdad: Bar. Una fila por establecimiento.
    """

    __tablename__ = "layouts_establecimiento"

    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    salas: Mapped[list] = mapped_column(JSONB, nullable=False)
    mesas: Mapped[list] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    establecimiento: Mapped[Establecimiento] = relationship(back_populates="layout")


class Membresia(NegocioBase):
    __tablename__ = "membresias"
    __table_args__ = (
        UniqueConstraint(
            "establecimiento_id", "camarero_id", name="uq_membresia_establecimiento_camarero"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # UUID plano: el camarero vive en la BD de profesionales (otro servicio).
    camarero_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    rol: Mapped[MembresiaRol] = mapped_column(
        Enum(MembresiaRol, name="membresia_rol"), nullable=False
    )
    estado: Mapped[MembresiaEstado] = mapped_column(
        Enum(MembresiaEstado, name="membresia_estado"), nullable=False
    )
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    establecimiento: Mapped[Establecimiento] = relationship(back_populates="membresias")


class Invitacion(NegocioBase):
    __tablename__ = "invitaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    establecimiento_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cuenta_negocio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cuentas_negocio.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_objetivo: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    rol: Mapped[MembresiaRol] = mapped_column(
        Enum(MembresiaRol, name="membresia_rol"), nullable=False
    )
    estado: Mapped[InvitacionEstado] = mapped_column(
        Enum(InvitacionEstado, name="invitacion_estado"), nullable=False
    )
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    aceptada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    establecimiento: Mapped[Establecimiento] = relationship(back_populates="invitaciones")
    cuenta_negocio: Mapped[CuentaNegocio] = relationship(back_populates="invitaciones")
    outbox: Mapped[list["EmailOutbox"]] = relationship(
        back_populates="invitacion", cascade="all, delete-orphan"
    )


class EmailOutbox(NegocioBase):
    __tablename__ = "email_outbox"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    invitacion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invitaciones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    destinatario: Mapped[str] = mapped_column(String(320), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    estado: Mapped[EmailOutboxEstado] = mapped_column(
        Enum(EmailOutboxEstado, name="email_outbox_estado"), nullable=False
    )
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ultimo_error: Mapped[str | None] = mapped_column(String(1000))
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    invitacion: Mapped[Invitacion | None] = relationship(back_populates="outbox")
