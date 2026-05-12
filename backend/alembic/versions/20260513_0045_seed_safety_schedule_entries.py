"""seed safety_schedule_entries from samsung_schedule_raw_dump (calendar data)

Revision ID: 20260513_0045
Revises: 20260512_0044
Create Date: 2026-05-13
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

from app.core.datetime_utils import utc_now

revision = "20260513_0045"
down_revision = "20260512_0044"
branch_labels = None
depends_on = None

_SCHEDULE_DUMP_DATE = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})")


def _load_schedule_rows_from_dump_file() -> list[dict]:
    """backend/app/seed/samsung_schedule_raw_dump.json — 일정이 있는 칸만 (연도 2026)."""
    backend_root = Path(__file__).resolve().parents[2]
    data_path = backend_root / "app" / "seed" / "samsung_schedule_raw_dump.json"
    if not data_path.is_file():
        return []
    grid = json.loads(data_path.read_text(encoding="utf-8"))
    year = 2026
    out: list[dict] = []
    i = 4
    while i + 1 < len(grid):
        date_row = grid[i]
        content_row = grid[i + 1]
        if not isinstance(date_row, list) or not isinstance(content_row, list):
            i += 1
            continue
        has_date = False
        for c in range(1, min(8, len(date_row))):
            cell = date_row[c]
            if cell is not None and _SCHEDULE_DUMP_DATE.match(str(cell).strip()):
                has_date = True
                break
        if not has_date:
            break
        for c in range(1, 8):
            if c >= len(date_row):
                continue
            cell = date_row[c]
            m = _SCHEDULE_DUMP_DATE.match(str(cell).strip()) if cell is not None else None
            if not m:
                continue
            month, day = int(m.group(1)), int(m.group(2))
            try:
                d = date(year, month, day)
            except ValueError:
                continue
            if c >= len(content_row):
                continue
            raw = content_row[c]
            if raw is None or not str(raw).strip():
                continue
            text_body = str(raw).strip()
            first_line = text_body.split("\n", 1)[0].strip()
            title = first_line if len(first_line) <= 500 else first_line[:497] + "..."
            digest = hashlib.sha256(text_body.encode("utf-8")).hexdigest()[:16]
            import_key = f"dump-{d.isoformat()}-{digest}"
            out.append(
                {
                    "import_key": import_key,
                    "scheduled_date": d,
                    "title": title,
                    "inspector_label": "-",
                    "detail_text": text_body,
                }
            )
        i += 2
    return out


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "safety_schedule_entries" not in inspector.get_table_names():
        return

    rows = _load_schedule_rows_from_dump_file()
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
