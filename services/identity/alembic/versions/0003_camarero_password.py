"""camareros: password_hash para login (argon2)

Revision ID: 0003_camarero_password
Revises: 0002_app_config
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_camarero_password"
down_revision: Union[str, None] = "0002_app_config"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "camareros",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("camareros", "password_hash")
