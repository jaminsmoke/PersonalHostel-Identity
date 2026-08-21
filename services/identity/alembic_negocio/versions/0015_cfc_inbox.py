"""jornada de local CFC, bandeja de pedidos y cursor

Revision ID: 0015_cfc_inbox
Revises: 0014_mesas_cfc
Create Date: 2026-08-21

La jornada es del establecimiento (no del camarero). Los pedidos se encolan
solo con jornada abierta; el horario corta la cola si el nodo desaparece
fuera de servicio.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0015_cfc_inbox"
down_revision: Union[str, None] = "0014_mesas_cfc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jornadas_cfc",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "abierta_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "ultimo_heartbeat",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"],
            ["establecimientos.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_jornadas_cfc_establecimiento_id",
        "jornadas_cfc",
        ["establecimiento_id"],
        unique=False,
    )
    op.create_index(
        "uq_jornadas_cfc_abierta",
        "jornadas_cfc",
        ["establecimiento_id"],
        unique=True,
        postgresql_where=sa.text("cerrada_en IS NULL"),
    )
    op.create_table(
        "pedidos_cfc",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jornada_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mesa_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("etiqueta_snapshot", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default="pendiente",
        ),
        sa.Column(
            "lineas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("total_centimos", sa.Integer(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"],
            ["establecimientos.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["jornada_id"],
            ["jornadas_cfc.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "establecimiento_id",
            "idempotency_key",
            name="uq_pedidos_cfc_idempotencia",
        ),
        sa.UniqueConstraint(
            "establecimiento_id",
            "seq",
            name="uq_pedidos_cfc_seq",
        ),
    )
    op.create_index(
        "ix_pedidos_cfc_establecimiento_estado",
        "pedidos_cfc",
        ["establecimiento_id", "estado"],
        unique=False,
    )
    op.create_index(
        "ix_pedidos_cfc_jornada_mesa",
        "pedidos_cfc",
        ["jornada_id", "mesa_uuid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pedidos_cfc_jornada_mesa", table_name="pedidos_cfc")
    op.drop_index("ix_pedidos_cfc_establecimiento_estado", table_name="pedidos_cfc")
    op.drop_table("pedidos_cfc")
    op.drop_index("uq_jornadas_cfc_abierta", table_name="jornadas_cfc")
    op.drop_index("ix_jornadas_cfc_establecimiento_id", table_name="jornadas_cfc")
    op.drop_table("jornadas_cfc")
