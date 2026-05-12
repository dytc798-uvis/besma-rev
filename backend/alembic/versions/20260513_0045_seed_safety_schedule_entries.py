"""seed safety_schedule_entries from samsung_schedule_raw_dump (calendar data)

Revision ID: 20260513_0045
Revises: 20260512_0044
Create Date: 2026-05-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.core.datetime_utils import utc_now
from app.seed.seed_data import _schedule_rows_from_samsung_dump

revision = "20260513_0045"
down_revision = "20260512_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_entries" not in inspector.get_table_names():
        return

    rows = _schedule_rows_from_samsung_dump()
    if not rows:
        return

    now = utc_now()
    for row in rows:
        exists = bind.execute(
            text("SELECT 1 FROM safety_schedule_entries WHERE import_key = :k LIMIT 1"),
            {"k": row["import_key"]},
        ).first()
        if exists:
            continue
        sd = row["scheduled_date"]
        bind.execute(
            text(
                """
                INSERT INTO safety_schedule_entries
                (import_key, title, inspector_label, detail_text, scheduled_date, created_at)
                VALUES (:import_key, :title, :inspector_label, :detail_text, :scheduled_date, :created_at)
                """
            ),
            {
                "import_key": row["import_key"],
                "title": row["title"],
                "inspector_label": row["inspector_label"],
                "detail_text": row["detail_text"],
                "scheduled_date": sd,
                "created_at": now,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_entries" not in inspector.get_table_names():
        return
    if "safety_schedule_date_proposals" in inspector.get_table_names():
        bind.execute(
            text(
                """
                DELETE FROM safety_schedule_date_proposals
                WHERE entry_id IN (SELECT id FROM safety_schedule_entries WHERE import_key LIKE 'dump-%')
                """
            )
        )
    bind.execute(text("DELETE FROM safety_schedule_entries WHERE import_key LIKE 'dump-%'"))
