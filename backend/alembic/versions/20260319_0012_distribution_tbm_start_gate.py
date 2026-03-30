"""add tbm start fields to distributions

Revision ID: 20260319_0012
Revises: 20260318_0011
Create Date: 2026-03-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260319_0012"
down_revision = "20260318_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("daily_work_plan_distributions")}
    index_names = {idx["name"] for idx in inspector.get_indexes("daily_work_plan_distributions")}
    with op.batch_alter_table("daily_work_plan_distributions", schema=None) as batch_op:
        if "tbm_started_at" not in columns:
            batch_op.add_column(sa.Column("tbm_started_at", sa.DateTime(), nullable=True))
        if "tbm_started_by_user_id" not in columns:
            batch_op.add_column(sa.Column("tbm_started_by_user_id", sa.Integer(), nullable=True))
        if "tbm_closed_at" not in columns:
            batch_op.add_column(sa.Column("tbm_closed_at", sa.DateTime(), nullable=True))
        if "ix_daily_work_plan_distributions_tbm_started_at" not in index_names:
            batch_op.create_index(
                "ix_daily_work_plan_distributions_tbm_started_at",
                ["tbm_started_at"],
                unique=False,
            )
        if "ix_daily_work_plan_distributions_tbm_started_by_user_id" not in index_names:
            batch_op.create_index(
                "ix_daily_work_plan_distributions_tbm_started_by_user_id",
                ["tbm_started_by_user_id"],
                unique=False,
            )
        foreign_keys = {fk["name"] for fk in inspector.get_foreign_keys("daily_work_plan_distributions")}
        if "fk_daily_work_plan_distributions_tbm_started_by_user_id_users" not in foreign_keys:
            batch_op.create_foreign_key(
                "fk_daily_work_plan_distributions_tbm_started_by_user_id_users",
                "users",
                ["tbm_started_by_user_id"],
                ["id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("daily_work_plan_distributions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_daily_work_plan_distributions_tbm_started_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_daily_work_plan_distributions_tbm_started_by_user_id")
        batch_op.drop_index("ix_daily_work_plan_distributions_tbm_started_at")
        batch_op.drop_column("tbm_closed_at")
        batch_op.drop_column("tbm_started_by_user_id")
        batch_op.drop_column("tbm_started_at")
