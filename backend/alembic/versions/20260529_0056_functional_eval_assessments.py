"""functional eval assessments (2-1 / 2-2)

Revision ID: 20260529_0056
Revises: 20260529_0055
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_0056"
down_revision = "20260529_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "functional_eval_assessments" in inspector.get_table_names():
        return
    op.create_table(
        "functional_eval_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("functional_eval_workers.id"), nullable=False),
        sa.Column("eval_type", sa.String(20), nullable=False),
        sa.Column("scores_json", sa.JSON(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("grade_code", sa.String(10), nullable=False, server_default=""),
        sa.Column("grade_label", sa.String(30), nullable=False, server_default=""),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("worker_id", "eval_type", name="uq_fe_assessment_worker_type"),
    )
    op.create_index("ix_fe_assessment_worker_id", "functional_eval_assessments", ["worker_id"])
    op.create_index("ix_fe_assessment_eval_type", "functional_eval_assessments", ["eval_type"])


def downgrade() -> None:
    op.drop_table("functional_eval_assessments")
