"""create document_communication_reads table

Revision ID: 20260512_0047
Revises: 20260514_0046
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260512_0047"
down_revision = "20260514_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_communication_reads" in inspector.get_table_names():
        return
    op.create_table(
        "document_communication_reads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("item_key", sa.String(length=80), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "item_key", name="uq_doc_comm_read_user_item"),
    )
    op.create_index(op.f("ix_document_communication_reads_id"), "document_communication_reads", ["id"], unique=False)
    op.create_index(op.f("ix_document_communication_reads_item_key"), "document_communication_reads", ["item_key"], unique=False)
    op.create_index(op.f("ix_document_communication_reads_user_id"), "document_communication_reads", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_communication_reads" not in inspector.get_table_names():
        return
    op.drop_index(op.f("ix_document_communication_reads_user_id"), table_name="document_communication_reads")
    op.drop_index(op.f("ix_document_communication_reads_item_key"), table_name="document_communication_reads")
    op.drop_index(op.f("ix_document_communication_reads_id"), table_name="document_communication_reads")
    op.drop_table("document_communication_reads")
