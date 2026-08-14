"""procedencia canónica de camareros

Revision ID: 0002_data_origin
Revises: 0001_camareros
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_data_origin"
down_revision: Union[str, None] = "0001_camareros"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    data_origin = postgresql.ENUM(
        "real", "test", "demo", name="data_origin", create_type=False
    )
    data_origin.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "camareros",
        sa.Column(
            "data_origin",
            data_origin,
            server_default=sa.text("'real'"),
            nullable=False,
        ),
    )
    op.create_index("ix_camareros_data_origin", "camareros", ["data_origin"])


def downgrade() -> None:
    op.drop_index("ix_camareros_data_origin", table_name="camareros")
    op.drop_column("camareros", "data_origin")
    postgresql.ENUM(
        "real", "test", "demo", name="data_origin", create_type=False
    ).drop(op.get_bind(), checkfirst=True)
