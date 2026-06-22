"""functional eval site completion lock

Revision ID: 20260622_0075
Revises: 20260622_0074
Create Date: 2026-06-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260622_0075"
down_revision = "20260622_0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("functional_eval_site_approvals") as batch:
        batch.add_column(sa.Column("evaluation_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("functional_eval_site_approvals") as batch:
        batch.drop_column("evaluation_completed_at")
