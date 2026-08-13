import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CredencialEstado(str, enum.Enum):
    activa = "activa"
    revocada = "revocada"


class MembresiaRol(str, enum.Enum):
    dueno = "dueno"
    staff = "staff"


class MembresiaEstado(str, enum.Enum):
    activa = "activa"
    revocada = "revocada"


class AppConfig(Base):
    __tablename__ = "app_config"

    clave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Camarero(Base):
    __tablename__ = "camareros"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(32), unique=True)
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
    membresias: Mapped[list["Membresia"]] = relationship(
        back_populates="camarero", cascade="all, delete-orphan"
    )
    cuentas_negocio_vinculadas: Mapped[list["CuentaNegocio"]] = relationship(
        back_populates="camarero_vinculado"
    )

    @property
    def foto_url(self) -> str | None:
        """URL relativa de la foto de perfil, o None si no hay."""
        if not self.foto_clave:
            return None
        return "/v1/camareros/me/foto"


class Credencial(Base):
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


class CuentaNegocio(Base):
    __tablename__ = "cuentas_negocio"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre_mostrar: Mapped[str] = mapped_column(String(200), nullable=False)
    camarero_vinculado_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("camareros.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    camarero_vinculado: Mapped[Camarero | None] = relationship(
        back_populates="cuentas_negocio_vinculadas"
    )
    establecimientos: Mapped[list["Establecimiento"]] = relationship(
        back_populates="cuenta_negocio", cascade="all, delete-orphan"
    )


class Establecimiento(Base):
    __tablename__ = "establecimientos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
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

    cuenta_negocio: Mapped[CuentaNegocio] = relationship(back_populates="establecimientos")
    membresias: Mapped[list["Membresia"]] = relationship(
        back_populates="establecimiento", cascade="all, delete-orphan"
    )


class Membresia(Base):
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
    camarero_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("camareros.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    camarero: Mapped[Camarero] = relationship(back_populates="membresias")
