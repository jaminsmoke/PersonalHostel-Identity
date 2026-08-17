"""dirección y ciudad en el perfil del camarero

Revision ID: 0005_direccion_ciudad
Revises: 0004_visible_otros
Create Date: 2026-08-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_direccion_ciudad"
down_revision: Union[str, None] = "0004_visible_otros"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "camareros",
        sa.Column("direccion", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "camareros",
        sa.Column("ciudad", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("camareros", "ciudad")
    op.drop_column("camareros", "direccion")
