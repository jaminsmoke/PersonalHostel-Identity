"""visibilidad del camarero para otros establecimientos (directorio)

Revision ID: 0004_visible_otros
Revises: 0003_visibilidad
Create Date: 2026-08-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_visible_otros"
down_revision: Union[str, None] = "0003_visibilidad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "camareros",
        sa.Column(
            "visible_otros_establecimientos",
            sa.String(length=20),
            server_default="nunca",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("camareros", "visible_otros_establecimientos")
