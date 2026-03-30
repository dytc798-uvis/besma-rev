"""add risk library and daily work plan tables

Revision ID: 20260318_0008
Revises: 20260318_0007
Create Date: 2026-03-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260318_0008"
down_revision = "20260318_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risk_library_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("source_scope", sa.String(length=20), nullable=False),
        sa.Column("owner_site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
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
    op.create_index("ix_risk_library_items_id", "risk_library_items", ["id"], unique=False)

    op.create_table(
        "risk_library_item_revisions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("risk_library_items.id"), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("work_category", sa.String(length=100), nullable=False),
        sa.Column("trade_type", sa.String(length=100), nullable=False),
        sa.Column("risk_factor", sa.Text(), nullable=False),
        sa.Column("risk_cause", sa.Text(), nullable=False),
        sa.Column("countermeasure", sa.Text(), nullable=False),
        sa.Column("risk_f", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("risk_s", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("risk_r", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("revised_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "revised_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
        sa.Column("revision_note", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_risk_library_item_revisions_id",
        "risk_library_item_revisions",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_item_revisions_item_id",
        "risk_library_item_revisions",
        ["item_id"],
        unique=False,
    )
    op.create_index(
        "uq_risk_library_item_current_true",
        "risk_library_item_revisions",
        ["item_id"],
        unique=True,
        sqlite_where=sa.text("is_current = 1"),
    )

    op.create_table(
        "risk_library_keywords",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "risk_revision_id",
            sa.Integer(),
            sa.ForeignKey("risk_library_item_revisions.id"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(length=100), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
    )
    op.create_index("ix_risk_library_keywords_id", "risk_library_keywords", ["id"], unique=False)
    op.create_index(
        "ix_risk_library_keywords_risk_revision_id",
        "risk_library_keywords",
        ["risk_revision_id"],
        unique=False,
    )
    op.create_index(
        "ix_risk_library_keywords_keyword",
        "risk_library_keywords",
        ["keyword"],
        unique=False,
    )

    op.create_table(
        "daily_work_plans",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
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
    op.create_index("ix_daily_work_plans_id", "daily_work_plans", ["id"], unique=False)
    op.create_index("ix_daily_work_plans_site_id", "daily_work_plans", ["site_id"], unique=False)
    op.create_index(
        "ix_daily_work_plans_work_date",
        "daily_work_plans",
        ["work_date"],
        unique=False,
    )
    op.create_index(
        "ix_daily_work_plans_author_user_id",
        "daily_work_plans",
        ["author_user_id"],
        unique=False,
    )

    op.create_table(
        "daily_work_plan_items",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("daily_work_plans.id"), nullable=False),
        sa.Column("work_name", sa.String(length=255), nullable=False),
        sa.Column("work_description", sa.Text(), nullable=False),
        sa.Column("team_label", sa.String(length=100), nullable=True),
        sa.Column("leader_person_id", sa.Integer(), sa.ForeignKey("persons.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
    )
    op.create_index(
        "ix_daily_work_plan_items_id",
        "daily_work_plan_items",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_daily_work_plan_items_plan_id",
        "daily_work_plan_items",
        ["plan_id"],
        unique=False,
    )

    op.create_table(
        "daily_work_plan_item_risk_refs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "plan_item_id",
            sa.Integer(),
            sa.ForeignKey("daily_work_plan_items.id"),
            nullable=False,
        ),
        sa.Column(
            "risk_item_id",
            sa.Integer(),
            sa.ForeignKey("risk_library_items.id"),
            nullable=False,
        ),
        sa.Column(
            "risk_revision_id",
            sa.Integer(),
            sa.ForeignKey("risk_library_item_revisions.id"),
            nullable=False,
        ),
        sa.Column("link_type", sa.String(length=20), nullable=False, server_default="RECOMMENDED"),
        sa.Column("is_selected", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("source_rule", sa.String(length=20), nullable=False, server_default="KEYWORD_MATCH"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("(datetime('now'))"),
        ),
    )
    op.create_index(
        "ix_daily_work_plan_item_risk_refs_id",
        "daily_work_plan_item_risk_refs",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_daily_work_plan_item_risk_refs_plan_item_id",
        "daily_work_plan_item_risk_refs",
        ["plan_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_daily_work_plan_item_risk_refs_risk_item_id",
        "daily_work_plan_item_risk_refs",
        ["risk_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_daily_work_plan_item_risk_refs_risk_revision_id",
        "daily_work_plan_item_risk_refs",
        ["risk_revision_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_daily_work_plan_item_risk_refs_risk_revision_id", table_name="daily_work_plan_item_risk_refs")
    op.drop_index("ix_daily_work_plan_item_risk_refs_risk_item_id", table_name="daily_work_plan_item_risk_refs")
    op.drop_index("ix_daily_work_plan_item_risk_refs_plan_item_id", table_name="daily_work_plan_item_risk_refs")
    op.drop_index("ix_daily_work_plan_item_risk_refs_id", table_name="daily_work_plan_item_risk_refs")
    op.drop_table("daily_work_plan_item_risk_refs")

    op.drop_index("ix_daily_work_plan_items_plan_id", table_name="daily_work_plan_items")
    op.drop_index("ix_daily_work_plan_items_id", table_name="daily_work_plan_items")
    op.drop_table("daily_work_plan_items")

    op.drop_index("ix_daily_work_plans_author_user_id", table_name="daily_work_plans")
    op.drop_index("ix_daily_work_plans_work_date", table_name="daily_work_plans")
    op.drop_index("ix_daily_work_plans_site_id", table_name="daily_work_plans")
    op.drop_index("ix_daily_work_plans_id", table_name="daily_work_plans")
    op.drop_table("daily_work_plans")

    op.drop_index("ix_risk_library_keywords_keyword", table_name="risk_library_keywords")
    op.drop_index("ix_risk_library_keywords_risk_revision_id", table_name="risk_library_keywords")
    op.drop_index("ix_risk_library_keywords_id", table_name="risk_library_keywords")
    op.drop_table("risk_library_keywords")

    op.drop_index("uq_risk_library_item_current_true", table_name="risk_library_item_revisions")
    op.drop_index("ix_risk_library_item_revisions_item_id", table_name="risk_library_item_revisions")
    op.drop_index("ix_risk_library_item_revisions_id", table_name="risk_library_item_revisions")
    op.drop_table("risk_library_item_revisions")

    op.drop_index("ix_risk_library_items_id", table_name="risk_library_items")
    op.drop_table("risk_library_items")
