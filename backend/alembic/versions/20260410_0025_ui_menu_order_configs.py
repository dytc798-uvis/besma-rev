"""add ui menu order configs table

Revision ID: 20260410_0025
Revises: 20260410_0024
Create Date: 2026-04-10 22:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260410_0025"
down_revision = "20260410_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ui_menu_order_configs" in tables:
        return
    op.create_table(
        "ui_menu_order_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ui_type", sa.String(length=20), nullable=False),
        sa.Column("ordered_keys", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ui_menu_order_configs_id", "ui_menu_order_configs", ["id"], unique=False)
    op.create_index("ix_ui_menu_order_configs_ui_type", "ui_menu_order_configs", ["ui_type"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "ui_menu_order_configs" not in tables:
        return
    op.drop_index("ix_ui_menu_order_configs_ui_type", table_name="ui_menu_order_configs")
    op.drop_index("ix_ui_menu_order_configs_id", table_name="ui_menu_order_configs")
    op.drop_table("ui_menu_order_configs")
