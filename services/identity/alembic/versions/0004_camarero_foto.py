"""camareros: foto de perfil (clave, mimetype, tamaño, fecha)

Revision ID: 0004_camarero_foto
Revises: 0003_camarero_password
Create Date: 2026-08-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_camarero_foto"
down_revision: Union[str, None] = "0003_camarero_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("camareros", sa.Column("foto_clave", sa.String(length=255), nullable=True))
    op.add_column("camareros", sa.Column("foto_mimetype", sa.String(length=64), nullable=True))
    op.add_column("camareros", sa.Column("foto_size", sa.Integer(), nullable=True))
    op.add_column(
        "camareros",
        sa.Column("foto_actualizada_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("camareros", "foto_actualizada_en")
    op.drop_column("camareros", "foto_size")
    op.drop_column("camareros", "foto_mimetype")
    op.drop_column("camareros", "foto_clave")
