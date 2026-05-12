"""document instance feedback loop tracking

Revision ID: 20260512_0048
Revises: 20260512_0047
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260512_0048"
down_revision = "20260512_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_instance_feedback_loops" in inspector.get_table_names():
        return
    op.create_table(
        "document_instance_feedback_loops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("improvement_due_date", sa.Date(), nullable=True),
        sa.Column("assignee_user_id", sa.Integer(), nullable=True),
        sa.Column("improvement_note", sa.Text(), nullable=True),
        sa.Column("improvement_requested_at", sa.DateTime(), nullable=True),
        sa.Column("improvement_requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("site_reuploaded_at", sa.DateTime(), nullable=True),
        sa.Column("hq_reviewing_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["improvement_requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["document_instances.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instance_id", name="uq_document_instance_feedback_loops_instance"),
    )
    op.create_index(
        op.f("ix_document_instance_feedback_loops_id"),
        "document_instance_feedback_loops",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_instance_feedback_loops_instance_id"),
        "document_instance_feedback_loops",
        ["instance_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_document_instance_feedback_loops_status"),
        "document_instance_feedback_loops",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_instance_feedback_loops_improvement_due_date"),
        "document_instance_feedback_loops",
        ["improvement_due_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_instance_feedback_loops_assignee_user_id"),
        "document_instance_feedback_loops",
        ["assignee_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_instance_feedback_loops_assignee_user_id"), table_name="document_instance_feedback_loops")
    op.drop_index(op.f("ix_document_instance_feedback_loops_improvement_due_date"), table_name="document_instance_feedback_loops")
    op.drop_index(op.f("ix_document_instance_feedback_loops_status"), table_name="document_instance_feedback_loops")
    op.drop_index(op.f("ix_document_instance_feedback_loops_instance_id"), table_name="document_instance_feedback_loops")
    op.drop_index(op.f("ix_document_instance_feedback_loops_id"), table_name="document_instance_feedback_loops")
    op.drop_table("document_instance_feedback_loops")
