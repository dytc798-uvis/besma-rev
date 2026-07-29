"""account and access request workflow

Revision ID: 20260729_0077
Revises: 20260624_0076
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260729_0077"
down_revision = "20260624_0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("temporary_password_expires_at", sa.DateTime(), nullable=True))

    op.create_table(
        "account_access_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_no", sa.String(32), nullable=False, unique=True),
        sa.Column("request_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("applicant_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("existing_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone_mobile", sa.String(30), nullable=False),
        sa.Column("company_name", sa.String(150), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("department", sa.String(100)),
        sa.Column("work_category", sa.String(40), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id")),
        sa.Column("site_code", sa.String(50)),
        sa.Column("site_name", sa.String(200)),
        sa.Column("request_reason", sa.Text(), nullable=False),
        sa.Column("employment_evidence_note", sa.Text()),
        sa.Column("privacy_consent_at", sa.DateTime(), nullable=False),
        sa.Column("roster_match_status", sa.String(30), nullable=False),
        sa.Column("duplicate_candidate_ids_json", sa.Text()),
        sa.Column("recommended_role", sa.String(50)),
        sa.Column("current_role_snapshot", sa.String(50)),
        sa.Column("current_site_id_snapshot", sa.Integer()),
        sa.Column("approved_role", sa.String(50)),
        sa.Column("approved_site_id", sa.Integer(), sa.ForeignKey("sites.id")),
        sa.Column("valid_until", sa.DateTime()),
        sa.Column("handled_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("handled_at", sa.DateTime()),
        sa.Column("decision_comment", sa.Text()),
        sa.Column("created_account_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in [
        "request_no",
        "request_type",
        "status",
        "applicant_user_id",
        "existing_user_id",
        "work_category",
        "site_id",
    ]:
        op.create_index(f"ix_account_access_requests_{column}", "account_access_requests", [column])

    op.create_table(
        "account_access_request_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("account_access_requests.id"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("actor_role", sa.String(50)),
        sa.Column("detail_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for column in ["request_id", "action", "actor_user_id"]:
        op.create_index(f"ix_account_access_request_events_{column}", "account_access_request_events", [column])


def downgrade() -> None:
    op.drop_table("account_access_request_events")
    op.drop_table("account_access_requests")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("temporary_password_expires_at")
