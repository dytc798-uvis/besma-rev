"""functional eval ERP attendance daily snapshot

Revision ID: 20260529_0057
Revises: 20260529_0056
Create Date: 2026-05-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260529_0057"
down_revision = "20260529_0056"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "functional_eval_periods" in inspector.get_table_names():
        with op.batch_alter_table("functional_eval_periods") as batch_op:
            if not _has_column(inspector, "functional_eval_periods", "last_attendance_date"):
                batch_op.add_column(sa.Column("last_attendance_date", sa.Date(), nullable=True))

    if "functional_eval_workers" in inspector.get_table_names():
        with op.batch_alter_table("functional_eval_workers") as batch_op:
            if not _has_column(inspector, "functional_eval_workers", "is_on_reference_roster"):
                batch_op.add_column(
                    sa.Column(
                        "is_on_reference_roster",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("1"),
                    )
                )
        bind.execute(
            sa.text(
                "UPDATE functional_eval_workers SET is_on_reference_roster = 1 "
                "WHERE is_on_reference_roster IS NULL"
            )
        )

    if "functional_eval_attendance_import_batches" not in inspector.get_table_names():
        op.create_table(
            "functional_eval_attendance_import_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("original_filename", sa.String(255), nullable=False),
            sa.Column("stored_path", sa.String(500), nullable=False),
            sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("linked_workers", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("skipped_no_roster", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_fe_attendance_batch_period_date",
            "functional_eval_attendance_import_batches",
            ["period_id", "work_date"],
        )

    inspector = sa.inspect(bind)
    if "functional_eval_attendance_entries" not in inspector.get_table_names():
        op.create_table(
            "functional_eval_attendance_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("period_id", sa.Integer(), sa.ForeignKey("functional_eval_periods.id"), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("worker_id", sa.Integer(), sa.ForeignKey("functional_eval_workers.id"), nullable=True),
            sa.Column("site_code", sa.String(50), nullable=False),
            sa.Column("rrn_hash", sa.String(128), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("job_name", sa.String(100), nullable=True),
            sa.Column("erp_site_label", sa.String(500), nullable=True),
            sa.Column(
                "batch_id",
                sa.Integer(),
                sa.ForeignKey("functional_eval_attendance_import_batches.id"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("period_id", "work_date", "rrn_hash", name="uq_fe_attendance_period_date_rrn"),
        )
        op.create_index("ix_fe_attendance_entry_period", "functional_eval_attendance_entries", ["period_id"])
        op.create_index("ix_fe_attendance_entry_site", "functional_eval_attendance_entries", ["site_code"])
        op.create_index("ix_fe_attendance_entry_date", "functional_eval_attendance_entries", ["work_date"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "functional_eval_attendance_entries" in inspector.get_table_names():
        op.drop_table("functional_eval_attendance_entries")
    if "functional_eval_attendance_import_batches" in inspector.get_table_names():
        op.drop_table("functional_eval_attendance_import_batches")
    if "functional_eval_workers" in inspector.get_table_names():
        with op.batch_alter_table("functional_eval_workers") as batch_op:
            if _has_column(inspector, "functional_eval_workers", "is_on_reference_roster"):
                batch_op.drop_column("is_on_reference_roster")
    if "functional_eval_periods" in inspector.get_table_names():
        with op.batch_alter_table("functional_eval_periods") as batch_op:
            if _has_column(inspector, "functional_eval_periods", "last_attendance_date"):
                batch_op.drop_column("last_attendance_date")
