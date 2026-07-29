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
    op.create_index("ix_auth_login_events_client_ip", "auth_login_events", ["client_ip"])
    op.create_index("ix_auth_login_events_created_at", "auth_login_events", ["created_at"])
    op.create_index("ix_auth_login_events_failure_reason", "auth_login_events", ["failure_reason"])
    op.create_index("ix_auth_login_events_login_id", "auth_login_events", ["login_id"])
    op.create_index("ix_auth_login_events_succeeded", "auth_login_events", ["succeeded"])
    op.create_index("ix_auth_login_events_user_id", "auth_login_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_auth_login_events_user_id", table_name="auth_login_events")
    op.drop_index("ix_auth_login_events_succeeded", table_name="auth_login_events")
    op.drop_index("ix_auth_login_events_login_id", table_name="auth_login_events")
    op.drop_index("ix_auth_login_events_failure_reason", table_name="auth_login_events")
    op.drop_index("ix_auth_login_events_created_at", table_name="auth_login_events")
    op.drop_index("ix_auth_login_events_client_ip", table_name="auth_login_events")
    op.drop_table("auth_login_events")
