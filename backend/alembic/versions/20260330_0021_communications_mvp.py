"""add communications mvp tables

Revision ID: 20260330_0021
Revises: 20260330_0020
Create Date: 2026-03-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260330_0021"
down_revision = "20260330_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "communications" not in tables:
        op.create_table(
            "communications",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.Integer(), nullable=False),
            sa.Column("sender_user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
            sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_communications_id", "communications", ["id"], unique=False)
        op.create_index("ix_communications_site_id", "communications", ["site_id"], unique=False)
        op.create_index("ix_communications_sender_user_id", "communications", ["sender_user_id"], unique=False)

    if "communication_attachments" not in tables:
        op.create_table(
            "communication_attachments",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("communication_id", sa.Integer(), nullable=False),
            sa.Column("file_path", sa.String(length=500), nullable=False),
            sa.Column("original_name", sa.String(length=255), nullable=False),
            sa.Column("file_type", sa.String(length=50), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["communication_id"], ["communications.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_communication_attachments_id", "communication_attachments", ["id"], unique=False)
        op.create_index(
            "ix_communication_attachments_communication_id",
            "communication_attachments",
            ["communication_id"],
            unique=False,
        )

    if "communication_receivers" not in tables:
        op.create_table(
            "communication_receivers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("communication_id", sa.Integer(), nullable=False),
            sa.Column("receiver_user_id", sa.Integer(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["communication_id"], ["communications.id"]),
            sa.ForeignKeyConstraint(["receiver_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_communication_receivers_id", "communication_receivers", ["id"], unique=False)
        op.create_index(
            "ix_communication_receivers_communication_id",
            "communication_receivers",
            ["communication_id"],
            unique=False,
        )
        op.create_index(
            "ix_communication_receivers_receiver_user_id",
            "communication_receivers",
            ["receiver_user_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "communication_receivers" in tables:
        op.drop_index("ix_communication_receivers_receiver_user_id", table_name="communication_receivers")
        op.drop_index("ix_communication_receivers_communication_id", table_name="communication_receivers")
        op.drop_index("ix_communication_receivers_id", table_name="communication_receivers")
        op.drop_table("communication_receivers")

    if "communication_attachments" in tables:
        op.drop_index("ix_communication_attachments_communication_id", table_name="communication_attachments")
        op.drop_index("ix_communication_attachments_id", table_name="communication_attachments")
        op.drop_table("communication_attachments")

    if "communications" in tables:
        op.drop_index("ix_communications_sender_user_id", table_name="communications")
        op.drop_index("ix_communications_site_id", table_name="communications")
        op.drop_index("ix_communications_id", table_name="communications")
        op.drop_table("communications")

