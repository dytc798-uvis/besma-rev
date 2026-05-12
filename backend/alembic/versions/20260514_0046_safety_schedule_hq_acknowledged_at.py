"""add hq_acknowledged_at on safety_schedule_entries

Revision ID: 20260514_0046
Revises: 20260513_0045
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260514_0046"
down_revision = "20260513_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_entries" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("safety_schedule_entries")}
    if "hq_acknowledged_at" in cols:
        return
    op.add_column(
        "safety_schedule_entries",
        sa.Column("hq_acknowledged_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_entries" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("safety_schedule_entries")}
    if "hq_acknowledged_at" not in cols:
        return
    op.drop_column("safety_schedule_entries", "hq_acknowledged_at")
