"""functional eval viewer accounts and consent kind

Revision ID: 20260617_0075
Revises: 20260617_0074
Create Date: 2026-06-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260617_0075"
down_revision = "20260617_0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    consent_cols = {c["name"] for c in inspector.get_columns("functional_eval_consents")}
    if "consent_kind" not in consent_cols:
        op.add_column(
            "functional_eval_consents",
            sa.Column("consent_kind", sa.String(20), nullable=False, server_default="evaluator"),
        )

    if not inspector.has_table("fe_viewer_provision_logs"):
        op.create_table(
            "fe_viewer_provision_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("source_label", sa.String(255), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_by_login_id", sa.String(50), nullable=True),
            sa.Column("planned_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("excluded_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("applied_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        )
        op.create_index("ix_fe_viewer_provision_logs_created_at", "fe_viewer_provision_logs", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("fe_viewer_provision_logs"):
        op.drop_index("ix_fe_viewer_provision_logs_created_at", table_name="fe_viewer_provision_logs")
        op.drop_table("fe_viewer_provision_logs")
    consent_cols = {c["name"] for c in inspector.get_columns("functional_eval_consents")}
    if "consent_kind" in consent_cols:
        op.drop_column("functional_eval_consents", "consent_kind")
