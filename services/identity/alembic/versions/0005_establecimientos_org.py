"""cuentas de negocio, establecimientos y membresías N:N

Revision ID: 0005_establecimientos_org
Revises: 0004_camarero_foto
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_establecimientos_org"
down_revision: Union[str, None] = "0004_camarero_foto"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    membresia_rol = postgresql.ENUM("dueno", "staff", name="membresia_rol", create_type=False)
    membresia_estado = postgresql.ENUM(
        "activa", "revocada", name="membresia_estado", create_type=False
    )
    membresia_rol.create(op.get_bind(), checkfirst=True)
    membresia_estado.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "cuentas_negocio",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("nombre_mostrar", sa.String(length=200), nullable=False),
        sa.Column("camarero_vinculado_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["camarero_vinculado_id"], ["camareros.id"], ondelete="SET NULL"),
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
        "membresias",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("camarero_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rol", membresia_rol, nullable=False),
        sa.Column("estado", membresia_estado, nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["camarero_id"], ["camareros.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("establecimiento_id", "camarero_id", name="uq_membresia_establecimiento_camarero"),
    )
    op.create_index("ix_membresias_establecimiento_id", "membresias", ["establecimiento_id"])
    op.create_index("ix_membresias_camarero_id", "membresias", ["camarero_id"])


def downgrade() -> None:
    op.drop_index("ix_membresias_camarero_id", table_name="membresias")
    op.drop_index("ix_membresias_establecimiento_id", table_name="membresias")
    op.drop_table("membresias")
    op.drop_index("ix_establecimientos_cuenta_negocio_id", table_name="establecimientos")
    op.drop_table("establecimientos")
    op.drop_index("ix_cuentas_negocio_camarero_vinculado_id", table_name="cuentas_negocio")
    op.drop_table("cuentas_negocio")
    op.execute("DROP TYPE IF EXISTS membresia_estado")
    op.execute("DROP TYPE IF EXISTS membresia_rol")
