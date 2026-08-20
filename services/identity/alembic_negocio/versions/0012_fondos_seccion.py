"""fondos JSONB por seccion en el perfil web

Revision ID: 0012_fondos_seccion
Revises: 0011_enlace_tipo_web
Create Date: 2026-08-20

Aditiva y reversible. El JSON guarda la asignacion de fondo por slot
(catalogo o upload); vacio = default Estate.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0012_fondos_seccion"
down_revision: Union[str, None] = "0011_enlace_tipo_web"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "perfiles_establecimiento",
        sa.Column(
            "fondos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("perfiles_establecimiento", "fondos")
