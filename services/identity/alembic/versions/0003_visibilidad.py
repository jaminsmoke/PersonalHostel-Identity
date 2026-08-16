"""visibilidad pública del perfil de camarero

Revision ID: 0003_visibilidad
Revises: 0002_data_origin
Create Date: 2026-08-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_visibilidad"
down_revision: Union[str, None] = "0002_data_origin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT = (
    '{"nombre": true, "apellidos": true, "nick": true, '
    '"email": false, "telefono": false, "foto": false}'
)


def upgrade() -> None:
    op.add_column(
        "camareros",
        sa.Column(
            "visibilidad",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(f"'{_DEFAULT}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("camareros", "visibilidad")
