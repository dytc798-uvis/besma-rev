"""기능인제 평가 수정 이력(본사·제재 연동)

Revision ID: 20260611_0066
Revises: 20260611_0065
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260611_0066"
down_revision = "20260611_0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_assessment_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("worker_id", sa.Integer(), sa.ForeignKey("functional_eval_workers.id"), nullable=False),
        sa.Column("eval_type", sa.String(length=20), nullable=False),
        sa.Column("before_scores_json", sa.JSON(), nullable=True),
        sa.Column("after_scores_json", sa.JSON(), nullable=False),
        sa.Column("before_grade_code", sa.String(length=10), nullable=True),
        sa.Column("after_grade_code", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="HQ_OVERRIDE"),
        sa.Column("sanction_id", sa.Integer(), sa.ForeignKey("functional_eval_sanctions.id"), nullable=True),
        sa.Column("edited_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_functional_eval_assessment_revisions_worker_id",
        "functional_eval_assessment_revisions",
        ["worker_id"],
    )
    op.create_index(
        "ix_functional_eval_assessment_revisions_eval_type",
        "functional_eval_assessment_revisions",
        ["eval_type"],
    )
    op.create_index(
        "ix_functional_eval_assessment_revisions_source",
        "functional_eval_assessment_revisions",
        ["source"],
    )
    op.create_index(
        "ix_functional_eval_assessment_revisions_sanction_id",
        "functional_eval_assessment_revisions",
        ["sanction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_functional_eval_assessment_revisions_sanction_id",
        table_name="functional_eval_assessment_revisions",
    )
    op.drop_index(
        "ix_functional_eval_assessment_revisions_source",
        table_name="functional_eval_assessment_revisions",
    )
    op.drop_index(
        "ix_functional_eval_assessment_revisions_eval_type",
        table_name="functional_eval_assessment_revisions",
    )
    op.drop_index(
        "ix_functional_eval_assessment_revisions_worker_id",
        table_name="functional_eval_assessment_revisions",
    )
    op.drop_table("functional_eval_assessment_revisions")
