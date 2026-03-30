"""add persons.is_disabled

Revision ID: 20260318_0006
Revises: 20260318_0005
Create Date: 2026-03-18

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260318_0006"
down_revision = "20260318_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "persons" not in tables:
        return

    cols = {c["name"] for c in insp.get_columns("persons")}
    if "is_disabled" in cols:
        return

    # SQLite: batch recreate for safe add with server_default
    with op.batch_alter_table("persons", recreate="always") as batch:
        batch.add_column(
            sa.Column(
                "is_disabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )


def downgrade() -> None:
    pass

