"""separate workflow_status from orchestration status

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260317_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "document_instances" in tables:
        with op.batch_alter_table("document_instances", recreate="always") as batch:
            cols = {c["name"] for c in insp.get_columns("document_instances")}
            if "workflow_status" not in cols:
                batch.add_column(
                    sa.Column(
                        "workflow_status",
                        sa.String(length=20),
                        nullable=False,
                        server_default="NOT_SUBMITTED",
                    )
                )

    if "document_review_histories" not in tables:
        op.create_table(
            "document_review_histories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("instance_id", sa.Integer(), sa.ForeignKey("document_instances.id"), nullable=False),
            sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
            sa.Column("action_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("action_type", sa.String(length=30), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("from_workflow_status", sa.String(length=20), nullable=True),
            sa.Column("to_workflow_status", sa.String(length=20), nullable=True),
            sa.Column("action_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_document_review_histories_instance_id",
            "document_review_histories",
            ["instance_id"],
        )
        op.create_index(
            "ix_document_review_histories_document_id",
            "document_review_histories",
            ["document_id"],
        )


def downgrade() -> None:
    pass

