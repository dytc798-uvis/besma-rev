"""sync missing document period fields on legacy sqlite db

Revision ID: 20260319_0014
Revises: 20260319_0013
Create Date: 2026-03-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260319_0014"
down_revision = "20260319_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("documents")}

    with op.batch_alter_table("documents", schema=None) as batch_op:
        if "period_start" not in columns:
            batch_op.add_column(sa.Column("period_start", sa.Date(), nullable=True))
        if "period_end" not in columns:
            batch_op.add_column(sa.Column("period_end", sa.Date(), nullable=True))
        if "due_date" not in columns:
            batch_op.add_column(sa.Column("due_date", sa.Date(), nullable=True))
        if "source_type" not in columns:
            batch_op.add_column(
                sa.Column("source_type", sa.String(length=20), nullable=False, server_default="MANUAL")
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("documents")}

    with op.batch_alter_table("documents", schema=None) as batch_op:
        if "source_type" in columns:
            batch_op.drop_column("source_type")
        if "due_date" in columns:
            batch_op.drop_column("due_date")
        if "period_end" in columns:
            batch_op.drop_column("period_end")
        if "period_start" in columns:
            batch_op.drop_column("period_start")
