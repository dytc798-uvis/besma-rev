"""new site deployment tables

Revision ID: 20260608_0062
Revises: 20260608_0061
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0062"
down_revision = "20260608_0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "new_site_deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("site_code", sa.String(length=50), nullable=True),
        sa.Column("site_alias", sa.String(length=30), nullable=False),
        sa.Column("contractor", sa.String(length=200), nullable=True),
        sa.Column("site_name", sa.String(length=300), nullable=False),
        sa.Column("construction_amount", sa.Integer(), nullable=True),
        sa.Column("construction_period", sa.String(length=200), nullable=True),
        sa.Column("site_manager_name", sa.String(length=100), nullable=True),
        sa.Column("gongmu_name", sa.String(length=100), nullable=True),
        sa.Column("safety_name", sa.String(length=100), nullable=True),
        sa.Column("construction_supervisor_name", sa.String(length=100), nullable=True),
        sa.Column("site_manager_login_id", sa.String(length=50), nullable=True),
        sa.Column("gongmu_login_id", sa.String(length=50), nullable=True),
        sa.Column("container_arrival_date", sa.Date(), nullable=True),
        sa.Column("safety_checks_json", sa.JSON(), nullable=True),
        sa.Column("is_complete", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_new_site_deployments_site_id", "new_site_deployments", ["site_id"])
    op.create_index("ix_new_site_deployments_site_code", "new_site_deployments", ["site_code"])

    op.create_table(
        "new_site_deployment_photos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("item_key", sa.String(length=50), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["new_site_deployments.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deployment_id", "item_key", name="uq_nsd_photo_item"),
    )

    op.create_table(
        "new_site_deployment_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("stored_path", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["new_site_deployments.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deployment_id", "doc_type", name="uq_nsd_doc_type"),
    )


def downgrade() -> None:
    op.drop_table("new_site_deployment_documents")
    op.drop_table("new_site_deployment_photos")
    op.drop_table("new_site_deployments")
