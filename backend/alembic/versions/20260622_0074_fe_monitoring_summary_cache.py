"""functional eval HQ monitoring summary cache

Revision ID: 20260622_0074
Revises: 20260616_0073
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260622_0074"
down_revision = "20260617_0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("functional_eval_periods") as batch:
        batch.add_column(sa.Column("hq_monitoring_summary_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("hq_monitoring_summary_computed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("functional_eval_periods") as batch:
        batch.drop_column("hq_monitoring_summary_computed_at")
        batch.drop_column("hq_monitoring_summary_json")
