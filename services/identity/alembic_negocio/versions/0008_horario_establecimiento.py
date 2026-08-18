"""horarios_establecimiento (horario semanal canónico del local)

Revision ID: 0008_horario_establecimiento
Revises: 0007_invitacion_rechazada
Create Date: 2026-08-18

Aditiva y reversible: tabla nueva sin datos que migrar. La validación de forma
(turnos, solapamientos) vive en la capa API; la BD solo garantiza el rango del
día y la unicidad establecimiento+día.

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0008_horario_establecimiento"
down_revision: Union[str, None] = "0007_invitacion_rechazada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "horarios_establecimiento",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column(
            "cerrado",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "turnos",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
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
        sa.CheckConstraint("dia_semana BETWEEN 0 AND 6", name="ck_horarios_dia_semana"),
        sa.UniqueConstraint(
            "establecimiento_id",
            "dia_semana",
            name="uq_horarios_establecimiento_dia",
        ),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_horarios_establecimiento_establecimiento_id",
        "horarios_establecimiento",
        ["establecimiento_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_horarios_establecimiento_establecimiento_id",
        table_name="horarios_establecimiento",
    )
    op.drop_table("horarios_establecimiento")
