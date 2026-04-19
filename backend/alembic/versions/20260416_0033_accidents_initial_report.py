"""accidents table (최초보고 붙여넣기 1단계)

Revision ID: 20260416_0033
Revises: 20260414_0032
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260416_0033"
down_revision = "20260414_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "accidents" not in tables:
        op.create_table(
            "accidents",
            sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
            sa.Column("display_code", sa.String(length=32), nullable=False),
            sa.Column("report_type", sa.String(length=32), nullable=False, server_default="initial_report"),
            sa.Column("source_type", sa.String(length=32), nullable=False, server_default="naverworks_message"),
            sa.Column("message_raw", sa.Text(), nullable=False),
            sa.Column("site_name", sa.String(length=255), nullable=True),
            sa.Column("reporter_name", sa.String(length=128), nullable=True),
            sa.Column("accident_datetime_text", sa.String(length=128), nullable=True),
            sa.Column("accident_datetime", sa.DateTime(), nullable=True),
            sa.Column("accident_place", sa.String(length=512), nullable=True),
            sa.Column("work_content", sa.String(length=512), nullable=True),
            sa.Column("injured_person_name", sa.String(length=128), nullable=True),
            sa.Column("accident_reason", sa.String(length=512), nullable=True),
            sa.Column("injured_part", sa.String(length=256), nullable=True),
            sa.Column("diagnosis_name", sa.String(length=256), nullable=True),
            sa.Column("parse_status", sa.String(length=16), nullable=False),
            sa.Column("parse_note", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("display_code"),
        )
        op.create_index("ix_accidents_id", "accidents", ["id"], unique=False)
        op.create_index("ix_accidents_parse_status", "accidents", ["parse_status"], unique=False)
        op.create_index("ix_accidents_created_by_user_id", "accidents", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "accidents" in tables:
        op.drop_index("ix_accidents_created_by_user_id", table_name="accidents")
        op.drop_index("ix_accidents_parse_status", table_name="accidents")
        op.drop_index("ix_accidents_id", table_name="accidents")
        op.drop_table("accidents")
