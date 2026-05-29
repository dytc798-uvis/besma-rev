"""functional eval periods, workers, sanctions

Revision ID: 20260529_0054
Revises: 20260514_0053
Create Date: 2026-05-29
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from alembic import op

revision = "20260529_0054"
down_revision = "20260514_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("deadline_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "functional_eval_workers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
        sa.Column("site_code", sa.String(length=50), nullable=False),
        sa.Column("site_name", sa.String(length=300), nullable=True),
        sa.Column("row_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("age_label", sa.String(length=20), nullable=True),
        sa.Column("position_name", sa.String(length=100), nullable=True),
        sa.Column("job_name", sa.String(length=100), nullable=True),
        sa.Column("rrn_masked", sa.String(length=20), nullable=True),
        sa.Column("rrn_hash", sa.String(length=128), nullable=True),
        sa.Column("job_code", sa.String(length=20), nullable=True),
        sa.Column("is_site_manager", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("period_id", "site_code", "row_no", name="uq_fe_worker_period_site_row"),
    )
    op.create_index("ix_functional_eval_workers_site_code", "functional_eval_workers", ["site_code"])
    op.create_index("ix_functional_eval_workers_rrn_hash", "functional_eval_workers", ["rrn_hash"])
    op.create_table(
        "functional_eval_sanctions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("functional_eval_workers.id"), nullable=False),
        sa.Column("site_code", sa.String(length=50), nullable=False),
        sa.Column("violation_code", sa.String(length=50), nullable=False),
        sa.Column("violation_category", sa.String(length=50), nullable=False),
        sa.Column("strike_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sanction_result", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reported_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_functional_eval_sanctions_period_id", "functional_eval_sanctions", ["period_id"])
    op.create_index("ix_functional_eval_sanctions_worker_id", "functional_eval_sanctions", ["worker_id"])
    op.create_index("ix_functional_eval_sanctions_site_code", "functional_eval_sanctions", ["site_code"])

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO functional_eval_periods (id, title, deadline_date, is_active, created_at, updated_at)
            VALUES (1, :title, :deadline, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"title": "기능인제 인사고과", "deadline": date(2026, 6, 15)},
    )


def downgrade() -> None:
    op.drop_index("ix_functional_eval_sanctions_site_code", table_name="functional_eval_sanctions")
    op.drop_index("ix_functional_eval_sanctions_worker_id", table_name="functional_eval_sanctions")
    op.drop_index("ix_functional_eval_sanctions_period_id", table_name="functional_eval_sanctions")
    op.drop_table("functional_eval_sanctions")
    op.drop_index("ix_functional_eval_workers_rrn_hash", table_name="functional_eval_workers")
    op.drop_index("ix_functional_eval_workers_site_code", table_name="functional_eval_workers")
    op.drop_table("functional_eval_workers")
    op.drop_table("functional_eval_periods")
