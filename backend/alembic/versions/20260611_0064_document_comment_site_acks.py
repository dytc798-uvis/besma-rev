"""document comment site-level acknowledgments

Revision ID: 20260611_0064
Revises: 20260608_0063
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260611_0064"
down_revision = "20260608_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_comment_site_acks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("acknowledged_by_user_id", sa.Integer(), nullable=False),
        sa.Column("ack_kind", sa.String(length=20), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["comment_id"], ["document_comments.id"]),
        sa.ForeignKeyConstraint(["acknowledged_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "comment_id", name="uq_doc_comment_site_ack"),
    )
    op.create_index("ix_doc_comment_site_acks_site_id", "document_comment_site_acks", ["site_id"])
    op.create_index("ix_doc_comment_site_acks_comment_id", "document_comment_site_acks", ["comment_id"])


def downgrade() -> None:
    op.drop_index("ix_doc_comment_site_acks_comment_id", table_name="document_comment_site_acks")
    op.drop_index("ix_doc_comment_site_acks_site_id", table_name="document_comment_site_acks")
    op.drop_table("document_comment_site_acks")
