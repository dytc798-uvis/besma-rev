"""users.password_changed_at

Revision ID: 20260414_0032
Revises: 20260414_0031
Create Date: 2026-04-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260414_0032"
down_revision = "20260414_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "password_changed_at" not in cols:
        op.add_column("users", sa.Column("password_changed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "password_changed_at" in cols:
        op.drop_column("users", "password_changed_at")
