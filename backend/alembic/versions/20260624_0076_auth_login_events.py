"""auth login event audit

Revision ID: 20260624_0076
Revises: 20260622_0075
Create Date: 2026-06-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260624_0076"
down_revision = "20260622_0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_login_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("login_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("failure_reason", sa.String(length=80), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("path", sa.String(length=120), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("client_ip", "created_at", "failure_reason", "login_id", "succeeded", "user_id"):
        op.create_index(f"ix_auth_login_events_{column}", "auth_login_events", [column])


def downgrade() -> None:
    for column in ("user_id", "succeeded", "login_id", "failure_reason", "created_at", "client_ip"):
        op.drop_index(f"ix_auth_login_events_{column}", table_name="auth_login_events")
    op.drop_table("auth_login_events")
