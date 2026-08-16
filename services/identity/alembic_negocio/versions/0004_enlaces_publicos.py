"""enlaces públicos revocables (ficha de negocio, carta, futuros)

Revision ID: 0004_enlaces_publicos
Revises: 0003_data_origin
Create Date: 2026-08-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_enlaces_publicos"
down_revision: Union[str, None] = "0003_data_origin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enlaces_publicos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="activo", nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creada_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "actualizada_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_enlaces_publicos_slug"),
    )
    op.create_index(
        "ix_enlaces_publicos_establecimiento_id",
        "enlaces_publicos",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_enlaces_publicos_activos",
        "enlaces_publicos",
        ["establecimiento_id", "tipo"],
        postgresql_where=sa.text("estado = 'activo'"),
    )


def downgrade() -> None:
    op.drop_index("ix_enlaces_publicos_activos", table_name="enlaces_publicos")
    op.drop_index("ix_enlaces_publicos_establecimiento_id", table_name="enlaces_publicos")
    op.drop_table("enlaces_publicos")
