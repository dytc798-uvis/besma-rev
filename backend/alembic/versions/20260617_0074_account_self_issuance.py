"""account self-issuance fields and logs

Revision ID: 20260617_0074
Revises: 20260616_0073
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260617_0074"
down_revision = "20260616_0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {c["name"] for c in inspector.get_columns("users")}

    if "initial_password_issued" not in user_cols:
        op.add_column(
            "users",
            sa.Column("initial_password_issued", sa.Boolean(), nullable=False, server_default="0"),
        )
    if "account_issued_by" not in user_cols:
        op.add_column("users", sa.Column("account_issued_by", sa.String(40), nullable=True))
    if "account_issued_at" not in user_cols:
        op.add_column("users", sa.Column("account_issued_at", sa.DateTime(), nullable=True))

    if not inspector.has_table("account_issuance_logs"):
        op.create_table(
            "account_issuance_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("issued_at", sa.DateTime(), nullable=False),
            sa.Column("scope", sa.String(20), nullable=False),
            sa.Column("site_code", sa.String(32), nullable=True),
            sa.Column("input_department", sa.String(100), nullable=True),
            sa.Column("input_name", sa.String(100), nullable=False),
            sa.Column("input_fingerprint", sa.String(64), nullable=False),
            sa.Column("recipient_name", sa.String(100), nullable=True),
            sa.Column("issued_account_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("issued_accounts_json", sa.Text(), nullable=True),
            sa.Column("request_ip", sa.String(64), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("failure_reason", sa.String(200), nullable=True),
        )
        op.create_index("ix_account_issuance_logs_issued_at", "account_issuance_logs", ["issued_at"])
        op.create_index(
            "ix_account_issuance_logs_input_fingerprint",
            "account_issuance_logs",
            ["input_fingerprint"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("account_issuance_logs"):
        op.drop_index("ix_account_issuance_logs_input_fingerprint", table_name="account_issuance_logs")
        op.drop_index("ix_account_issuance_logs_issued_at", table_name="account_issuance_logs")
        op.drop_table("account_issuance_logs")

    user_cols = {c["name"] for c in inspector.get_columns("users")}
    if "account_issued_at" in user_cols:
        op.drop_column("users", "account_issued_at")
    if "account_issued_by" in user_cols:
        op.drop_column("users", "account_issued_by")
    if "initial_password_issued" in user_cols:
        op.drop_column("users", "initial_password_issued")
