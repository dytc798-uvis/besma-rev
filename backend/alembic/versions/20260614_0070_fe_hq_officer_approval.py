"""functional eval HQ officer two-step approval

Revision ID: 20260614_0070
Revises: 20260614_0069
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0070"
down_revision = "20260614_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "functional_eval_site_approvals",
        sa.Column("hq_officer_approved_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "functional_eval_site_approvals",
        sa.Column("hq_officer_approved_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "functional_eval_site_approvals",
        sa.Column("hq_officer_comment", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_fe_site_approval_hq_officer_user",
        "functional_eval_site_approvals",
        "users",
        ["hq_officer_approved_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_fe_site_approval_hq_officer_user", "functional_eval_site_approvals", type_="foreignkey")
    op.drop_column("functional_eval_site_approvals", "hq_officer_comment")
    op.drop_column("functional_eval_site_approvals", "hq_officer_approved_by_user_id")
    op.drop_column("functional_eval_site_approvals", "hq_officer_approved_at")
