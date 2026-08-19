"""descripcion opcional de producto para la carta pública

Revision ID: 0010_producto_descripcion
Revises: 0009_perfil_web_establecimiento
Create Date: 2026-08-19

Aditiva y reversible: columna nullable; los clientes de sync que no la envían
siguen funcionando (NULL).

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_producto_descripcion"
down_revision: Union[str, None] = "0009_perfil_web_establecimiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "productos_catalogo",
        sa.Column("descripcion", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("productos_catalogo", "descripcion")
