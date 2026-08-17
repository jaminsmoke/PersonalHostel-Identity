"""visible_directorio (opt-in del directorio de establecimientos)

Revision ID: 0006_visible_directorio
Revises: 0005_perfil_establecimiento
Create Date: 2026-08-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_visible_directorio"
down_revision: Union[str, None] = "0005_perfil_establecimiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "establecimientos",
        sa.Column(
            "visible_directorio",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("establecimientos", "visible_directorio")
