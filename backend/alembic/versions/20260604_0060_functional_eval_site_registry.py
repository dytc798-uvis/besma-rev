"""functional eval site registry (월별현장별집계)

Revision ID: 20260604_0060
Revises: 20260602_0059
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260604_0060"
down_revision = "20260602_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "functional_eval_site_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_code", sa.String(length=50), nullable=False),
        sa.Column("erp_site_label", sa.String(length=500), nullable=False),
        sa.Column("site_alias", sa.String(length=30), nullable=False),
        sa.Column("manager_name", sa.String(length=100), nullable=False),
        sa.Column("manager_login_id", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_code", name="uq_fe_site_registry_site_code"),
    )
    op.create_index("ix_fe_site_registry_site_code", "functional_eval_site_registry", ["site_code"])
    op.create_index("ix_fe_site_registry_site_alias", "functional_eval_site_registry", ["site_alias"])
    op.create_index(
        "ix_fe_site_registry_manager_login_id",
        "functional_eval_site_registry",
        ["manager_login_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_fe_site_registry_manager_login_id", table_name="functional_eval_site_registry")
    op.drop_index("ix_fe_site_registry_site_alias", table_name="functional_eval_site_registry")
    op.drop_index("ix_fe_site_registry_site_code", table_name="functional_eval_site_registry")
    op.drop_table("functional_eval_site_registry")
