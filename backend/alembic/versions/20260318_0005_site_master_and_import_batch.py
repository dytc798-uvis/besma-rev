"""site master enrichment + import batch

Revision ID: 20260318_0005
Revises: 20260317_0004
Create Date: 2026-03-18

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0005"
down_revision = "20260317_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "sites" in tables:
        cols = {c["name"] for c in insp.get_columns("sites")}
        with op.batch_alter_table("sites", recreate="always") as batch:
            def add_col(name: str, type_: sa.types.TypeEngine, **kwargs) -> None:
                if name not in cols:
                    batch.add_column(sa.Column(name, type_, **kwargs))

            add_col("contract_type", sa.String(length=50), nullable=True)
            add_col("contract_date", sa.Date(), nullable=True)
            add_col("contractor_name", sa.String(length=200), nullable=True)
            add_col("project_amount", sa.Integer(), nullable=True)
            add_col("phone_number", sa.String(length=50), nullable=True)
            add_col("address", sa.String(length=300), nullable=True)
            add_col("building_count", sa.Integer(), nullable=True)
            add_col("floor_underground", sa.Integer(), nullable=True)
            add_col("floor_ground", sa.Integer(), nullable=True)
            add_col("household_count", sa.Integer(), nullable=True)
            add_col("gross_area", sa.Integer(), nullable=True)
            add_col("gross_area_unit", sa.String(length=20), nullable=True)
            add_col("main_usage", sa.String(length=100), nullable=True)
            add_col("work_types", sa.String(length=200), nullable=True)
            add_col("project_manager", sa.String(length=100), nullable=True)
            add_col("site_manager", sa.String(length=100), nullable=True)
            add_col("notes", sa.String(length=500), nullable=True)

            add_col("created_by_user_id", sa.Integer(), nullable=True)
            add_col("updated_by_user_id", sa.Integer(), nullable=True)

            if "users" in tables:
                batch.create_foreign_key(
                    "fk_sites_created_by_user_id",
                    "users",
                    ["created_by_user_id"],
                    ["id"],
                )
                batch.create_foreign_key(
                    "fk_sites_updated_by_user_id",
                    "users",
                    ["updated_by_user_id"],
                    ["id"],
                )

    if "site_import_batches" not in tables:
        op.create_table(
            "site_import_batches",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("stored_path", sa.String(length=500), nullable=False),
            sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(), nullable=False),
            sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_summary", sa.String(length=1000), nullable=True),
            sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], name="fk_site_import_batches_user"),
        )


def downgrade() -> None:
    # 안전을 위해 다운그레이드는 정의하지 않는다.
    pass

