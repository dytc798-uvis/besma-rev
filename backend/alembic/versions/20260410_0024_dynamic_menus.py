"""add dynamic menu tables

Revision ID: 20260410_0024
Revises: 20260410_0023
Create Date: 2026-04-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260410_0024"
down_revision = "20260410_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "dynamic_menu_configs" not in tables:
        op.create_table(
            "dynamic_menu_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("menu_type", sa.String(length=20), nullable=False),
            sa.Column("target_ui_type", sa.String(length=20), nullable=False, server_default="SITE"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("custom_config", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_dynamic_menu_configs_id", "dynamic_menu_configs", ["id"])
        op.create_index("ix_dynamic_menu_configs_slug", "dynamic_menu_configs", ["slug"], unique=True)

    if "dynamic_menu_board_posts" not in tables:
        op.create_table(
            "dynamic_menu_board_posts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("menu_id", sa.Integer(), sa.ForeignKey("dynamic_menu_configs.id"), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_dynamic_menu_board_posts_id", "dynamic_menu_board_posts", ["id"])
        op.create_index("ix_dynamic_menu_board_posts_menu_id", "dynamic_menu_board_posts", ["menu_id"])

    if "dynamic_menu_board_comments" not in tables:
        op.create_table(
            "dynamic_menu_board_comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("post_id", sa.Integer(), sa.ForeignKey("dynamic_menu_board_posts.id"), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_dynamic_menu_board_comments_id", "dynamic_menu_board_comments", ["id"])
        op.create_index("ix_dynamic_menu_board_comments_post_id", "dynamic_menu_board_comments", ["post_id"])

    if "dynamic_menu_table_rows" not in tables:
        op.create_table(
            "dynamic_menu_table_rows",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("menu_id", sa.Integer(), sa.ForeignKey("dynamic_menu_configs.id"), nullable=False),
            sa.Column("row_data", sa.Text(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_dynamic_menu_table_rows_id", "dynamic_menu_table_rows", ["id"])
        op.create_index("ix_dynamic_menu_table_rows_menu_id", "dynamic_menu_table_rows", ["menu_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "dynamic_menu_table_rows" in tables:
        op.drop_table("dynamic_menu_table_rows")
    if "dynamic_menu_board_comments" in tables:
        op.drop_table("dynamic_menu_board_comments")
    if "dynamic_menu_board_posts" in tables:
        op.drop_table("dynamic_menu_board_posts")
    if "dynamic_menu_configs" in tables:
        op.drop_table("dynamic_menu_configs")
