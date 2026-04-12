"""add document comments table

Revision ID: 20260412_0029
Revises: 20260412_0028
Create Date: 2026-04-12 22:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260412_0029"
down_revision = "20260412_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_role", sa.String(length=10), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["document_instances.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_comments_document_id"), "document_comments", ["document_id"], unique=False)
    op.create_index(op.f("ix_document_comments_id"), "document_comments", ["id"], unique=False)
    op.create_index(op.f("ix_document_comments_instance_id"), "document_comments", ["instance_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_comments_instance_id"), table_name="document_comments")
    op.drop_index(op.f("ix_document_comments_id"), table_name="document_comments")
    op.drop_index(op.f("ix_document_comments_document_id"), table_name="document_comments")
    op.drop_table("document_comments")
