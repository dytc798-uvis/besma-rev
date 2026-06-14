"""functional eval HQ officer two-step approval

Revision ID: 20260614_0070
Revises: 20260614_0069
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260614_0070"
down_revision = "20260614_0069"
branch_labels = None
depends_on = None


def _approval_columns(conn) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns("functional_eval_site_approvals")}


def upgrade() -> None:
    conn = op.get_bind()
    cols = _approval_columns(conn)
    with op.batch_alter_table("functional_eval_site_approvals") as batch:
        if "hq_officer_approved_at" not in cols:
            batch.add_column(sa.Column("hq_officer_approved_at", sa.DateTime(), nullable=True))
        if "hq_officer_approved_by_user_id" not in cols:
            batch.add_column(sa.Column("hq_officer_approved_by_user_id", sa.Integer(), nullable=True))
        if "hq_officer_comment" not in cols:
            batch.add_column(sa.Column("hq_officer_comment", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_fe_site_approval_hq_officer_user",
            "users",
            ["hq_officer_approved_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("functional_eval_site_approvals") as batch:
        batch.drop_constraint("fk_fe_site_approval_hq_officer_user", type_="foreignkey")
        batch.drop_column("hq_officer_comment")
        batch.drop_column("hq_officer_approved_by_user_id")
        batch.drop_column("hq_officer_approved_at")
