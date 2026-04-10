"""add worker voice item extra fields

Revision ID: 20260410_0023
Revises: 20260330_0022
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260410_0023"
down_revision = "20260330_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "worker_voice_items" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("worker_voice_items")}
    with op.batch_alter_table("worker_voice_items", schema=None) as batch_op:
        if "worker_birth_date" not in columns:
            batch_op.add_column(sa.Column("worker_birth_date", sa.String(length=30), nullable=True))
        if "worker_phone_number" not in columns:
            batch_op.add_column(sa.Column("worker_phone_number", sa.String(length=30), nullable=True))
        if "opinion_kind" not in columns:
            batch_op.add_column(sa.Column("opinion_kind", sa.String(length=50), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "worker_voice_items" not in tables:
        return

    columns = {c["name"] for c in inspector.get_columns("worker_voice_items")}
    with op.batch_alter_table("worker_voice_items", schema=None) as batch_op:
        if "opinion_kind" in columns:
            batch_op.drop_column("opinion_kind")
        if "worker_phone_number" in columns:
            batch_op.drop_column("worker_phone_number")
        if "worker_birth_date" in columns:
            batch_op.drop_column("worker_birth_date")
