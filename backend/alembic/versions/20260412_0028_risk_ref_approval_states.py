"""add risk ref approval states

Revision ID: 20260412_0028
Revises: 89b31d14afcb
Create Date: 2026-04-12 20:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260412_0028"
down_revision = "89b31d14afcb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_work_plan_item_risk_refs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("site_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("site_approved_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("site_approved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("hq_final_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("hq_final_approved_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("hq_final_approved_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_dwpr_site_approved_by_user_id", ["site_approved_by_user_id"], unique=False)
        batch_op.create_index("ix_dwpr_hq_final_approved_by_user_id", ["hq_final_approved_by_user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("daily_work_plan_item_risk_refs", schema=None) as batch_op:
        batch_op.drop_index("ix_dwpr_hq_final_approved_by_user_id")
        batch_op.drop_index("ix_dwpr_site_approved_by_user_id")
        batch_op.drop_column("hq_final_approved_at")
        batch_op.drop_column("hq_final_approved_by_user_id")
        batch_op.drop_column("hq_final_approved")
        batch_op.drop_column("site_approved_at")
        batch_op.drop_column("site_approved_by_user_id")
        batch_op.drop_column("site_approved")
