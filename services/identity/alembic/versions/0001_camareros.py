"""esquema inicial de profesionales: camareros, credenciales y app_config

Revision ID: 0001_camareros
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_camareros"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    credencial_estado = postgresql.ENUM(
        "activa", "revocada", name="credencial_estado", create_type=False
    )
    credencial_estado.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "camareros",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("apellidos", sa.String(length=200), nullable=False),
        sa.Column("nick", sa.String(length=40), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("telefono", sa.String(length=32), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("foto_clave", sa.String(length=255), nullable=True),
        sa.Column("foto_mimetype", sa.String(length=64), nullable=True),
        sa.Column("foto_size", sa.Integer(), nullable=True),
        sa.Column("foto_actualizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("telefono"),
    )

    op.create_table(
        "credenciales",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("camarero_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("secreto", sa.String(length=255), nullable=False),
        sa.Column("estado", credencial_estado, nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_revocacion", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["camarero_id"], ["camareros.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secreto"),
    )
    op.create_index("ix_credenciales_camarero_id", "credenciales", ["camarero_id"])

    op.create_table(
        "app_config",
        sa.Column("clave", sa.String(length=100), nullable=False),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("clave"),
    )


def downgrade() -> None:
    op.drop_table("app_config")
    op.drop_index("ix_credenciales_camarero_id", table_name="credenciales")
    op.drop_table("credenciales")
    op.drop_table("camareros")

    credencial_estado = postgresql.ENUM(
        "activa", "revocada", name="credencial_estado", create_type=False
    )
    credencial_estado.drop(op.get_bind(), checkfirst=True)
