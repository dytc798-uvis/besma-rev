"""기능인제 동의서·단계별 서명

Revision ID: 20260614_0067
Revises: 20260611_0066
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260614_0067"
down_revision = "20260611_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "functional_eval_workers",
        sa.Column("evaluation_batch", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_functional_eval_workers_evaluation_batch",
        "functional_eval_workers",
        ["evaluation_batch"],
    )

    op.create_table(
        "functional_eval_consents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("login_id", sa.String(length=50), nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=False),
        sa.Column("signature_data", sa.Text(), nullable=False),
        sa.Column("signature_hash", sa.String(length=64), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column("signer_ip", sa.String(length=64), nullable=True),
        sa.Column("signer_user_agent", sa.Text(), nullable=True),
        sa.Column("signed_document_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_fe_consent_user"),
    )
    op.create_index("ix_functional_eval_consents_user_id", "functional_eval_consents", ["user_id"])
    op.create_index("ix_functional_eval_consents_login_id", "functional_eval_consents", ["login_id"])

    op.create_table(
        "functional_eval_signatures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
        sa.Column("evaluation_batch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("site_code", sa.String(length=50), nullable=True),
        sa.Column("team_leader_login_id", sa.String(length=50), nullable=True),
        sa.Column("signer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("signer_login_id", sa.String(length=50), nullable=False),
        sa.Column("signer_name", sa.String(length=100), nullable=False),
        sa.Column("scope_label", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("worker_scope_json", sa.JSON(), nullable=True),
        sa.Column("signature_data", sa.Text(), nullable=False),
        sa.Column("signature_hash", sa.String(length=64), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column("signer_ip", sa.String(length=64), nullable=True),
        sa.Column("signer_user_agent", sa.Text(), nullable=True),
        sa.Column("signed_document_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "period_id",
            "evaluation_batch",
            "stage",
            "site_code",
            "team_leader_login_id",
            name="uq_fe_signature_scope",
        ),
    )
    op.create_index("ix_functional_eval_signatures_period_id", "functional_eval_signatures", ["period_id"])
    op.create_index("ix_functional_eval_signatures_evaluation_batch", "functional_eval_signatures", ["evaluation_batch"])
    op.create_index("ix_functional_eval_signatures_stage", "functional_eval_signatures", ["stage"])
    op.create_index("ix_functional_eval_signatures_site_code", "functional_eval_signatures", ["site_code"])
    op.create_index("ix_functional_eval_signatures_team_leader_login_id", "functional_eval_signatures", ["team_leader_login_id"])
    op.create_index("ix_functional_eval_signatures_signer_user_id", "functional_eval_signatures", ["signer_user_id"])


def downgrade() -> None:
    op.drop_table("functional_eval_signatures")
    op.drop_table("functional_eval_consents")
    op.drop_index("ix_functional_eval_workers_evaluation_batch", table_name="functional_eval_workers")
    op.drop_column("functional_eval_workers", "evaluation_batch")
