"""registro canónico de mesas CFC y tokens opacos

Revision ID: 0014_mesas_cfc
Revises: 0013_layout_documento
Create Date: 2026-08-21

Identity no interpreta el layout: Bar envía el conjunto de mesas públicas.
El token se busca por hash; el valor se reconstruye cifrado para url_publica.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014_mesas_cfc"
down_revision: Union[str, None] = "0013_layout_documento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mesas_cfc",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mesa_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("etiqueta", sa.String(length=40), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_protegido", sa.Text(), nullable=False),
        sa.Column(
            "estado",
            sa.String(length=20),
            nullable=False,
            server_default="activo",
        ),
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
            ["establecimiento_id"],
            ["establecimientos.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_mesas_cfc_token_hash"),
    )
    op.create_index(
        "ix_mesas_cfc_establecimiento_id",
        "mesas_cfc",
        ["establecimiento_id"],
        unique=False,
    )
    op.create_index(
        "ix_mesas_cfc_establecimiento_estado",
        "mesas_cfc",
        ["establecimiento_id", "estado"],
        unique=False,
    )
    op.create_index(
        "uq_mesas_cfc_activa",
        "mesas_cfc",
        ["establecimiento_id", "mesa_uuid"],
        unique=True,
        postgresql_where=sa.text("estado = 'activo'"),
    )


def downgrade() -> None:
    op.drop_index("uq_mesas_cfc_activa", table_name="mesas_cfc")
    op.drop_index("ix_mesas_cfc_establecimiento_estado", table_name="mesas_cfc")
    op.drop_index("ix_mesas_cfc_establecimiento_id", table_name="mesas_cfc")
    op.drop_table("mesas_cfc")
