"""functional eval accident histories

Revision ID: 20260629_0077
Revises: 20260622_0075
Create Date: 2026-06-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260629_0077"
down_revision = "20260622_0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_accident_histories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("source_sheet", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("accident_date", sa.Date(), nullable=True),
        sa.Column("worker_name", sa.String(length=100), nullable=False),
        sa.Column("birth6", sa.String(length=6), nullable=True),
        sa.Column("rrn_hash", sa.String(length=128), nullable=True),
        sa.Column("accident_site_name", sa.String(length=300), nullable=True),
        sa.Column("accident_type", sa.String(length=100), nullable=True),
        sa.Column("accident_reason", sa.Text(), nullable=True),
        sa.Column("prevention_note", sa.Text(), nullable=True),
        sa.Column("disease_name", sa.String(length=255), nullable=True),
        sa.Column("matched_worker_id", sa.Integer(), nullable=True),
        sa.Column("matched_period_id", sa.Integer(), nullable=True),
        sa.Column("matched_site_code", sa.String(length=50), nullable=True),
        sa.Column("match_status", sa.String(length=20), nullable=False, server_default="UNMATCHED"),
        sa.Column("safety_penalty_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("safety_penalty_points", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("sanction_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["matched_period_id"], ["functional_eval_periods.id"]),
        sa.ForeignKeyConstraint(["matched_worker_id"], ["functional_eval_workers.id"]),
        sa.ForeignKeyConstraint(["sanction_id"], ["functional_eval_sanctions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", name="uq_fe_accident_history_source_key"),
    )
    op.create_index("ix_fe_accident_history_accident_date", "functional_eval_accident_histories", ["accident_date"])
    op.create_index("ix_fe_accident_history_birth6", "functional_eval_accident_histories", ["birth6"])
    op.create_index("ix_fe_accident_history_match_status", "functional_eval_accident_histories", ["match_status"])
    op.create_index("ix_fe_accident_history_matched_period", "functional_eval_accident_histories", ["matched_period_id"])
    op.create_index("ix_fe_accident_history_matched_site", "functional_eval_accident_histories", ["matched_site_code"])
    op.create_index("ix_fe_accident_history_matched_worker", "functional_eval_accident_histories", ["matched_worker_id"])
    op.create_index("ix_fe_accident_history_rrn_hash", "functional_eval_accident_histories", ["rrn_hash"])
    op.create_index("ix_fe_accident_history_sanction", "functional_eval_accident_histories", ["sanction_id"])
    op.create_index("ix_fe_accident_history_source_key", "functional_eval_accident_histories", ["source_key"])
    op.create_index("ix_fe_accident_history_worker_name", "functional_eval_accident_histories", ["worker_name"])


def downgrade() -> None:
    op.drop_index("ix_fe_accident_history_worker_name", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_source_key", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_sanction", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_rrn_hash", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_matched_worker", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_matched_site", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_matched_period", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_match_status", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_birth6", table_name="functional_eval_accident_histories")
    op.drop_index("ix_fe_accident_history_accident_date", table_name="functional_eval_accident_histories")
    op.drop_table("functional_eval_accident_histories")
