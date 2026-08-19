"""perfil público de la web y galería del establecimiento

Revision ID: 0009_perfil_web_establecimiento
Revises: 0008_horario_establecimiento
Create Date: 2026-08-19

Aditiva y reversible: dos tablas nuevas. La tabla de perfiles se rellena con un
backfill para que las webs públicas existentes sigan funcionando sin cambios (el
perfil con defaults activa la web con la plantilla por defecto).

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0009_perfil_web_establecimiento"
down_revision: Union[str, None] = "0008_horario_establecimiento"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    data_origin = postgresql.ENUM("real", "test", "demo", name="data_origin", create_type=False)

    op.create_table(
        "perfiles_establecimiento",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eslogan", sa.String(length=140), nullable=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("direccion", sa.String(length=255), nullable=True),
        sa.Column("ciudad", sa.String(length=100), nullable=True),
        sa.Column("telefono", sa.String(length=32), nullable=True),
        sa.Column("email_contacto", sa.String(length=320), nullable=True),
        sa.Column("web", sa.String(length=255), nullable=True),
        sa.Column(
            "redes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "tz",
            sa.String(length=64),
            server_default=sa.text("'Europe/Madrid'"),
            nullable=False,
        ),
        sa.Column("hero_clave", sa.String(length=255), nullable=True),
        sa.Column("hero_mimetype", sa.String(length=64), nullable=True),
        sa.Column("hero_size", sa.Integer(), nullable=True),
        sa.Column("hero_actualizada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "plantilla",
            sa.String(length=50),
            server_default=sa.text("'estate_hospitality'"),
            nullable=False,
        ),
        sa.Column("color_primario", sa.String(length=20), nullable=True),
        sa.Column(
            "web_publica",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "mostrar_equipo",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "data_origin",
            data_origin,
            server_default=sa.text("'real'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "establecimiento_id", name="uq_perfiles_establecimiento_establecimiento"
        ),
    )
    op.create_index(
        "ix_perfiles_establecimiento_establecimiento_id",
        "perfiles_establecimiento",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_perfiles_establecimiento_data_origin",
        "perfiles_establecimiento",
        ["data_origin"],
    )

    # Backfill: toda web existente (establecimiento con enlace activo) hereda el
    # perfil por defecto y su procedencia para no cambiar de comportamiento.
    op.execute(
        """
        INSERT INTO perfiles_establecimiento (
            establecimiento_id, tz, plantilla, web_publica, mostrar_equipo, redes, data_origin
        )
        SELECT
            e.id, 'Europe/Madrid', 'estate_hospitality', true, false, '{}'::jsonb, e.data_origin
        FROM establecimientos AS e
        """
    )

    op.create_table(
        "imagenes_establecimiento",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("clave", sa.String(length=255), nullable=False),
        sa.Column("mimetype", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column(
            "uso",
            sa.String(length=20),
            server_default=sa.text("'galeria'"),
            nullable=False,
        ),
        sa.Column("orden", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "data_origin",
            data_origin,
            server_default=sa.text("'real'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_imagenes_establecimiento_establecimiento_id",
        "imagenes_establecimiento",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_imagenes_establecimiento_data_origin",
        "imagenes_establecimiento",
        ["data_origin"],
    )


def downgrade() -> None:
    op.drop_index("ix_imagenes_establecimiento_data_origin", table_name="imagenes_establecimiento")
    op.drop_index(
        "ix_imagenes_establecimiento_establecimiento_id", table_name="imagenes_establecimiento"
    )
    op.drop_table("imagenes_establecimiento")
    op.drop_index("ix_perfiles_establecimiento_data_origin", table_name="perfiles_establecimiento")
    op.drop_index(
        "ix_perfiles_establecimiento_establecimiento_id", table_name="perfiles_establecimiento"
    )
    op.drop_table("perfiles_establecimiento")
