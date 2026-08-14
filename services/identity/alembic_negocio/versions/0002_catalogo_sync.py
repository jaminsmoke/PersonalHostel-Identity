"""catálogo canónico y protocolo de sincronización offline

Revision ID: 0002_catalogo_sync
Revises: 0001_negocio
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_catalogo_sync"
down_revision: Union[str, None] = "0001_negocio"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    producto_destino = postgresql.ENUM(
        "barra", "cocina", name="producto_destino", create_type=False
    )
    sync_accion = postgresql.ENUM(
        "crear", "actualizar", "archivar", name="sync_accion", create_type=False
    )
    sync_estado = postgresql.ENUM(
        "aplicada", "conflicto", "rechazada", name="sync_estado", create_type=False
    )
    conflicto_estado = postgresql.ENUM(
        "pendiente", "aceptado", "rechazado", name="conflicto_estado", create_type=False
    )
    for enum in (producto_destino, sync_accion, sync_estado, conflicto_estado):
        enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "establecimientos",
        sa.Column("sync_revision", sa.BigInteger(), server_default="0", nullable=False),
    )

    op.create_table(
        "productos_catalogo",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("categoria", sa.String(length=100), nullable=False),
        sa.Column("destino", producto_destino, nullable=False),
        sa.Column("precio_centimos", sa.Integer(), nullable=False),
        sa.Column("moneda", sa.String(length=3), nullable=False),
        sa.Column("disponible", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("precio_centimos >= 0", name="ck_producto_precio_no_negativo"),
        sa.CheckConstraint("revision > 0", name="ck_producto_revision_positiva"),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_productos_catalogo_establecimiento_id",
        "productos_catalogo",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_productos_catalogo_activos",
        "productos_catalogo",
        ["establecimiento_id", "destino"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "operaciones_sync",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.String(length=200), nullable=False),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sync_accion, nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("base_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("server_received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("estado", sync_estado, nullable=False),
        sa.Column("global_revision", sa.BigInteger(), nullable=True),
        sa.Column("result_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_operaciones_sync_establecimiento_id",
        "operaciones_sync",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_operaciones_sync_change_feed",
        "operaciones_sync",
        ["establecimiento_id", "global_revision"],
        postgresql_where=sa.text("global_revision IS NOT NULL"),
    )

    op.create_table(
        "conflictos_sync",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("operacion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_revision", sa.Integer(), nullable=False),
        sa.Column("base_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("canonical_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("proposed_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("estado", conflicto_estado, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operacion_id"], ["operaciones_sync.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operacion_id"),
    )
    op.create_index(
        "ix_conflictos_sync_establecimiento_id",
        "conflictos_sync",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_conflictos_sync_pendientes",
        "conflictos_sync",
        ["establecimiento_id", "created_at"],
        postgresql_where=sa.text("estado = 'pendiente'"),
    )

    op.create_table(
        "notificaciones_negocio",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("establecimiento_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conflicto_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tipo", sa.String(length=80), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("mensaje", sa.String(length=500), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conflicto_id"], ["conflictos_sync.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["establecimiento_id"], ["establecimientos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notificaciones_negocio_establecimiento_id",
        "notificaciones_negocio",
        ["establecimiento_id"],
    )
    op.create_index(
        "ix_notificaciones_negocio_no_leidas",
        "notificaciones_negocio",
        ["establecimiento_id", "created_at"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_notificaciones_negocio_no_leidas", table_name="notificaciones_negocio")
    op.drop_index("ix_notificaciones_negocio_establecimiento_id", table_name="notificaciones_negocio")
    op.drop_table("notificaciones_negocio")
    op.drop_index("ix_conflictos_sync_pendientes", table_name="conflictos_sync")
    op.drop_index("ix_conflictos_sync_establecimiento_id", table_name="conflictos_sync")
    op.drop_table("conflictos_sync")
    op.drop_index("ix_operaciones_sync_change_feed", table_name="operaciones_sync")
    op.drop_index("ix_operaciones_sync_establecimiento_id", table_name="operaciones_sync")
    op.drop_table("operaciones_sync")
    op.drop_index("ix_productos_catalogo_activos", table_name="productos_catalogo")
    op.drop_index("ix_productos_catalogo_establecimiento_id", table_name="productos_catalogo")
    op.drop_table("productos_catalogo")
    op.drop_column("establecimientos", "sync_revision")
    op.execute("DROP TYPE IF EXISTS conflicto_estado")
    op.execute("DROP TYPE IF EXISTS sync_estado")
    op.execute("DROP TYPE IF EXISTS sync_accion")
    op.execute("DROP TYPE IF EXISTS producto_destino")
