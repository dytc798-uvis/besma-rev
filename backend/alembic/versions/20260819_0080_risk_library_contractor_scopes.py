"""scope risk library by contractor and assign site reviewers

Revision ID: 20260819_0080
Revises: 20260803_0078
Create Date: 2026-08-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260819_0080"
down_revision = "20260803_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("risk_library_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_common",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )

    op.create_table(
        "risk_library_contractors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contractor_key", sa.String(length=120), nullable=False),
        sa.Column("contractor_name", sa.String(length=200), nullable=False),
        sa.Column(
            "evaluation_method",
            sa.String(length=30),
            nullable=False,
            server_default="회사 4×5",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contractor_key"),
    )
    op.create_index(
        "ix_risk_library_contractors_id",
        "risk_library_contractors",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_contractors_contractor_key",
        "risk_library_contractors",
        ["contractor_key"],
        unique=True,
    )

    op.create_table(
        "risk_library_item_contractors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_item_id", sa.Integer(), nullable=False),
        sa.Column("contractor_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.ForeignKeyConstraint(["contractor_id"], ["risk_library_contractors.id"]),
        sa.ForeignKeyConstraint(["risk_item_id"], ["risk_library_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "risk_item_id",
            "contractor_id",
            name="uq_risk_library_item_contractor",
        ),
    )
    op.create_index(
        "ix_risk_library_item_contractors_id",
        "risk_library_item_contractors",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_item_contractors_risk_item_id",
        "risk_library_item_contractors",
        ["risk_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_item_contractors_contractor_id",
        "risk_library_item_contractors",
        ["contractor_id"],
        unique=False,
    )

    op.create_table(
        "risk_assessment_site_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("inspector_name", sa.String(length=100), nullable=True),
        sa.Column("verifier_name", sa.String(length=100), nullable=True),
        sa.Column("appointed_on", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", name="uq_risk_assessment_site_roles_site"),
    )
    op.create_index(
        "ix_risk_assessment_site_roles_id",
        "risk_assessment_site_roles",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_assessment_site_roles_site_id",
        "risk_assessment_site_roles",
        ["site_id"],
        unique=True,
    )

    op.create_table(
        "risk_library_site_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("risk_item_id", sa.Integer(), nullable=False),
        sa.Column("improvement_owner_name", sa.String(length=100), nullable=True),
        sa.Column("improvement_verifier_name", sa.String(length=100), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["risk_item_id"], ["risk_library_items.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "site_id",
            "risk_item_id",
            name="uq_risk_library_site_assignment",
        ),
    )
    op.create_index(
        "ix_risk_library_site_assignments_id",
        "risk_library_site_assignments",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_site_assignments_site_id",
        "risk_library_site_assignments",
        ["site_id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_site_assignments_risk_item_id",
        "risk_library_site_assignments",
        ["risk_item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_risk_library_site_assignments_risk_item_id",
        table_name="risk_library_site_assignments",
    )
    op.drop_index(
        "ix_risk_library_site_assignments_site_id",
        table_name="risk_library_site_assignments",
    )
    op.drop_index(
        "ix_risk_library_site_assignments_id",
        table_name="risk_library_site_assignments",
    )
    op.drop_table("risk_library_site_assignments")

    op.drop_index(
        "ix_risk_assessment_site_roles_site_id",
        table_name="risk_assessment_site_roles",
    )
    op.drop_index(
        "ix_risk_assessment_site_roles_id",
        table_name="risk_assessment_site_roles",
    )
    op.drop_table("risk_assessment_site_roles")

    op.drop_index(
        "ix_risk_library_item_contractors_contractor_id",
        table_name="risk_library_item_contractors",
    )
    op.drop_index(
        "ix_risk_library_item_contractors_risk_item_id",
        table_name="risk_library_item_contractors",
    )
    op.drop_index(
        "ix_risk_library_item_contractors_id",
        table_name="risk_library_item_contractors",
    )
    op.drop_table("risk_library_item_contractors")

    op.drop_index(
        "ix_risk_library_contractors_contractor_key",
        table_name="risk_library_contractors",
    )
    op.drop_index(
        "ix_risk_library_contractors_id",
        table_name="risk_library_contractors",
    )
    op.drop_table("risk_library_contractors")

    with op.batch_alter_table("risk_library_items", schema=None) as batch_op:
        batch_op.drop_column("is_common")
