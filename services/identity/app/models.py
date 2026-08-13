import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class CredencialEstado(str, enum.Enum):
    activa = "activa"
    revocada = "revocada"


class Camarero(Base):
    __tablename__ = "camareros"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    credenciales: Mapped[list["Credencial"]] = relationship(
        back_populates="camarero", cascade="all, delete-orphan"
    )


class Credencial(Base):
    __tablename__ = "credenciales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    camarero_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("camareros.id"), nullable=False
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
