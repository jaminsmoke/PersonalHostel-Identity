"""opt-in del camarero para la web pública del negocio

Revision ID: 0007_aparecer_web_negocio
Revises: 0006_oficio
Create Date: 2026-08-19

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_aparecer_web_negocio"
down_revision: Union[str, None] = "0006_oficio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "camareros",
        sa.Column(
            "aparecer_web_negocio",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("camareros", "aparecer_web_negocio")
