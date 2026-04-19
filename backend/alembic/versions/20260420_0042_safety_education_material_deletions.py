"""safety education material deletion audit

Revision ID: 20260420_0042
Revises: 20260419_0041
Create Date: 2026-04-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260420_0042"
down_revision = "20260419_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_education_material_deletions" in inspector.get_table_names():
        return
    op.create_table(
        "safety_education_material_deletions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_by_name", sa.String(length=100), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("deleted_by_login", sa.String(length=50), nullable=False),
        sa.Column("deleted_by_name", sa.String(length=100), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deleted_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_safety_education_material_deletions_material_id",
        "safety_education_material_deletions",
        ["material_id"],
        unique=False,
    )
    op.create_index(
        "ix_safety_education_material_deletions_site_id",
        "safety_education_material_deletions",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_safety_education_material_deletions_deleted_by_user_id",
        "safety_education_material_deletions",
        ["deleted_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_education_material_deletions" not in inspector.get_table_names():
        return
    op.drop_index("ix_safety_education_material_deletions_deleted_by_user_id", table_name="safety_education_material_deletions")
    op.drop_index("ix_safety_education_material_deletions_site_id", table_name="safety_education_material_deletions")
    op.drop_index("ix_safety_education_material_deletions_material_id", table_name="safety_education_material_deletions")
    op.drop_table("safety_education_material_deletions")
