"""expand ledger rows for manual management

Revision ID: 20260412_0024
Revises: 20260410_0023
Create Date: 2026-04-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260412_0024"
down_revision = "20260412_0026"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "worker_voice_ledgers"):
        columns = _column_names(inspector, "worker_voice_ledgers")
        with op.batch_alter_table("worker_voice_ledgers", schema=None) as batch_op:
            if "source_type" not in columns:
                batch_op.add_column(
                    sa.Column("source_type", sa.String(length=20), nullable=False, server_default="IMPORT")
                )

    if _has_table(inspector, "nonconformity_ledgers"):
        columns = _column_names(inspector, "nonconformity_ledgers")
        with op.batch_alter_table("nonconformity_ledgers", schema=None) as batch_op:
            if "source_type" not in columns:
                batch_op.add_column(
                    sa.Column("source_type", sa.String(length=20), nullable=False, server_default="IMPORT")
                )

    if _has_table(inspector, "worker_voice_items"):
        columns = _column_names(inspector, "worker_voice_items")
        with op.batch_alter_table("worker_voice_items", schema=None) as batch_op:
            if "action_before" not in columns:
                batch_op.add_column(sa.Column("action_before", sa.Text(), nullable=True))
            if "action_after" not in columns:
                batch_op.add_column(sa.Column("action_after", sa.Text(), nullable=True))
            if "action_status" not in columns:
                batch_op.add_column(sa.Column("action_status", sa.String(length=30), nullable=True))
            if "action_owner" not in columns:
                batch_op.add_column(sa.Column("action_owner", sa.String(length=100), nullable=True))
            if "before_photo_path" not in columns:
                batch_op.add_column(sa.Column("before_photo_path", sa.String(length=500), nullable=True))
            if "after_photo_path" not in columns:
                batch_op.add_column(sa.Column("after_photo_path", sa.String(length=500), nullable=True))

    if _has_table(inspector, "nonconformity_items"):
        columns = _column_names(inspector, "nonconformity_items")
        with op.batch_alter_table("nonconformity_items", schema=None) as batch_op:
            if "action_before" not in columns:
                batch_op.add_column(sa.Column("action_before", sa.Text(), nullable=True))
            if "action_status" not in columns:
                batch_op.add_column(sa.Column("action_status", sa.String(length=30), nullable=True))
            if "action_due_date" not in columns:
                batch_op.add_column(sa.Column("action_due_date", sa.Date(), nullable=True))
            if "before_photo_path" not in columns:
                batch_op.add_column(sa.Column("before_photo_path", sa.String(length=500), nullable=True))
            if "after_photo_path" not in columns:
                batch_op.add_column(sa.Column("after_photo_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "nonconformity_items"):
        columns = _column_names(inspector, "nonconformity_items")
        with op.batch_alter_table("nonconformity_items", schema=None) as batch_op:
            if "after_photo_path" in columns:
                batch_op.drop_column("after_photo_path")
            if "before_photo_path" in columns:
                batch_op.drop_column("before_photo_path")
            if "action_due_date" in columns:
                batch_op.drop_column("action_due_date")
            if "action_status" in columns:
                batch_op.drop_column("action_status")
            if "action_before" in columns:
                batch_op.drop_column("action_before")

    if _has_table(inspector, "worker_voice_items"):
        columns = _column_names(inspector, "worker_voice_items")
        with op.batch_alter_table("worker_voice_items", schema=None) as batch_op:
            if "after_photo_path" in columns:
                batch_op.drop_column("after_photo_path")
            if "before_photo_path" in columns:
                batch_op.drop_column("before_photo_path")
            if "action_owner" in columns:
                batch_op.drop_column("action_owner")
            if "action_status" in columns:
                batch_op.drop_column("action_status")
            if "action_after" in columns:
                batch_op.drop_column("action_after")
            if "action_before" in columns:
                batch_op.drop_column("action_before")

    if _has_table(inspector, "nonconformity_ledgers"):
        columns = _column_names(inspector, "nonconformity_ledgers")
        with op.batch_alter_table("nonconformity_ledgers", schema=None) as batch_op:
            if "source_type" in columns:
                batch_op.drop_column("source_type")

    if _has_table(inspector, "worker_voice_ledgers"):
        columns = _column_names(inspector, "worker_voice_ledgers")
        with op.batch_alter_table("worker_voice_ledgers", schema=None) as batch_op:
            if "source_type" in columns:
                batch_op.drop_column("source_type")
