"""functional eval daily progress reports

Revision ID: 20260616_0073
Revises: 20260614_0072
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260616_0073"
down_revision = "20260614_0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_daily_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("criteria_at_kst", sa.String(40), nullable=False),
        sa.Column("timezone", sa.String(40), nullable=False, server_default="Asia/Seoul"),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.Column("regenerated_at", sa.DateTime(), nullable=True),
        sa.Column("total_workers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_workers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("bottleneck_site_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("report_path", sa.Text(), nullable=True),
        sa.Column("report_json_path", sa.Text(), nullable=True),
        sa.Column("report_format", sa.String(20), nullable=False, server_default="pdf"),
        sa.Column("report_json_snapshot", sa.JSON(), nullable=True),
        sa.Column("generated_by", sa.String(20), nullable=False, server_default="system"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("period_id", "report_date", name="uq_fe_daily_report_period_date"),
    )
    op.create_index("ix_fe_daily_report_period_id", "functional_eval_daily_reports", ["period_id"])
    op.create_index("ix_fe_daily_report_report_date", "functional_eval_daily_reports", ["report_date"])


def downgrade() -> None:
    op.drop_index("ix_fe_daily_report_report_date", table_name="functional_eval_daily_reports")
    op.drop_index("ix_fe_daily_report_period_id", table_name="functional_eval_daily_reports")
    op.drop_table("functional_eval_daily_reports")
