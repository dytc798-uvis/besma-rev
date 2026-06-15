"""기능인제 제재 승인 상태 (마감 후 현장 신고 · 본사 승인)

Revision ID: 20260617_0076
Revises: 20260617_0075
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260617_0076"
down_revision = "20260617_0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("functional_eval_sanctions") as batch:
        batch.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="APPROVED"),
        )
        batch.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("reject_note", sa.Text(), nullable=True))
    op.create_index(
        "ix_fe_sanctions_period_status",
        "functional_eval_sanctions",
        ["period_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_fe_sanctions_period_status", table_name="functional_eval_sanctions")
    with op.batch_alter_table("functional_eval_sanctions") as batch:
        batch.drop_column("reject_note")
        batch.drop_column("reviewed_at")
        batch.drop_column("reviewed_by_user_id")
        batch.drop_column("status")
