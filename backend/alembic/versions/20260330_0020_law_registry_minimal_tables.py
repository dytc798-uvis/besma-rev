"""add minimal law registry tables

Revision ID: 20260330_0020
Revises: 20260325_0019
Create Date: 2026-03-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260330_0020"
down_revision = "20260325_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "law_master" not in tables:
        op.create_table(
            "law_master",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_name", sa.String(length=255), nullable=False),
            sa.Column("law_type", sa.String(length=50), nullable=False),
            sa.Column("law_api_id", sa.String(length=100), nullable=True),
            sa.Column("law_key", sa.String(length=200), nullable=True),
            sa.Column("effective_date", sa.Date(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_law_master_id", "law_master", ["id"], unique=False)
        op.create_index("ix_law_master_law_name", "law_master", ["law_name"], unique=False)
        op.create_index("ix_law_master_law_type", "law_master", ["law_type"], unique=False)
        op.create_index("ix_law_master_law_api_id", "law_master", ["law_api_id"], unique=False)
        op.create_index("ix_law_master_law_key", "law_master", ["law_key"], unique=False)
        op.create_index("ix_law_master_effective_date", "law_master", ["effective_date"], unique=False)

    if "law_article_item" not in tables:
        op.create_table(
            "law_article_item",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_master_id", sa.Integer(), nullable=False),
            sa.Column("article_display", sa.String(length=255), nullable=True),
            sa.Column("summary_title", sa.Text(), nullable=True),
            sa.Column("department", sa.String(length=255), nullable=True),
            sa.Column("action_required", sa.Text(), nullable=True),
            sa.Column("countermeasure", sa.Text(), nullable=True),
            sa.Column("penalty", sa.Text(), nullable=True),
            sa.Column("keywords", sa.Text(), nullable=True),
            sa.Column("risk_tags", sa.Text(), nullable=True),
            sa.Column("work_type_tags", sa.Text(), nullable=True),
            sa.Column("document_tags", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("search_text", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["law_master_id"], ["law_master.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_law_article_item_id", "law_article_item", ["id"], unique=False)
        op.create_index("ix_law_article_item_law_master_id", "law_article_item", ["law_master_id"], unique=False)
        op.create_index("ix_law_article_item_article_display", "law_article_item", ["article_display"], unique=False)
        op.create_index("ix_law_article_item_department", "law_article_item", ["department"], unique=False)

    if "law_revision_history" not in tables:
        op.create_table(
            "law_revision_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("law_master_id", sa.Integer(), nullable=False),
            sa.Column("revision_date", sa.Date(), nullable=True),
            sa.Column("revision_summary", sa.Text(), nullable=True),
            sa.Column("source_ref", sa.String(length=255), nullable=True),
            sa.Column("parse_status", sa.String(length=50), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["law_master_id"], ["law_master.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_law_revision_history_id", "law_revision_history", ["id"], unique=False)
        op.create_index("ix_law_revision_history_law_master_id", "law_revision_history", ["law_master_id"], unique=False)
        op.create_index("ix_law_revision_history_revision_date", "law_revision_history", ["revision_date"], unique=False)
        op.create_index("ix_law_revision_history_parse_status", "law_revision_history", ["parse_status"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "law_revision_history" in tables:
        op.drop_index("ix_law_revision_history_parse_status", table_name="law_revision_history")
        op.drop_index("ix_law_revision_history_revision_date", table_name="law_revision_history")
        op.drop_index("ix_law_revision_history_law_master_id", table_name="law_revision_history")
        op.drop_index("ix_law_revision_history_id", table_name="law_revision_history")
        op.drop_table("law_revision_history")

    if "law_article_item" in tables:
        op.drop_index("ix_law_article_item_department", table_name="law_article_item")
        op.drop_index("ix_law_article_item_article_display", table_name="law_article_item")
        op.drop_index("ix_law_article_item_law_master_id", table_name="law_article_item")
        op.drop_index("ix_law_article_item_id", table_name="law_article_item")
        op.drop_table("law_article_item")

    if "law_master" in tables:
        op.drop_index("ix_law_master_effective_date", table_name="law_master")
        op.drop_index("ix_law_master_law_key", table_name="law_master")
        op.drop_index("ix_law_master_law_api_id", table_name="law_master")
        op.drop_index("ix_law_master_law_type", table_name="law_master")
        op.drop_index("ix_law_master_law_name", table_name="law_master")
        op.drop_index("ix_law_master_id", table_name="law_master")
        op.drop_table("law_master")
