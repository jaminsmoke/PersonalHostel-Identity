"""cuentas_negocio: tipo de establecimiento (catálogo) y logo de negocio

Revision ID: 0009_cuenta_negocio_tipo_logo
Revises: 0008_camarero_nick
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_cuenta_negocio_tipo_logo"
down_revision: Union[str, None] = "0008_camarero_nick"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIPOS_ESTABLECIMIENTO = ("bar", "restaurante", "cafeteria", "pub", "copas")


def upgrade() -> None:
    op.add_column(
        "cuentas_negocio",
        sa.Column("tipo_establecimiento", sa.String(length=50), nullable=True),
    )
    valores = ", ".join("'" + t + "'" for t in TIPOS_ESTABLECIMIENTO)
    op.create_check_constraint(
        "ck_cuentas_tipo_establecimiento",
        "cuentas_negocio",
        "tipo_establecimiento IS NULL OR tipo_establecimiento IN (" + valores + ")",
    )
    op.add_column("cuentas_negocio", sa.Column("logo_clave", sa.String(length=255), nullable=True))
    op.add_column("cuentas_negocio", sa.Column("logo_mimetype", sa.String(length=64), nullable=True))
    op.add_column("cuentas_negocio", sa.Column("logo_size", sa.Integer(), nullable=True))
    op.add_column(
        "cuentas_negocio",
        sa.Column("logo_actualizada_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_constraint("ck_cuentas_tipo_establecimiento", "cuentas_negocio", type_="check")
    op.drop_column("cuentas_negocio", "logo_actualizada_en")
    op.drop_column("cuentas_negocio", "logo_size")
    op.drop_column("cuentas_negocio", "logo_mimetype")
    op.drop_column("cuentas_negocio", "logo_clave")
    op.drop_column("cuentas_negocio", "tipo_establecimiento")