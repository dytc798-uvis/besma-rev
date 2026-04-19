"""add accident action taken field

Revision ID: 20260419_0040
Revises: 20260419_0039
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260419_0040"
down_revision = "20260419_0039"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "accidents" not in inspector.get_table_names():
        return

    if _has_column(inspector, "accidents", "action_taken"):
        return

    with op.batch_alter_table("accidents") as batch_op:
        batch_op.add_column(sa.Column("action_taken", sa.Text(), nullable=True))


def downgrade() -> None:
    pass
