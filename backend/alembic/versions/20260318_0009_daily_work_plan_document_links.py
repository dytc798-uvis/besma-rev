"""add daily work plan document links

Revision ID: 20260318_0009
Revises: 20260318_0008
Create Date: 2026-03-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260318_0009"
down_revision = "20260318_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("daily_work_plan_document_links"):
        op.create_table(
            "daily_work_plan_document_links",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "instance_id",
                sa.Integer(),
                sa.ForeignKey("document_instances.id"),
                nullable=False,
            ),
            sa.Column(
                "plan_id",
                sa.Integer(),
                sa.ForeignKey("daily_work_plans.id"),
                nullable=False,
            ),
            sa.Column(
                "assembled_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column(
                "assembled_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("(datetime('now'))"),
            ),
            sa.UniqueConstraint(
                "instance_id",
                "plan_id",
                name="uq_daily_work_plan_document_links_instance_plan",
            ),
        )

    index_names = {idx["name"] for idx in inspector.get_indexes("daily_work_plan_document_links")}
    if "ix_daily_work_plan_document_links_id" not in index_names:
        op.create_index(
            "ix_daily_work_plan_document_links_id",
            "daily_work_plan_document_links",
            ["id"],
            unique=False,
        )
    if "ix_daily_work_plan_document_links_instance_id" not in index_names:
        op.create_index(
            "ix_daily_work_plan_document_links_instance_id",
            "daily_work_plan_document_links",
            ["instance_id"],
            unique=False,
        )
    if "ix_daily_work_plan_document_links_plan_id" not in index_names:
        op.create_index(
            "ix_daily_work_plan_document_links_plan_id",
            "daily_work_plan_document_links",
            ["plan_id"],
            unique=False,
        )
    if "ix_daily_work_plan_document_links_assembled_by_user_id" not in index_names:
        op.create_index(
            "ix_daily_work_plan_document_links_assembled_by_user_id",
            "daily_work_plan_document_links",
            ["assembled_by_user_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_work_plan_document_links_assembled_by_user_id",
        table_name="daily_work_plan_document_links",
    )
    op.drop_index(
        "ix_daily_work_plan_document_links_plan_id",
        table_name="daily_work_plan_document_links",
    )
    op.drop_index(
        "ix_daily_work_plan_document_links_instance_id",
        table_name="daily_work_plan_document_links",
    )
    op.drop_index(
        "ix_daily_work_plan_document_links_id",
        table_name="daily_work_plan_document_links",
    )
    op.drop_table("daily_work_plan_document_links")
