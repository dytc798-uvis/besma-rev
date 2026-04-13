"""ledger row: receipt / action vs risk DB promotion axes

Revision ID: 20260414_0031
Revises: 20260413_0030
Create Date: 2026-04-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260414_0031"
down_revision = "20260413_0030"
branch_labels = None
depends_on = None


def _has_table(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {c["name"] for c in inspector.get_columns(table_name)}


def _add_axis_columns(inspector: sa.Inspector, table: str) -> None:
    if not _has_table(inspector, table):
        return
    columns = _column_names(inspector, table)
    with op.batch_alter_table(table, schema=None) as batch_op:
        if "receipt_decision" not in columns:
            batch_op.add_column(
                sa.Column("receipt_decision", sa.String(length=20), nullable=False, server_default="pending")
            )
        if "site_action_comment" not in columns:
            batch_op.add_column(sa.Column("site_action_comment", sa.Text(), nullable=True))
        if "risk_db_request_status" not in columns:
            batch_op.add_column(
                sa.Column("risk_db_request_status", sa.String(length=20), nullable=False, server_default="pending")
            )
        if "risk_db_hq_status" not in columns:
            batch_op.add_column(
                sa.Column("risk_db_hq_status", sa.String(length=20), nullable=False, server_default="pending")
            )
        if "risk_db_requested_at" not in columns:
            batch_op.add_column(sa.Column("risk_db_requested_at", sa.DateTime(), nullable=True))
        if "risk_db_requested_by_user_id" not in columns:
            batch_op.add_column(sa.Column("risk_db_requested_by_user_id", sa.Integer(), nullable=True))
        if "risk_db_hq_decided_at" not in columns:
            batch_op.add_column(sa.Column("risk_db_hq_decided_at", sa.DateTime(), nullable=True))
        if "risk_db_hq_decided_by_user_id" not in columns:
            batch_op.add_column(sa.Column("risk_db_hq_decided_by_user_id", sa.Integer(), nullable=True))
        if "hq_review_comment" not in columns:
            batch_op.add_column(sa.Column("hq_review_comment", sa.Text(), nullable=True))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _add_axis_columns(inspector, "worker_voice_items")
    _add_axis_columns(inspector, "nonconformity_items")

    is_pg = bind.dialect.name == "postgresql"
    rej_cond = "site_rejected IS TRUE" if is_pg else "site_rejected = 1"
    acc_cond = "site_approved IS TRUE" if is_pg else "site_approved = 1"
    hq_cond = "hq_checked IS TRUE" if is_pg else "hq_checked = 1"

    # Backfill from legacy flags
    for table in ("worker_voice_items", "nonconformity_items"):
        if not _has_table(inspector, table):
            continue
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET receipt_decision = CASE
                    WHEN {rej_cond} THEN 'rejected'
                    WHEN {acc_cond} THEN 'accepted'
                    ELSE 'pending'
                END
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET risk_db_request_status = CASE
                    WHEN {hq_cond} THEN 'requested'
                    ELSE 'pending'
                END
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET risk_db_hq_status = CASE
                    WHEN {hq_cond} THEN 'approved'
                    ELSE 'pending'
                END
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET risk_db_requested_at = CASE
                    WHEN {hq_cond} THEN COALESCE(risk_db_requested_at, hq_checked_at)
                    ELSE risk_db_requested_at
                END
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET risk_db_hq_decided_at = CASE
                    WHEN {hq_cond} THEN COALESCE(risk_db_hq_decided_at, hq_checked_at)
                    ELSE risk_db_hq_decided_at
                END
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET risk_db_hq_decided_by_user_id = CASE
                    WHEN {hq_cond} THEN COALESCE(risk_db_hq_decided_by_user_id, hq_checked_by_user_id)
                    ELSE risk_db_hq_decided_by_user_id
                END
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET risk_db_requested_by_user_id = CASE
                    WHEN {hq_cond} THEN COALESCE(risk_db_requested_by_user_id, hq_checked_by_user_id)
                    ELSE risk_db_requested_by_user_id
                END
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in ("worker_voice_items", "nonconformity_items"):
        if not _has_table(inspector, table):
            continue
        cols = _column_names(inspector, table)
        with op.batch_alter_table(table, schema=None) as batch_op:
            for c in (
                "hq_review_comment",
                "risk_db_hq_decided_by_user_id",
                "risk_db_hq_decided_at",
                "risk_db_requested_by_user_id",
                "risk_db_requested_at",
                "risk_db_hq_status",
                "risk_db_request_status",
                "site_action_comment",
                "receipt_decision",
            ):
                if c in cols:
                    batch_op.drop_column(c)
