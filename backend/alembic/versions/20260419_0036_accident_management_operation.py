"""accident management operation tables and role expansion

Revision ID: 20260419_0036
Revises: 20260417_0035
Create Date: 2026-04-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260419_0036"
down_revision = "20260417_0035"
branch_labels = None
depends_on = None


OLD_ROLE_ENUM = sa.Enum(
    "HQ_SAFE",
    "SITE",
    "HQ_OTHER",
    "WORKER",
    "HQ_SAFE_ADMIN",
    "SUPER_ADMIN",
    name="role",
)


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(ix["name"] == index_name for ix in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "users" in tables and _has_column(inspector, "users", "role"):
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "role",
                existing_type=OLD_ROLE_ENUM,
                type_=sa.String(length=32),
                existing_nullable=False,
            )

    if "accidents" in tables:
        accident_columns = {col["name"] for col in inspector.get_columns("accidents")}
        with op.batch_alter_table("accidents") as batch_op:
            if "accident_id" not in accident_columns:
                batch_op.add_column(sa.Column("accident_id", sa.String(length=32), nullable=True))
            if "status" not in accident_columns:
                batch_op.add_column(
                    sa.Column("status", sa.String(length=32), nullable=False, server_default="신규")
                )
            if "management_category" not in accident_columns:
                batch_op.add_column(
                    sa.Column("management_category", sa.String(length=32), nullable=False, server_default="일반")
                )
            if "site_standard_name" not in accident_columns:
                batch_op.add_column(sa.Column("site_standard_name", sa.String(length=255), nullable=True))
            if "initial_report_template" not in accident_columns:
                batch_op.add_column(sa.Column("initial_report_template", sa.Text(), nullable=True))
            if "is_complete" not in accident_columns:
                batch_op.add_column(
                    sa.Column("is_complete", sa.Boolean(), nullable=False, server_default=sa.text("0"))
                )
            if "nas_folder_path" not in accident_columns:
                batch_op.add_column(sa.Column("nas_folder_path", sa.String(length=1024), nullable=True))
            if "nas_folder_key" not in accident_columns:
                batch_op.add_column(sa.Column("nas_folder_key", sa.String(length=255), nullable=True))
            if "notes" not in accident_columns:
                batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
            if "updated_by_user_id" not in accident_columns:
                batch_op.add_column(sa.Column("updated_by_user_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_accidents_updated_by_user_id_users",
                    "users",
                    ["updated_by_user_id"],
                    ["id"],
                )

        bind.execute(
            sa.text(
                "UPDATE accidents SET accident_id = COALESCE(accident_id, substr(display_code, 5, 4) || '-' || substr(display_code, 10, 3))"
            )
        )
        bind.execute(
            sa.text("UPDATE accidents SET site_standard_name = COALESCE(site_standard_name, site_name)")
        )
        bind.execute(
            sa.text("UPDATE accidents SET nas_folder_key = COALESCE(nas_folder_key, accident_id)")
        )

        refreshed = sa.inspect(bind)
        if not _has_index(refreshed, "accidents", "ix_accidents_accident_id"):
            op.create_index("ix_accidents_accident_id", "accidents", ["accident_id"], unique=True)
        if not _has_index(refreshed, "accidents", "ix_accidents_nas_folder_key"):
            op.create_index("ix_accidents_nas_folder_key", "accidents", ["nas_folder_key"], unique=False)
        if not _has_index(refreshed, "accidents", "ix_accidents_updated_by_user_id"):
            op.create_index("ix_accidents_updated_by_user_id", "accidents", ["updated_by_user_id"], unique=False)

    refreshed = sa.inspect(bind)
    if "accident_attachments" not in refreshed.get_table_names():
        op.create_table(
            "accident_attachments",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("accident_id_fk", sa.Integer(), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("stored_path", sa.String(length=1024), nullable=False),
            sa.Column("content_type", sa.String(length=255), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["accident_id_fk"], ["accidents.id"]),
        )
        op.create_index("ix_accident_attachments_accident_id_fk", "accident_attachments", ["accident_id_fk"], unique=False)

    refreshed = sa.inspect(bind)
    if "accident_site_standards" not in refreshed.get_table_names():
        op.create_table(
            "accident_site_standards",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("site_name", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("site_name"),
        )
        op.create_index("ix_accident_site_standards_site_name", "accident_site_standards", ["site_name"], unique=True)

        if "accidents" in refreshed.get_table_names() and _has_column(refreshed, "accidents", "site_standard_name"):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO accident_site_standards (site_name, is_active, created_at)
                    SELECT DISTINCT site_standard_name, 1, CURRENT_TIMESTAMP
                    FROM accidents
                    WHERE site_standard_name IS NOT NULL AND trim(site_standard_name) <> ''
                    """
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "accident_site_standards" in tables:
        op.drop_index("ix_accident_site_standards_site_name", table_name="accident_site_standards")
        op.drop_table("accident_site_standards")

    if "accident_attachments" in tables:
        op.drop_index("ix_accident_attachments_accident_id_fk", table_name="accident_attachments")
        op.drop_table("accident_attachments")
