"""functional eval site approval workflow

Revision ID: 20260608_0061
Revises: 20260604_0060
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0061"
down_revision = "20260604_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_site_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("site_code", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="IN_PROGRESS"),
        sa.Column("site_submitted_at", sa.DateTime(), nullable=True),
        sa.Column("site_submitted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("hq_approved_at", sa.DateTime(), nullable=True),
        sa.Column("hq_approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("ceo_approved_at", sa.DateTime(), nullable=True),
        sa.Column("ceo_approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_by_user_id", sa.Integer(), nullable=True),
        sa.Column("rejected_stage", sa.String(length=20), nullable=True),
        sa.Column("reject_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ceo_approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["hq_approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["functional_eval_periods.id"]),
        sa.ForeignKeyConstraint(["rejected_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["site_submitted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("period_id", "site_code", name="uq_fe_site_approval_period_site"),
    )
    op.create_index(
        "ix_fe_site_approval_period_id",
        "functional_eval_site_approvals",
        ["period_id"],
    )
    op.create_index(
        "ix_fe_site_approval_site_code",
        "functional_eval_site_approvals",
        ["site_code"],
    )
    op.create_index(
        "ix_fe_site_approval_status",
        "functional_eval_site_approvals",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_fe_site_approval_status", table_name="functional_eval_site_approvals")
    op.drop_index("ix_fe_site_approval_site_code", table_name="functional_eval_site_approvals")
    op.drop_index("ix_fe_site_approval_period_id", table_name="functional_eval_site_approvals")
    op.drop_table("functional_eval_site_approvals")
