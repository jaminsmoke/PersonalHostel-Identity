"""espejo del layout del establecimiento (DR del mapa de Bar)

Revision ID: 0007_layout_establecimiento
Revises: 0006_invitaciones_outbox
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0007_layout_establecimiento"
down_revision: Union[str, None] = "0006_invitaciones_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "layouts_establecimiento",
        sa.Column(
            "establecimiento_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("salas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mesas", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("establecimiento_id"),
    )


def downgrade() -> None:
    op.drop_table("layouts_establecimiento")
