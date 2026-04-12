"""opinions created_by_user_id for author-based delete

Revision ID: 20260412_0026
Revises: 20260410_0025
Create Date: 2026-04-12 12:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260412_0026"
down_revision = "20260410_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("opinions")}
    if "created_by_user_id" in cols:
        return
    op.add_column("opinions", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_opinions_created_by_user_id_users",
        "opinions",
        "users",
        ["created_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("opinions")}
    if "created_by_user_id" not in cols:
        return
    op.drop_constraint("fk_opinions_created_by_user_id_users", "opinions", type_="foreignkey")
    op.drop_column("opinions", "created_by_user_id")
