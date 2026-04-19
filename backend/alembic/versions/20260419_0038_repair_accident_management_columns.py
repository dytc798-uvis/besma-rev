"""repair missing accident management columns

Revision ID: 20260419_0038
Revises: 20260419_0037
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260419_0038"
down_revision = "20260419_0037"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "accidents" not in inspector.get_table_names():
        return

    with op.batch_alter_table("accidents") as batch_op:
        if not _has_column(inspector, "accidents", "accident_id"):
            batch_op.add_column(sa.Column("accident_id", sa.String(length=32), nullable=True))
        if not _has_column(inspector, "accidents", "status"):
            batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="신규"))
        if not _has_column(inspector, "accidents", "management_category"):
            batch_op.add_column(
                sa.Column("management_category", sa.String(length=32), nullable=False, server_default="일반")
            )
        if not _has_column(inspector, "accidents", "site_standard_name"):
            batch_op.add_column(sa.Column("site_standard_name", sa.String(length=255), nullable=True))
        if not _has_column(inspector, "accidents", "initial_report_template"):
            batch_op.add_column(sa.Column("initial_report_template", sa.Text(), nullable=True))
        if not _has_column(inspector, "accidents", "is_complete"):
            batch_op.add_column(sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.text("0")))
        if not _has_column(inspector, "accidents", "nas_folder_path"):
            batch_op.add_column(sa.Column("nas_folder_path", sa.String(length=1024), nullable=True))
        if not _has_column(inspector, "accidents", "nas_folder_key"):
            batch_op.add_column(sa.Column("nas_folder_key", sa.String(length=255), nullable=True))
        if not _has_column(inspector, "accidents", "notes"):
            batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        if not _has_column(inspector, "accidents", "updated_by_user_id"):
            batch_op.add_column(sa.Column("updated_by_user_id", sa.Integer(), nullable=True))

    bind.execute(
        sa.text(
            """
            UPDATE accidents
            SET accident_id = COALESCE(
                accident_id,
                substr(display_code, 5, 4) || '-' || printf('%03d', id)
            )
            """
        )
    )
    bind.execute(sa.text("UPDATE accidents SET site_standard_name = COALESCE(site_standard_name, site_name)"))
    bind.execute(sa.text("UPDATE accidents SET nas_folder_key = COALESCE(nas_folder_key, accident_id)"))
    bind.execute(sa.text("UPDATE accidents SET status = COALESCE(status, '신규')"))
    bind.execute(sa.text("UPDATE accidents SET management_category = COALESCE(management_category, '일반')"))

    refreshed = sa.inspect(bind)
    if not _has_index(refreshed, "accidents", "ix_accidents_accident_id"):
        op.create_index("ix_accidents_accident_id", "accidents", ["accident_id"], unique=True)
    if not _has_index(refreshed, "accidents", "ix_accidents_nas_folder_key"):
        op.create_index("ix_accidents_nas_folder_key", "accidents", ["nas_folder_key"], unique=False)
    if not _has_index(refreshed, "accidents", "ix_accidents_updated_by_user_id"):
        op.create_index("ix_accidents_updated_by_user_id", "accidents", ["updated_by_user_id"], unique=False)


def downgrade() -> None:
    pass
