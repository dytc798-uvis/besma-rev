"""add user map_preference

Revision ID: 20260330_0022
Revises: 20260330_0021
Create Date: 2026-03-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260330_0022"
down_revision = "20260330_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("users")}
    if "map_preference" not in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("map_preference", sa.String(length=20), nullable=True, server_default="NAVER"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("users")}
    if "map_preference" in columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.drop_column("map_preference")

