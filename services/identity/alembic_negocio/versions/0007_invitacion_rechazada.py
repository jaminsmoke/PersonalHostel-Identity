"""rechazada en invitacion_estado (rechazo del camarero)

Revision ID: 0007_invitacion_rechazada
Revises: 0006_visible_directorio
Create Date: 2026-08-18

Migración aditiva: PostgreSQL no permite DROP VALUE de forma simple, así que el
downgrade es un no-op documentado. El ciclo upgrade→downgrade→upgrade de
`check_migrations.py` sigue cerrando porque el `downgrade base` de 0001_negocio
dropea el tipo entero.

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0007_invitacion_rechazada"
down_revision: Union[str, None] = "0006_visible_directorio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE invitacion_estado ADD VALUE IF NOT EXISTS 'rechazada'")


def downgrade() -> None:
    # No-op: añadir un valor a un enum de Postgres no es reversible con
    # `DROP VALUE` de forma simple; el valor queda disponible pero sin uso.
    pass
