"""functional eval roster diff fields, mileage placeholder, import batches

Revision ID: 20260529_0055
Revises: 20260529_0054
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_0055"
down_revision = "20260529_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("functional_eval_workers") as batch_op:
        batch_op.add_column("phone_mobile", sa.String(length=30), nullable=True)
        batch_op.add_column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        batch_op.add_column("removed_at", sa.DateTime(), nullable=True)
        batch_op.add_column("mileage_points", sa.Integer(), nullable=False, server_default="0")
        batch_op.add_column("mileage_note", sa.String(length=500), nullable=True)
        batch_op.add_column("updated_at", sa.DateTime(), nullable=True)

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE functional_eval_workers SET updated_at = created_at WHERE updated_at IS NULL"
        )
    )
    with op.batch_alter_table("functional_eval_workers") as batch_op:
        batch_op.alter_column("updated_at", nullable=False)

    # rrn_hash backfill for legacy rows (empty hash -> delete orphans without hash)
    bind.execute(
        sa.text(
            "DELETE FROM functional_eval_sanctions WHERE worker_id IN "
            "(SELECT id FROM functional_eval_workers WHERE rrn_hash IS NULL OR rrn_hash = '')"
        )
    )
    bind.execute(
        sa.text("DELETE FROM functional_eval_workers WHERE rrn_hash IS NULL OR rrn_hash = ''")
    )

    with op.batch_alter_table("functional_eval_workers") as batch_op:
        batch_op.alter_column("rrn_hash", existing_type=sa.String(128), nullable=False)
        try:
            batch_op.drop_constraint("uq_fe_worker_period_site_row", type_="unique")
        except Exception:
            pass
        batch_op.create_unique_constraint("uq_fe_worker_period_rrn", ["period_id", "rrn_hash"])

    op.create_table(
        "functional_eval_roster_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("removed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("functional_eval_roster_import_batches")
    with op.batch_alter_table("functional_eval_workers") as batch_op:
        try:
            batch_op.drop_constraint("uq_fe_worker_period_rrn", type_="unique")
        except Exception:
            pass
        batch_op.create_unique_constraint("uq_fe_worker_period_site_row", ["period_id", "site_code", "row_no"])
        batch_op.drop_column("updated_at")
        batch_op.drop_column("mileage_note")
        batch_op.drop_column("mileage_points")
        batch_op.drop_column("removed_at")
        batch_op.drop_column("is_active")
        batch_op.drop_column("phone_mobile")
