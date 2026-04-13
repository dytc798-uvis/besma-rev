"""worker voice site reject fields + nonconformity item approval columns

Revision ID: 20260413_0030
Revises: 20260412_0029
Create Date: 2026-04-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260413_0030"
down_revision = "20260412_0029"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "worker_voice_items"):
        columns = _column_names(inspector, "worker_voice_items")
        with op.batch_alter_table("worker_voice_items", schema=None) as batch_op:
            if "site_rejected" not in columns:
                batch_op.add_column(sa.Column("site_rejected", sa.Boolean(), nullable=False, server_default=sa.false()))
            if "site_reject_note" not in columns:
                batch_op.add_column(sa.Column("site_reject_note", sa.Text(), nullable=True))
            if "site_rejected_at" not in columns:
                batch_op.add_column(sa.Column("site_rejected_at", sa.DateTime(), nullable=True))
            if "site_rejected_by_user_id" not in columns:
                batch_op.add_column(sa.Column("site_rejected_by_user_id", sa.Integer(), nullable=True))

    if _has_table(inspector, "nonconformity_items"):
        columns = _column_names(inspector, "nonconformity_items")
        with op.batch_alter_table("nonconformity_items", schema=None) as batch_op:
            for col, typ, default in (
                ("site_approved", sa.Boolean(), sa.false()),
                ("site_approved_by_user_id", sa.Integer(), None),
                ("site_approved_at", sa.DateTime(), None),
                ("site_rejected", sa.Boolean(), sa.false()),
                ("site_reject_note", sa.Text(), None),
                ("site_rejected_at", sa.DateTime(), None),
                ("site_rejected_by_user_id", sa.Integer(), None),
                ("hq_checked", sa.Boolean(), sa.false()),
                ("hq_checked_by_user_id", sa.Integer(), None),
                ("hq_checked_at", sa.DateTime(), None),
                ("reward_candidate", sa.Boolean(), sa.false()),
                ("reward_candidate_by_user_id", sa.Integer(), None),
                ("reward_candidate_at", sa.DateTime(), None),
            ):
                if col not in columns:
                    if default is not None:
                        batch_op.add_column(sa.Column(col, typ, nullable=False, server_default=default))
                    else:
                        batch_op.add_column(sa.Column(col, typ, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "nonconformity_items"):
        columns = _column_names(inspector, "nonconformity_items")
        with op.batch_alter_table("nonconformity_items", schema=None) as batch_op:
            for col in (
                "reward_candidate_at",
                "reward_candidate_by_user_id",
                "reward_candidate",
                "hq_checked_at",
                "hq_checked_by_user_id",
                "hq_checked",
                "site_rejected_by_user_id",
                "site_rejected_at",
                "site_reject_note",
                "site_rejected",
                "site_approved_at",
                "site_approved_by_user_id",
                "site_approved",
            ):
                if col in columns:
                    batch_op.drop_column(col)

    if _has_table(inspector, "worker_voice_items"):
        columns = _column_names(inspector, "worker_voice_items")
        with op.batch_alter_table("worker_voice_items", schema=None) as batch_op:
            for col in ("site_rejected_by_user_id", "site_rejected_at", "site_reject_note", "site_rejected"):
                if col in columns:
                    batch_op.drop_column(col)
