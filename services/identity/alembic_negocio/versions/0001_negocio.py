"""esquema inicial de negocio: cuentas, establecimientos, membresías, invitaciones y outbox

Revision ID: 0001_negocio
Revises:
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_negocio"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    membresia_rol = postgresql.ENUM("dueno", "staff", name="membresia_rol", create_type=False)
    membresia_estado = postgresql.ENUM(
        "activa", "revocada", name="membresia_estado", create_type=False
    )
    invitacion_estado = postgresql.ENUM(
        "pendiente", "aceptada", "revocada", "expirada",
        name="invitacion_estado", create_type=False,
    )
    email_outbox_estado = postgresql.ENUM(
        "pendiente", "enviando", "enviado", "fallido",
        name="email_outbox_estado", create_type=False,
    )
    for enum in (membresia_rol, membresia_estado, invitacion_estado, email_outbox_estado):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "cuentas_negocio",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nombre_mostrar", sa.String(length=200), nullable=False),
        sa.Column("tipo_establecimiento", sa.String(length=50), nullable=True),
        sa.Column("logo_clave", sa.String(length=255), nullable=True),
        sa.Column("logo_mimetype", sa.String(length=64), nullable=True),
        sa.Column("logo_size", sa.Integer(), nullable=True),
        sa.Column("logo_actualizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("camarero_vinculado_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "tipo_establecimiento IS NULL OR tipo_establecimiento IN "
            "('bar', 'restaurante', 'cafeteria', 'pub', 'copas')",
            name="ck_cuentas_tipo_establecimiento",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(
        "ix_cuentas_negocio_camarero_vinculado_id",
        "cuentas_negocio",
        ["camarero_vinculado_id"],
    )

    op.create_table(
        "establecimientos",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("cuenta_negocio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["cuenta_negocio_id"], ["cuentas_negocio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_establecimientos_cuenta_negocio_id", "establecimientos", ["cuenta_negocio_id"]
    )

    op.create_table(
        "layouts_establecimiento",
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("salas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mesas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("establecimiento_id"),
    )

    op.create_table(
        "membresias",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camarero_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rol", membresia_rol, nullable=False),
        sa.Column("estado", membresia_estado, nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("establecimiento_id", "camarero_id", name="uq_membresia_establecimiento_camarero"),
    )
    op.create_index("ix_membresias_establecimiento_id", "membresias", ["establecimiento_id"])
    op.create_index("ix_membresias_camarero_id", "membresias", ["camarero_id"])

    op.create_table(
        "invitaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cuenta_negocio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_objetivo", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("rol", membresia_rol, nullable=False),
        sa.Column("estado", invitacion_estado, nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("aceptada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cuenta_negocio_id"], ["cuentas_negocio.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_invitaciones_establecimiento_id", "invitaciones", ["establecimiento_id"])
    op.create_index("ix_invitaciones_cuenta_negocio_id", "invitaciones", ["cuenta_negocio_id"])
    op.create_index("ix_invitaciones_email_objetivo", "invitaciones", ["email_objetivo"])

    op.create_table(
        "email_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invitacion_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("destinatario", sa.String(length=320), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("estado", email_outbox_estado, nullable=False),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ultimo_error", sa.String(length=1000), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("enviado_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["invitacion_id"], ["invitaciones.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_outbox_invitacion_id", "email_outbox", ["invitacion_id"])


def downgrade() -> None:
    op.drop_index("ix_email_outbox_invitacion_id", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_index("ix_invitaciones_email_objetivo", table_name="invitaciones")
    op.drop_index("ix_invitaciones_cuenta_negocio_id", table_name="invitaciones")
    op.drop_index("ix_invitaciones_establecimiento_id", table_name="invitaciones")
    op.drop_table("invitaciones")
    op.drop_index("ix_membresias_camarero_id", table_name="membresias")
    op.drop_index("ix_membresias_establecimiento_id", table_name="membresias")
    op.drop_table("membresias")
    op.drop_table("layouts_establecimiento")
    op.drop_index("ix_establecimientos_cuenta_negocio_id", table_name="establecimientos")
    op.drop_table("establecimientos")
    op.drop_index("ix_cuentas_negocio_camarero_vinculado_id", table_name="cuentas_negocio")
    op.drop_table("cuentas_negocio")
    op.execute("DROP TYPE IF EXISTS email_outbox_estado")
    op.execute("DROP TYPE IF EXISTS invitacion_estado")
    op.execute("DROP TYPE IF EXISTS membresia_estado")
    op.execute("DROP TYPE IF EXISTS membresia_rol")
