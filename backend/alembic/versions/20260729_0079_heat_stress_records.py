"""heat stress records and audit logs

Revision ID: 20260729_0079
Revises: 20260729_0078
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260729_0079"
down_revision = "20260729_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "heat_stress_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("measured_at", sa.DateTime(), nullable=False),
        sa.Column("work_location", sa.String(200), nullable=False),
        sa.Column("work_process", sa.String(200)),
        sa.Column("measurement_source", sa.String(20), nullable=False),
        sa.Column("air_temperature_c", sa.Float(), nullable=False),
        sa.Column("relative_humidity_pct", sa.Float(), nullable=False),
        sa.Column("apparent_temperature_c", sa.Float(), nullable=False),
        sa.Column("formula_version", sa.String(40), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("legal_guidance", sa.Text(), nullable=False),
        sa.Column("company_guidance", sa.Text(), nullable=False),
        sa.Column("actual_actions_json", sa.Text(), nullable=False),
        sa.Column("action_notes", sa.Text()),
        sa.Column("action_compliance", sa.String(30), nullable=False),
        sa.Column("recorder_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recorder_name", sa.String(100), nullable=False),
        sa.Column("recorder_signature_data", sa.Text(), nullable=False),
        sa.Column("recorder_signature_sha256", sa.String(64), nullable=False),
        sa.Column("recorder_signed_at", sa.DateTime(), nullable=False),
        sa.Column("confirmer_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("confirmer_name", sa.String(100)),
        sa.Column("confirmer_title", sa.String(100)),
        sa.Column("confirmer_signature_data", sa.Text()),
        sa.Column("confirmer_signature_sha256", sa.String(64)),
        sa.Column("confirmer_signed_at", sa.DateTime()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("template_code", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    for column in ("site_id", "measured_at", "apparent_temperature_c", "risk_level", "action_compliance", "status"):
        op.create_index(f"ix_heat_stress_records_{column}", "heat_stress_records", [column])
    op.create_table(
        "heat_stress_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("record_id", sa.Integer(), sa.ForeignKey("heat_stress_records.id"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_name", sa.String(100), nullable=False),
        sa.Column("detail_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_heat_stress_audit_logs_record_id", "heat_stress_audit_logs", ["record_id"])


def downgrade() -> None:
    op.drop_index("ix_heat_stress_audit_logs_record_id", table_name="heat_stress_audit_logs")
    op.drop_table("heat_stress_audit_logs")
    for column in ("status", "action_compliance", "risk_level", "apparent_temperature_c", "measured_at", "site_id"):
        op.drop_index(f"ix_heat_stress_records_{column}", table_name="heat_stress_records")
    op.drop_table("heat_stress_records")
