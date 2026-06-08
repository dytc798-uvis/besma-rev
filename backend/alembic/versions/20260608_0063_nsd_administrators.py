"""new site deployment administrators table

Revision ID: 20260608_0063
Revises: 20260608_0062
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260608_0063"
down_revision = "20260608_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "new_site_deployment_administrators",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("login_id", sa.String(length=50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["new_site_deployments.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nsd_admin_deployment_id",
        "new_site_deployment_administrators",
        ["deployment_id"],
    )
    op.create_index(
        "ix_nsd_admin_role",
        "new_site_deployment_administrators",
        ["role"],
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, site_manager_name, site_manager_login_id,
                   gongmu_name, gongmu_login_id,
                   safety_name, construction_supervisor_name
            FROM new_site_deployments
            """
        )
    ).fetchall()
    for row in rows:
        dep_id = row[0]
        order = 0
        legacy = [
            ("SITE_MANAGER", row[1], row[2]),
            ("GONGMU", row[3], row[4]),
            ("SAFETY", row[5], None),
            ("CONSTRUCTION_SUPERVISOR", row[6], None),
        ]
        for role, name, login_id in legacy:
            if not name or not str(name).strip():
                continue
            conn.execute(
                sa.text(
                    """
                    INSERT INTO new_site_deployment_administrators
                    (deployment_id, role, name, login_id, sort_order, created_at)
                    VALUES (:dep_id, :role, :name, :login_id, :sort_order, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "dep_id": dep_id,
                    "role": role,
                    "name": str(name).strip(),
                    "login_id": login_id,
                    "sort_order": order,
                },
            )
            order += 1


def downgrade() -> None:
    op.drop_index("ix_nsd_admin_role", table_name="new_site_deployment_administrators")
    op.drop_index("ix_nsd_admin_deployment_id", table_name="new_site_deployment_administrators")
    op.drop_table("new_site_deployment_administrators")
