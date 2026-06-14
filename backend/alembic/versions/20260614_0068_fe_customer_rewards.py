"""기능인제 고객사 포상(사진·승인·가점)

Revision ID: 20260614_0068
Revises: 20260614_0067
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0068"
down_revision = "20260614_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_customer_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("functional_eval_workers.id"), nullable=False),
        sa.Column("site_code", sa.String(length=50), nullable=False),
        sa.Column("photo_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("bonus_points", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reject_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_fe_customer_rewards_period_worker",
        "functional_eval_customer_rewards",
        ["period_id", "worker_id"],
    )
    op.create_index(
        "ix_fe_customer_rewards_status",
        "functional_eval_customer_rewards",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_fe_customer_rewards_status", table_name="functional_eval_customer_rewards")
    op.drop_index("ix_fe_customer_rewards_period_worker", table_name="functional_eval_customer_rewards")
    op.drop_table("functional_eval_customer_rewards")
