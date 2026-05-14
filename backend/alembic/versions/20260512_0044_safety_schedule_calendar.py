"""safety schedule calendar + date proposals

Revision ID: 20260512_0044
Revises: 20260422_0043
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260512_0044"
down_revision = "20260422_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_entries" not in inspector.get_table_names():
        op.create_table(
            "safety_schedule_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("import_key", sa.String(length=120), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("inspector_label", sa.String(length=300), nullable=False),
            sa.Column("detail_text", sa.Text(), nullable=True),
            sa.Column("scheduled_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("import_key"),
        )
        op.create_index(
            "ix_safety_schedule_entries_scheduled_date",
            "safety_schedule_entries",
            ["scheduled_date"],
            unique=False,
        )
    if "safety_schedule_date_proposals" not in inspector.get_table_names():
        op.create_table(
            "safety_schedule_date_proposals",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("proposed_by_user_id", sa.Integer(), nullable=False),
            sa.Column("proposed_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
            sa.Column("decision_note", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["entry_id"], ["safety_schedule_entries.id"]),
            sa.ForeignKeyConstraint(["proposed_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_safety_schedule_date_proposals_entry_id",
            "safety_schedule_date_proposals",
            ["entry_id"],
            unique=False,
        )
        op.create_index(
            "ix_safety_schedule_date_proposals_proposed_by_user_id",
            "safety_schedule_date_proposals",
            ["proposed_by_user_id"],
            unique=False,
        )
        op.create_index(
            "ix_safety_schedule_date_proposals_status",
            "safety_schedule_date_proposals",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_date_proposals" in inspector.get_table_names():
        op.drop_index("ix_safety_schedule_date_proposals_status", table_name="safety_schedule_date_proposals")
        op.drop_index("ix_safety_schedule_date_proposals_proposed_by_user_id", table_name="safety_schedule_date_proposals")
        op.drop_index("ix_safety_schedule_date_proposals_entry_id", table_name="safety_schedule_date_proposals")
        op.drop_table("safety_schedule_date_proposals")
    if "safety_schedule_entries" in inspector.get_table_names():
        op.drop_index("ix_safety_schedule_entries_scheduled_date", table_name="safety_schedule_entries")
        op.drop_table("safety_schedule_entries")
