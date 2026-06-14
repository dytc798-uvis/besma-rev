"""functional eval grade stats live-from date

Revision ID: 20260614_0072
Revises: 20260614_0071
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0072"
down_revision = "20260614_0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "functional_eval_periods",
        sa.Column("grade_stats_live_from", sa.Date(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE functional_eval_periods SET grade_stats_live_from = '2026-06-16' "
            "WHERE grade_stats_live_from IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("functional_eval_periods", "grade_stats_live_from")
