"""set EMERGENCY_DRILL_REPORT frequency to HALF_YEARLY on existing rows

Revision ID: 20260514_0049
Revises: 20260512_0048
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260514_0049"
down_revision = "20260512_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_requirements" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("document_requirements")}
    if "frequency" not in cols or "code" not in cols:
        return
    op.execute(
        sa.text(
            """
            UPDATE document_requirements
            SET frequency = 'HALF_YEARLY'
            WHERE code = 'EMERGENCY_DRILL_REPORT'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "document_requirements" not in inspector.get_table_names():
        return
    cols = {c["name"] for c in inspector.get_columns("document_requirements")}
    if "frequency" not in cols or "code" not in cols:
        return
    op.execute(
        sa.text(
            """
            UPDATE document_requirements
            SET frequency = 'MONTHLY'
            WHERE code = 'EMERGENCY_DRILL_REPORT'
              AND frequency = 'HALF_YEARLY'
            """
        )
    )
