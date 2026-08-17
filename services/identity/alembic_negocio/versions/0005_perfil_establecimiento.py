"""perfil canónico por establecimiento y enlace activo único

Revision ID: 0005_perfil_establecimiento
Revises: 0004_enlaces_publicos
Create Date: 2026-08-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_perfil_establecimiento"
down_revision: Union[str, None] = "0004_enlaces_publicos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "establecimientos",
        sa.Column("tipo_establecimiento", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "establecimientos", sa.Column("logo_clave", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "establecimientos", sa.Column("logo_mimetype", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "establecimientos", sa.Column("logo_size", sa.Integer(), nullable=True)
    )
    op.add_column(
        "establecimientos",
        sa.Column("logo_actualizada_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_establecimientos_tipo_establecimiento",
        "establecimientos",
        "tipo_establecimiento IS NULL OR tipo_establecimiento IN "
        "('bar', 'restaurante', 'cafeteria', 'pub', 'copas')",
    )
    op.execute(
        """
        UPDATE establecimientos AS e
        SET tipo_establecimiento = c.tipo_establecimiento
        FROM cuentas_negocio AS c
        WHERE e.cuenta_negocio_id = c.id
          AND e.tipo_establecimiento IS NULL
        """
    )

    # La primera URL compartida es la que se conserva. Las posteriores quedan
    # revocadas antes de imponer la garantía de un único enlace activo.
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY establecimiento_id, tipo
                       ORDER BY creada_en ASC, id ASC
                   ) AS position
            FROM enlaces_publicos
            WHERE estado = 'activo'
        )
        UPDATE enlaces_publicos AS enlace
        SET estado = 'revocado',
            revocada_en = COALESCE(enlace.revocada_en, now()),
            actualizada_en = now()
        FROM ranked
        WHERE enlace.id = ranked.id
          AND ranked.position > 1
        """
    )
    op.drop_index("ix_enlaces_publicos_activos", table_name="enlaces_publicos")
    op.create_index(
        "ix_enlaces_publicos_activos",
        "enlaces_publicos",
        ["establecimiento_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("estado = 'activo'"),
    )


def downgrade() -> None:
    op.drop_index("ix_enlaces_publicos_activos", table_name="enlaces_publicos")
    op.create_index(
        "ix_enlaces_publicos_activos",
        "enlaces_publicos",
        ["establecimiento_id", "tipo"],
        postgresql_where=sa.text("estado = 'activo'"),
    )
    op.drop_constraint(
        "ck_establecimientos_tipo_establecimiento",
        "establecimientos",
        type_="check",
    )
    op.drop_column("establecimientos", "logo_actualizada_en")
    op.drop_column("establecimientos", "logo_size")
    op.drop_column("establecimientos", "logo_mimetype")
    op.drop_column("establecimientos", "logo_clave")
    op.drop_column("establecimientos", "tipo_establecimiento")
