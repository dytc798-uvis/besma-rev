"""functional eval ERP headcount + precomputed HQ grade stats

Revision ID: 20260614_0071
Revises: 20260614_0070
Create Date: 2026-06-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0071"
down_revision = "20260614_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("functional_eval_site_registry") as batch:
        batch.add_column(sa.Column("erp_headcount", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("erp_man_days", sa.Float(), nullable=True))
        batch.add_column(sa.Column("erp_work_days", sa.Float(), nullable=True))

    with op.batch_alter_table("functional_eval_periods") as batch:
        batch.add_column(sa.Column("hq_grade_stats_json", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("hq_grade_stats_computed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("functional_eval_periods") as batch:
        batch.drop_column("hq_grade_stats_computed_at")
        batch.drop_column("hq_grade_stats_json")

    with op.batch_alter_table("functional_eval_site_registry") as batch:
        batch.drop_column("erp_work_days")
        batch.drop_column("erp_man_days")
        batch.drop_column("erp_headcount")
