"""nick visible del camarero (mote de sala; el nombre legal no se toca)

Revision ID: 0008_camarero_nick
Revises: 0007_layout_establecimiento
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_camarero_nick"
down_revision: Union[str, None] = "0007_layout_establecimiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("camareros", sa.Column("nick", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("camareros", "nick")
