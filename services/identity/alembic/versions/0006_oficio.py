"""jornadas y servicios (libro de oficio) del camarero

Revision ID: 0006_oficio
Revises: 0005_direccion_ciudad
Create Date: 2026-08-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0006_oficio"
down_revision: Union[str, None] = "0005_direccion_ciudad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    data_origin = postgresql.ENUM(
        "real", "test", "demo", name="data_origin", create_type=False
    )

    op.create_table(
        "jornadas",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("camarero_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "data_origin",
            data_origin,
            server_default=sa.text("'real'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["camarero_id"], ["camareros.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("fin IS NULL OR fin >= inicio", name="ck_jornadas_intervalo"),
    )
    op.create_index("ix_jornadas_camarero_id", "jornadas", ["camarero_id"])
    op.create_index("ix_jornadas_establecimiento_id", "jornadas", ["establecimiento_id"])
    op.create_index("ix_jornadas_data_origin", "jornadas", ["data_origin"])
    op.create_index("ix_jornadas_camarero_ventana", "jornadas", ["camarero_id", "inicio"])

    op.create_table(
        "servicios",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("camarero_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evento_id", sa.String(length=64), nullable=False),
        sa.Column("tipo", sa.String(length=50), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column(
            "data_origin",
            data_origin,
            server_default=sa.text("'real'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["camarero_id"], ["camareros.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "establecimiento_id", "evento_id", name="uq_servicios_establecimiento_evento"
        ),
        sa.CheckConstraint("cantidad > 0", name="ck_servicios_cantidad_positiva"),
    )
    op.create_index("ix_servicios_camarero_id", "servicios", ["camarero_id"])
    op.create_index("ix_servicios_establecimiento_id", "servicios", ["establecimiento_id"])
    op.create_index("ix_servicios_data_origin", "servicios", ["data_origin"])
    op.create_index("ix_servicios_camarero_ventana", "servicios", ["camarero_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_servicios_camarero_ventana", table_name="servicios")
    op.drop_index("ix_servicios_data_origin", table_name="servicios")
    op.drop_index("ix_servicios_establecimiento_id", table_name="servicios")
    op.drop_index("ix_servicios_camarero_id", table_name="servicios")
    op.drop_table("servicios")

    op.drop_index("ix_jornadas_camarero_ventana", table_name="jornadas")
    op.drop_index("ix_jornadas_data_origin", table_name="jornadas")
    op.drop_index("ix_jornadas_establecimiento_id", table_name="jornadas")
    op.drop_index("ix_jornadas_camarero_id", table_name="jornadas")
    op.drop_table("jornadas")
