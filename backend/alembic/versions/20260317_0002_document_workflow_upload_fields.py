"""document workflow fields (instance review + document file meta + instance_id)

Revision ID: 20260317_0002
Revises: 20260317_0001
Create Date: 2026-03-17

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260317_0002"
down_revision = "20260317_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    # document_instances: review meta columns
    if "document_instances" in tables:
        with op.batch_alter_table("document_instances", recreate="always") as batch:
            cols = {c["name"] for c in insp.get_columns("document_instances")}
            if "review_comment" not in cols:
                batch.add_column(sa.Column("review_comment", sa.String(length=500), nullable=True))
            if "reviewed_by_user_id" not in cols:
                batch.add_column(sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
            if "reviewed_at" not in cols:
                batch.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))

            # FK는 recreate 과정에서 누락될 수 있으므로 명시적으로 생성
            # (SQLite에서는 constraint name 관리가 제한적이어서 자동 name 사용)
            if "users" in tables:
                batch.create_foreign_key(
                    "fk_document_instances_reviewed_by_user_id",
                    "users",
                    ["reviewed_by_user_id"],
                    ["id"],
                )

    # documents: file meta + instance_id(UNIQUE)
    if "documents" in tables:
        with op.batch_alter_table("documents", recreate="always") as batch:
            cols = {c["name"] for c in insp.get_columns("documents")}
            if "file_name" not in cols:
                batch.add_column(sa.Column("file_name", sa.String(length=255), nullable=True))
            if "file_size" not in cols:
                batch.add_column(sa.Column("file_size", sa.Integer(), nullable=True))
            if "uploaded_by_user_id" not in cols:
                batch.add_column(sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True))
            if "uploaded_at" not in cols:
                batch.add_column(sa.Column("uploaded_at", sa.DateTime(), nullable=True))

            if "instance_id" not in cols:
                batch.add_column(sa.Column("instance_id", sa.Integer(), nullable=True))

            batch.create_unique_constraint("uq_documents_instance_id", ["instance_id"])
            if "users" in tables:
                batch.create_foreign_key(
                    "fk_documents_uploaded_by_user_id",
                    "users",
                    ["uploaded_by_user_id"],
                    ["id"],
                )
            if "document_instances" in tables:
                batch.create_foreign_key(
                    "fk_documents_instance_id",
                    "document_instances",
                    ["instance_id"],
                    ["id"],
                )

    # backfill: 기존 instance.document_id -> document.instance_id
    if "document_instances" in insp.get_table_names() and "documents" in insp.get_table_names():
        # documents.instance_id가 NULL인 경우만 채움
        op.execute(
            """
            UPDATE documents
            SET instance_id = (
              SELECT di.id FROM document_instances di
              WHERE di.document_id = documents.id
              LIMIT 1
            )
            WHERE instance_id IS NULL
              AND EXISTS (SELECT 1 FROM document_instances di WHERE di.document_id = documents.id)
            """
        )


def downgrade() -> None:
    pass

