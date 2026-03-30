"""add document upload history table

Revision ID: 20260320_0018
Revises: 20260320_0017
Create Date: 2026-03-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260320_0018"
down_revision = "20260320_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "document_upload_histories" in tables:
        return

    op.create_table(
        "document_upload_histories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=True),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("action_type", sa.String(length=30), nullable=False, server_default="UPLOAD"),
        sa.Column("document_status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["document_instances.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_upload_histories_document_id",
        "document_upload_histories",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_upload_histories_instance_id",
        "document_upload_histories",
        ["instance_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "document_upload_histories" not in tables:
        return
    op.drop_index("ix_document_upload_histories_instance_id", table_name="document_upload_histories")
    op.drop_index("ix_document_upload_histories_document_id", table_name="document_upload_histories")
    op.drop_table("document_upload_histories")
