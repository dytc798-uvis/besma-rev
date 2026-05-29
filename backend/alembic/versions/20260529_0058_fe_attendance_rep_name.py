"""functional eval attendance rep_name column

Revision ID: 20260529_0058
Revises: 20260529_0057
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_0058"
down_revision = "20260529_0057"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "functional_eval_attendance_entries" in inspector.get_table_names():
        if not _has_column(inspector, "functional_eval_attendance_entries", "rep_name"):
            with op.batch_alter_table("functional_eval_attendance_entries") as batch_op:
                batch_op.add_column(sa.Column("rep_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "functional_eval_attendance_entries" in inspector.get_table_names():
        if _has_column(inspector, "functional_eval_attendance_entries", "rep_name"):
            with op.batch_alter_table("functional_eval_attendance_entries") as batch_op:
                batch_op.drop_column("rep_name")
