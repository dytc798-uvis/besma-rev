"""add daily work plan distribution and worker signature tables

Revision ID: 20260318_0010
Revises: 20260318_0009
Create Date: 2026-03-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260318_0010"
down_revision = "20260318_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    site_columns = {col["name"] for col in inspector.get_columns("sites")}
    with op.batch_alter_table("sites", schema=None) as batch_op:
        if "latitude" not in site_columns:
            batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        if "longitude" not in site_columns:
            batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))
        if "allowed_radius_m" not in site_columns:
            batch_op.add_column(sa.Column("allowed_radius_m", sa.Integer(), nullable=True))

    if not inspector.has_table("daily_work_plan_distributions"):
        op.create_table(
            "daily_work_plan_distributions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.Integer(), nullable=False),
            sa.Column("target_date", sa.Date(), nullable=False),
            sa.Column("visible_from", sa.DateTime(), nullable=False),
            sa.Column("distributed_by_user_id", sa.Integer(), nullable=False),
            sa.Column(
                "distributed_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("(datetime('now'))"),
            ),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="SCHEDULED"),
            sa.ForeignKeyConstraint(["distributed_by_user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["plan_id"], ["daily_work_plans.id"]),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "plan_id",
                "target_date",
                name="uq_daily_work_plan_distributions_plan_target_date",
            ),
        )
    distribution_indexes = (
        {idx["name"] for idx in inspector.get_indexes("daily_work_plan_distributions")}
        if inspector.has_table("daily_work_plan_distributions")
        else set()
    )
    if "ix_daily_work_plan_distributions_id" not in distribution_indexes:
        op.create_index(
            "ix_daily_work_plan_distributions_id",
            "daily_work_plan_distributions",
            ["id"],
            unique=False,
        )
    if "ix_daily_work_plan_distributions_plan_id" not in distribution_indexes:
        op.create_index(
            "ix_daily_work_plan_distributions_plan_id",
            "daily_work_plan_distributions",
            ["plan_id"],
            unique=False,
        )
    if "ix_daily_work_plan_distributions_site_id" not in distribution_indexes:
        op.create_index(
            "ix_daily_work_plan_distributions_site_id",
            "daily_work_plan_distributions",
            ["site_id"],
            unique=False,
        )
    if "ix_daily_work_plan_distributions_target_date" not in distribution_indexes:
        op.create_index(
            "ix_daily_work_plan_distributions_target_date",
            "daily_work_plan_distributions",
            ["target_date"],
            unique=False,
        )
    if "ix_daily_work_plan_distributions_visible_from" not in distribution_indexes:
        op.create_index(
            "ix_daily_work_plan_distributions_visible_from",
            "daily_work_plan_distributions",
            ["visible_from"],
            unique=False,
        )
    if "ix_daily_work_plan_distributions_distributed_by_user_id" not in distribution_indexes:
        op.create_index(
            "ix_daily_work_plan_distributions_distributed_by_user_id",
            "daily_work_plan_distributions",
            ["distributed_by_user_id"],
            unique=False,
        )

    if not inspector.has_table("daily_work_plan_distribution_workers"):
        op.create_table(
            "daily_work_plan_distribution_workers",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("distribution_id", sa.Integer(), nullable=False),
            sa.Column("person_id", sa.Integer(), nullable=False),
            sa.Column("employment_id", sa.Integer(), nullable=True),
            sa.Column("access_token", sa.String(length=64), nullable=False),
            sa.Column("ack_status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("viewed_at", sa.DateTime(), nullable=True),
            sa.Column("signed_at", sa.DateTime(), nullable=True),
            sa.Column("signature_data", sa.Text(), nullable=True),
            sa.Column("signature_mime", sa.String(length=50), nullable=True),
            sa.Column("signature_hash", sa.String(length=128), nullable=True),
            sa.ForeignKeyConstraint(["distribution_id"], ["daily_work_plan_distributions.id"]),
            sa.ForeignKeyConstraint(["employment_id"], ["employments.id"]),
            sa.ForeignKeyConstraint(["person_id"], ["persons.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("access_token"),
            sa.UniqueConstraint(
                "distribution_id",
                "person_id",
                name="uq_daily_work_plan_distribution_workers_distribution_person",
            ),
        )
    worker_indexes = (
        {idx["name"] for idx in inspector.get_indexes("daily_work_plan_distribution_workers")}
        if inspector.has_table("daily_work_plan_distribution_workers")
        else set()
    )
    if "ix_daily_work_plan_distribution_workers_id" not in worker_indexes:
        op.create_index(
            "ix_daily_work_plan_distribution_workers_id",
            "daily_work_plan_distribution_workers",
            ["id"],
            unique=False,
        )
    if "ix_daily_work_plan_distribution_workers_distribution_id" not in worker_indexes:
        op.create_index(
            "ix_daily_work_plan_distribution_workers_distribution_id",
            "daily_work_plan_distribution_workers",
            ["distribution_id"],
            unique=False,
        )
    if "ix_daily_work_plan_distribution_workers_person_id" not in worker_indexes:
        op.create_index(
            "ix_daily_work_plan_distribution_workers_person_id",
            "daily_work_plan_distribution_workers",
            ["person_id"],
            unique=False,
        )
    if "ix_daily_work_plan_distribution_workers_employment_id" not in worker_indexes:
        op.create_index(
            "ix_daily_work_plan_distribution_workers_employment_id",
            "daily_work_plan_distribution_workers",
            ["employment_id"],
            unique=False,
        )
    if "ix_daily_work_plan_distribution_workers_access_token" not in worker_indexes:
        op.create_index(
            "ix_daily_work_plan_distribution_workers_access_token",
            "daily_work_plan_distribution_workers",
            ["access_token"],
            unique=True,
        )
    if "ix_daily_work_plan_distribution_workers_signature_hash" not in worker_indexes:
        op.create_index(
            "ix_daily_work_plan_distribution_workers_signature_hash",
            "daily_work_plan_distribution_workers",
            ["signature_hash"],
            unique=False,
        )

    if not inspector.has_table("site_admin_presences"):
        op.create_table(
            "site_admin_presences",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("site_id", sa.Integer(), nullable=False),
            sa.Column("lat", sa.Float(), nullable=True),
            sa.Column("lng", sa.Float(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("(datetime('now'))"),
            ),
            sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "site_id", name="uq_site_admin_presences_user_site"),
        )
    presence_indexes = (
        {idx["name"] for idx in inspector.get_indexes("site_admin_presences")}
        if inspector.has_table("site_admin_presences")
        else set()
    )
    if "ix_site_admin_presences_id" not in presence_indexes:
        op.create_index(
            "ix_site_admin_presences_id",
            "site_admin_presences",
            ["id"],
            unique=False,
        )
    if "ix_site_admin_presences_user_id" not in presence_indexes:
        op.create_index(
            "ix_site_admin_presences_user_id",
            "site_admin_presences",
            ["user_id"],
            unique=False,
        )
    if "ix_site_admin_presences_site_id" not in presence_indexes:
        op.create_index(
            "ix_site_admin_presences_site_id",
            "site_admin_presences",
            ["site_id"],
            unique=False,
        )
    if "ix_site_admin_presences_last_seen_at" not in presence_indexes:
        op.create_index(
            "ix_site_admin_presences_last_seen_at",
            "site_admin_presences",
            ["last_seen_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_site_admin_presences_last_seen_at", table_name="site_admin_presences")
    op.drop_index("ix_site_admin_presences_site_id", table_name="site_admin_presences")
    op.drop_index("ix_site_admin_presences_user_id", table_name="site_admin_presences")
    op.drop_index("ix_site_admin_presences_id", table_name="site_admin_presences")
    op.drop_table("site_admin_presences")

    op.drop_index(
        "ix_daily_work_plan_distribution_workers_signature_hash",
        table_name="daily_work_plan_distribution_workers",
    )
    op.drop_index(
        "ix_daily_work_plan_distribution_workers_access_token",
        table_name="daily_work_plan_distribution_workers",
    )
    op.drop_index(
        "ix_daily_work_plan_distribution_workers_employment_id",
        table_name="daily_work_plan_distribution_workers",
    )
    op.drop_index(
        "ix_daily_work_plan_distribution_workers_person_id",
        table_name="daily_work_plan_distribution_workers",
    )
    op.drop_index(
        "ix_daily_work_plan_distribution_workers_distribution_id",
        table_name="daily_work_plan_distribution_workers",
    )
    op.drop_index(
        "ix_daily_work_plan_distribution_workers_id",
        table_name="daily_work_plan_distribution_workers",
    )
    op.drop_table("daily_work_plan_distribution_workers")

    op.drop_index(
        "ix_daily_work_plan_distributions_distributed_by_user_id",
        table_name="daily_work_plan_distributions",
    )
    op.drop_index(
        "ix_daily_work_plan_distributions_visible_from",
        table_name="daily_work_plan_distributions",
    )
    op.drop_index(
        "ix_daily_work_plan_distributions_target_date",
        table_name="daily_work_plan_distributions",
    )
    op.drop_index(
        "ix_daily_work_plan_distributions_site_id",
        table_name="daily_work_plan_distributions",
    )
    op.drop_index(
        "ix_daily_work_plan_distributions_plan_id",
        table_name="daily_work_plan_distributions",
    )
    op.drop_index(
        "ix_daily_work_plan_distributions_id",
        table_name="daily_work_plan_distributions",
    )
    op.drop_table("daily_work_plan_distributions")

    with op.batch_alter_table("sites", schema=None) as batch_op:
        batch_op.drop_column("allowed_radius_m")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
