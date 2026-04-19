"""add accident verification status and circumstance

Revision ID: 20260419_0039
Revises: 20260419_0038
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260419_0039"
down_revision = "20260419_0038"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "accidents" not in inspector.get_table_names():
        return

    with op.batch_alter_table("accidents") as batch_op:
        if not _has_column(inspector, "accidents", "accident_circumstance"):
            batch_op.add_column(sa.Column("accident_circumstance", sa.String(length=512), nullable=True))
        if not _has_column(inspector, "accidents", "verification_status"):
            batch_op.add_column(
                sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="미검증")
            )

    bind.execute(sa.text("UPDATE accidents SET verification_status = COALESCE(verification_status, '미검증')"))


def downgrade() -> None:
    pass
