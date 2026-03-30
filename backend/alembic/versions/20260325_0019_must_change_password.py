"""force password change on initial login

Revision ID: 20260325_0019
Revises: 20260320_0018
Create Date: 2026-03-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260325_0019"
down_revision = "20260320_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    with op.batch_alter_table("users", schema=None) as batch_op:
        if "must_change_password" not in columns:
            batch_op.add_column(
                sa.Column(
                    "must_change_password",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("1"),
                )
            )

    # Ensure legacy rows are forced to change at least once.
    op.execute("UPDATE users SET must_change_password = 1 WHERE must_change_password IS NULL")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}
    with op.batch_alter_table("users", schema=None) as batch_op:
        if "must_change_password" in columns:
            batch_op.drop_column("must_change_password")

