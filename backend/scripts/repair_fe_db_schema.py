"""로컬 DB에 누락된 기능인제 컬럼·테이블을 best-effort로 보정."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


def _db_path() -> Path:
    return BACKEND_ROOT.parent / "database" / "besma.db"


def _has_column(cur: sqlite3.Cursor, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == col for row in cur.fetchall())


def _has_table(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def main() -> None:
    path = _db_path()
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    changes: list[str] = []

    if _has_table(cur, "functional_eval_periods") and not _has_column(cur, "functional_eval_periods", "last_attendance_date"):
        cur.execute("ALTER TABLE functional_eval_periods ADD COLUMN last_attendance_date DATE")
        changes.append("functional_eval_periods.last_attendance_date")

    if _has_table(cur, "functional_eval_workers"):
        if not _has_column(cur, "functional_eval_workers", "assigned_evaluator_login_id"):
            cur.execute("ALTER TABLE functional_eval_workers ADD COLUMN assigned_evaluator_login_id VARCHAR(50)")
            changes.append("functional_eval_workers.assigned_evaluator_login_id")
        if not _has_column(cur, "functional_eval_workers", "is_on_reference_roster"):
            cur.execute(
                "ALTER TABLE functional_eval_workers ADD COLUMN is_on_reference_roster BOOLEAN NOT NULL DEFAULT 1"
            )
            changes.append("functional_eval_workers.is_on_reference_roster")

    if _has_table(cur, "functional_eval_attendance_entries"):
        for col, ddl in [
            ("job_name", "ALTER TABLE functional_eval_attendance_entries ADD COLUMN job_name VARCHAR(100)"),
            ("erp_site_label", "ALTER TABLE functional_eval_attendance_entries ADD COLUMN erp_site_label VARCHAR(500)"),
            ("rep_name", "ALTER TABLE functional_eval_attendance_entries ADD COLUMN rep_name VARCHAR(100)"),
        ]:
            if not _has_column(cur, "functional_eval_attendance_entries", col):
                cur.execute(ddl)
                changes.append(f"functional_eval_attendance_entries.{col}")

    conn.commit()
    conn.close()
    if changes:
        print("repaired:", ", ".join(changes))
    else:
        print("no repairs needed")


if __name__ == "__main__":
    main()
