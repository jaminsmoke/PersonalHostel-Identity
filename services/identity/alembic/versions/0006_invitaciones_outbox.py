"""invitaciones seguras y outbox de email

Revision ID: 0006_invitaciones_outbox
Revises: 0005_establecimientos_org
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_invitaciones_outbox"
down_revision: Union[str, None] = "0005_establecimientos_org"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    invitacion_estado = postgresql.ENUM(
        "pendiente",
        "aceptada",
        "revocada",
        "expirada",
        name="invitacion_estado",
        create_type=False,
    )
    email_outbox_estado = postgresql.ENUM(
        "pendiente",
        "enviando",
        "enviado",
        "fallido",
        name="email_outbox_estado",
        create_type=False,
    )
    invitacion_estado.create(op.get_bind(), checkfirst=True)
    email_outbox_estado.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "invitaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cuenta_negocio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email_objetivo", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("rol", postgresql.ENUM("dueno", "staff", name="membresia_rol", create_type=False), nullable=False),
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
    op.execute("DROP TYPE IF EXISTS email_outbox_estado")
    op.execute("DROP TYPE IF EXISTS invitacion_estado")
