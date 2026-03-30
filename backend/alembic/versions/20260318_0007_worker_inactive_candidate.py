"""add worker_inactive_candidates table

Revision ID: 20260318_0007
Revises: 20260318_0006
Create Date: 2026-03-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260318_0007"
down_revision = "20260318_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "worker_inactive_candidates" in tables:
        return

    op.create_table(
        "worker_inactive_candidates",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("employment_id", sa.Integer(), sa.ForeignKey("employments.id"), nullable=True),
        sa.Column("rrn_hash", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False, server_default="employee"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="CANDIDATE"),
        sa.Column("resolution", sa.String(length=50), nullable=True),
        sa.Column("missing_streak", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "detected_in_batch_id",
            sa.Integer(),
            sa.ForeignKey("worker_import_batches.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
    )
    op.create_index(
        "ix_worker_inactive_candidates_id",
        "worker_inactive_candidates",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_worker_inactive_candidates_rrn_hash",
        "worker_inactive_candidates",
        ["rrn_hash"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "worker_inactive_candidates" not in tables:
        return
    op.drop_index("ix_worker_inactive_candidates_rrn_hash", table_name="worker_inactive_candidates")
    op.drop_index("ix_worker_inactive_candidates_id", table_name="worker_inactive_candidates")
    op.drop_table("worker_inactive_candidates")

