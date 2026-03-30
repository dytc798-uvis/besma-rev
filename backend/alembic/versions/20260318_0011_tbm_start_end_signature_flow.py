"""add start/end signature fields for tbm flow

Revision ID: 20260318_0011
Revises: 20260318_0010
Create Date: 2026-03-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260318_0011"
down_revision = "20260318_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("daily_work_plan_distribution_workers")}
    with op.batch_alter_table("daily_work_plan_distribution_workers", schema=None) as batch_op:
        if "start_signed_at" not in columns:
            batch_op.add_column(sa.Column("start_signed_at", sa.DateTime(), nullable=True))
        if "start_signature_data" not in columns:
            batch_op.add_column(sa.Column("start_signature_data", sa.Text(), nullable=True))
        if "start_signature_mime" not in columns:
            batch_op.add_column(sa.Column("start_signature_mime", sa.String(length=50), nullable=True))
        if "start_signature_hash" not in columns:
            batch_op.add_column(sa.Column("start_signature_hash", sa.String(length=128), nullable=True))
        if "end_signed_at" not in columns:
            batch_op.add_column(sa.Column("end_signed_at", sa.DateTime(), nullable=True))
        if "end_status" not in columns:
            batch_op.add_column(sa.Column("end_status", sa.String(length=20), nullable=True))
        if "issue_flag" not in columns:
            batch_op.add_column(
                sa.Column(
                    "issue_flag",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )
        if "end_signature_data" not in columns:
            batch_op.add_column(sa.Column("end_signature_data", sa.Text(), nullable=True))
        if "end_signature_mime" not in columns:
            batch_op.add_column(sa.Column("end_signature_mime", sa.String(length=50), nullable=True))
        if "end_signature_hash" not in columns:
            batch_op.add_column(sa.Column("end_signature_hash", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("daily_work_plan_distribution_workers", schema=None) as batch_op:
        batch_op.drop_column("end_signature_hash")
        batch_op.drop_column("end_signature_mime")
        batch_op.drop_column("end_signature_data")
        batch_op.drop_column("issue_flag")
        batch_op.drop_column("end_status")
        batch_op.drop_column("end_signed_at")
        batch_op.drop_column("start_signature_hash")
        batch_op.drop_column("start_signature_mime")
        batch_op.drop_column("start_signature_data")
        batch_op.drop_column("start_signed_at")
