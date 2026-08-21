"""layout como documento JSONB opaco

Revision ID: 0013_layout_documento
Revises: 0012_fondos_seccion
Create Date: 2026-08-21

Sustituye las columnas por capa (salas, mesas) por un documento JSON unico.
Identity no interpreta el layout; persiste el snapshot que manda Bar.
Reversible a nivel de esquema: el downgrade reconstruye salas/mesas y descarta
claves extra (zonas y futuras).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0013_layout_documento"
down_revision: Union[str, None] = "0012_fondos_seccion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "layouts_establecimiento",
        sa.Column(
            "documento",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE layouts_establecimiento "
            "SET documento = jsonb_build_object('salas', salas, 'mesas', mesas)"
        )
    )
    op.drop_column("layouts_establecimiento", "salas")
    op.drop_column("layouts_establecimiento", "mesas")


def downgrade() -> None:
    op.add_column(
        "layouts_establecimiento",
        sa.Column("salas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "layouts_establecimiento",
        sa.Column("mesas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE layouts_establecimiento SET "
            "salas = COALESCE(documento->'salas', '[]'::jsonb), "
            "mesas = COALESCE(documento->'mesas', '[]'::jsonb)"
        )
    )
    op.alter_column("layouts_establecimiento", "salas", nullable=False)
    op.alter_column("layouts_establecimiento", "mesas", nullable=False)
    op.drop_column("layouts_establecimiento", "documento")
