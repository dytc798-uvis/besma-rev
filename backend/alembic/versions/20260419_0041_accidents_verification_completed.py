"""set all accidents verification_status to completed

Revision ID: 20260419_0041
Revises: 20260419_0040
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260419_0041"
down_revision = "20260419_0040"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "accidents" not in inspector.get_table_names():
        return
    if not _has_column(inspector, "accidents", "verification_status"):
        return

    bind.execute(sa.text("UPDATE accidents SET verification_status = '검증완료'"))


def downgrade() -> None:
    # Non-destructive: we can't reliably restore previous verification states.
    pass
