"""tipo de enlace canónico web (depreca ficha_negocio)

Revision ID: 0011_enlace_tipo_web
Revises: 0010_producto_descripcion
Create Date: 2026-08-19

``tipo`` es VARCHAR, no enum de Postgres: solo se reetiquetan filas
``ficha_negocio`` → ``web``. El alias HTTP sigue aceptando el valor antiguo.

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0011_enlace_tipo_web"
down_revision: Union[str, None] = "0010_producto_descripcion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE enlaces_publicos SET tipo = 'web' WHERE tipo = 'ficha_negocio'")


def downgrade() -> None:
    op.execute("UPDATE enlaces_publicos SET tipo = 'ficha_negocio' WHERE tipo = 'web'")
