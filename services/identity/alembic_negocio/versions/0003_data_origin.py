"""procedencia canónica de negocio, establecimientos y catálogo

Revision ID: 0003_data_origin
Revises: 0002_catalogo_sync
Create Date: 2026-08-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_data_origin"
down_revision: Union[str, None] = "0002_catalogo_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    data_origin = postgresql.ENUM(
        "real", "test", "demo", name="data_origin", create_type=False
    )
    data_origin.create(op.get_bind(), checkfirst=True)
    for table_name in ("cuentas_negocio", "establecimientos", "productos_catalogo"):
        op.add_column(
            table_name,
            sa.Column(
                "data_origin",
                data_origin,
                server_default=sa.text("'real'"),
                nullable=False,
            ),
        )
        op.create_index(
            f"ix_{table_name}_data_origin", table_name, ["data_origin"]
        )


def downgrade() -> None:
    for table_name in reversed(
        ("cuentas_negocio", "establecimientos", "productos_catalogo")
    ):
        op.drop_index(f"ix_{table_name}_data_origin", table_name=table_name)
        op.drop_column(table_name, "data_origin")
    postgresql.ENUM(
        "real", "test", "demo", name="data_origin", create_type=False
    ).drop(op.get_bind(), checkfirst=True)
