"""add feedback and reassignment support

Revision ID: 20260320_0016
Revises: 20260320_0015
Create Date: 2026-03-20

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260320_0016"
down_revision = "20260320_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("daily_work_plan_distributions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_distribution_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_reassignment",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("reassignment_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("reassigned_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("reassigned_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            "ix_daily_work_plan_distributions_parent_distribution_id",
            ["parent_distribution_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_daily_work_plan_distributions_reassigned_by_user_id",
            ["reassigned_by_user_id"],
            unique=False,
        )
        batch_op.create_foreign_key(
            "fk_daily_work_plan_distributions_parent_distribution_id",
            "daily_work_plan_distributions",
            ["parent_distribution_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_daily_work_plan_distributions_reassigned_by_user_id",
            "users",
            ["reassigned_by_user_id"],
            ["id"],
        )

    op.create_table(
        "worker_feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("distribution_id", sa.Integer(), nullable=False),
        sa.Column("distribution_worker_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("plan_item_id", sa.Integer(), nullable=True),
        sa.Column("feedback_type", sa.String(length=20), nullable=False, server_default="other"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["distribution_id"], ["daily_work_plan_distributions.id"]),
        sa.ForeignKeyConstraint(
            ["distribution_worker_id"],
            ["daily_work_plan_distribution_workers.id"],
        ),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
        sa.ForeignKeyConstraint(["plan_id"], ["daily_work_plans.id"]),
        sa.ForeignKeyConstraint(["plan_item_id"], ["daily_work_plan_items.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
    )
    op.create_index("ix_worker_feedbacks_distribution_id", "worker_feedbacks", ["distribution_id"])
    op.create_index(
        "ix_worker_feedbacks_distribution_worker_id",
        "worker_feedbacks",
        ["distribution_worker_id"],
    )
    op.create_index("ix_worker_feedbacks_person_id", "worker_feedbacks", ["person_id"])
    op.create_index("ix_worker_feedbacks_plan_id", "worker_feedbacks", ["plan_id"])
    op.create_index("ix_worker_feedbacks_plan_item_id", "worker_feedbacks", ["plan_item_id"])
    op.create_index(
        "ix_worker_feedbacks_reviewed_by_user_id",
        "worker_feedbacks",
        ["reviewed_by_user_id"],
    )

    op.create_table(
        "risk_library_feedback_candidates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), nullable=False),
        sa.Column("inferred_unit_work", sa.String(length=100), nullable=True),
        sa.Column("inferred_process", sa.Text(), nullable=True),
        sa.Column("inferred_risk_factor", sa.Text(), nullable=True),
        sa.Column("inferred_countermeasure", sa.Text(), nullable=True),
        sa.Column("source_distribution_id", sa.Integer(), nullable=False),
        sa.Column("source_plan_item_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["feedback_id"], ["worker_feedbacks.id"]),
        sa.ForeignKeyConstraint(["source_distribution_id"], ["daily_work_plan_distributions.id"]),
        sa.ForeignKeyConstraint(["source_plan_item_id"], ["daily_work_plan_items.id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("feedback_id"),
    )
    op.create_index(
        "ix_risk_library_feedback_candidates_feedback_id",
        "risk_library_feedback_candidates",
        ["feedback_id"],
    )
    op.create_index(
        "ix_risk_library_feedback_candidates_source_distribution_id",
        "risk_library_feedback_candidates",
        ["source_distribution_id"],
    )
    op.create_index(
        "ix_risk_library_feedback_candidates_source_plan_item_id",
        "risk_library_feedback_candidates",
        ["source_plan_item_id"],
    )
    op.create_index(
        "ix_risk_library_feedback_candidates_approved_by_user_id",
        "risk_library_feedback_candidates",
        ["approved_by_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_library_feedback_candidates_approved_by_user_id",
        table_name="risk_library_feedback_candidates",
    )
    op.drop_index(
        "ix_risk_library_feedback_candidates_source_plan_item_id",
        table_name="risk_library_feedback_candidates",
    )
    op.drop_index(
        "ix_risk_library_feedback_candidates_source_distribution_id",
        table_name="risk_library_feedback_candidates",
    )
    op.drop_index(
        "ix_risk_library_feedback_candidates_feedback_id",
        table_name="risk_library_feedback_candidates",
    )
    op.drop_table("risk_library_feedback_candidates")

    op.drop_index("ix_worker_feedbacks_reviewed_by_user_id", table_name="worker_feedbacks")
    op.drop_index("ix_worker_feedbacks_plan_item_id", table_name="worker_feedbacks")
    op.drop_index("ix_worker_feedbacks_plan_id", table_name="worker_feedbacks")
    op.drop_index("ix_worker_feedbacks_person_id", table_name="worker_feedbacks")
    op.drop_index(
        "ix_worker_feedbacks_distribution_worker_id",
        table_name="worker_feedbacks",
    )
    op.drop_index("ix_worker_feedbacks_distribution_id", table_name="worker_feedbacks")
    op.drop_table("worker_feedbacks")

    with op.batch_alter_table("daily_work_plan_distributions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_daily_work_plan_distributions_reassigned_by_user_id",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_daily_work_plan_distributions_parent_distribution_id",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_daily_work_plan_distributions_reassigned_by_user_id")
        batch_op.drop_index("ix_daily_work_plan_distributions_parent_distribution_id")
        batch_op.drop_column("reassigned_at")
        batch_op.drop_column("reassigned_by_user_id")
        batch_op.drop_column("reassignment_reason")
        batch_op.drop_column("is_reassignment")
        batch_op.drop_column("parent_distribution_id")
