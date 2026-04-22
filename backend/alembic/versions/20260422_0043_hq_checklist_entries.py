"""add hq checklist entries table

Revision ID: 20260422_0043
Revises: 20260420_0042
Create Date: 2026-04-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260422_0043"
down_revision = "20260420_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hq_checklist_entries" in inspector.get_table_names():
        return

    op.create_table(
        "hq_checklist_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("checklist_code", sa.String(length=50), nullable=False),
        sa.Column("checklist_title", sa.String(length=255), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("period_label", sa.String(length=50), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING_CONFIRM"),
        sa.Column("improvement_note", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("checked_by_user_id", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["checked_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hq_checklist_entries_checklist_code", "hq_checklist_entries", ["checklist_code"], unique=False)
    op.create_index("ix_hq_checklist_entries_period_label", "hq_checklist_entries", ["period_label"], unique=False)
    op.create_index("ix_hq_checklist_entries_target_date", "hq_checklist_entries", ["target_date"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hq_checklist_entries" not in inspector.get_table_names():
        return
    op.drop_index("ix_hq_checklist_entries_target_date", table_name="hq_checklist_entries")
    op.drop_index("ix_hq_checklist_entries_period_label", table_name="hq_checklist_entries")
    op.drop_index("ix_hq_checklist_entries_checklist_code", table_name="hq_checklist_entries")
    op.drop_table("hq_checklist_entries")
