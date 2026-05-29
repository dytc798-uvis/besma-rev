"""기능인제 출역일보 테이블·컬럼 추가 (기존 SQLite DB용, 1회 실행).

Usage (from backend/):
  python scripts/migrate_fe_attendance_tables.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "backend" / "besma.db"
if not DB.is_file():
    DB = Path(__file__).resolve().parents[1] / "besma.db"


def column_exists(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def main() -> None:
    if not DB.is_file():
        print(f"DB not found: {DB}")
        return
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    if not column_exists(cur, "functional_eval_periods", "last_attendance_date"):
        cur.execute("ALTER TABLE functional_eval_periods ADD COLUMN last_attendance_date DATE")
        print("Added functional_eval_periods.last_attendance_date")
    if not column_exists(cur, "functional_eval_workers", "is_on_reference_roster"):
        cur.execute(
            "ALTER TABLE functional_eval_workers "
            "ADD COLUMN is_on_reference_roster BOOLEAN NOT NULL DEFAULT 1"
        )
        print("Added functional_eval_workers.is_on_reference_roster")
    if not table_exists(cur, "functional_eval_attendance_import_batches"):
        cur.execute(
            """
            CREATE TABLE functional_eval_attendance_import_batches (
                id INTEGER PRIMARY KEY,
                period_id INTEGER NOT NULL REFERENCES functional_eval_periods(id),
                work_date DATE NOT NULL,
                original_filename VARCHAR(255) NOT NULL,
                stored_path VARCHAR(500) NOT NULL,
                total_rows INTEGER NOT NULL DEFAULT 0,
                linked_workers INTEGER NOT NULL DEFAULT 0,
                skipped_no_roster INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL
            )
            """
        )
        print("Created functional_eval_attendance_import_batches")
    if not table_exists(cur, "functional_eval_attendance_entries"):
        cur.execute(
            """
            CREATE TABLE functional_eval_attendance_entries (
                id INTEGER PRIMARY KEY,
                period_id INTEGER NOT NULL REFERENCES functional_eval_periods(id),
                work_date DATE NOT NULL,
                worker_id INTEGER REFERENCES functional_eval_workers(id),
                site_code VARCHAR(50) NOT NULL,
                rrn_hash VARCHAR(128) NOT NULL,
                name VARCHAR(100) NOT NULL,
                job_name VARCHAR(100),
                erp_site_label VARCHAR(500),
                batch_id INTEGER NOT NULL REFERENCES functional_eval_attendance_import_batches(id),
                created_at DATETIME NOT NULL,
                UNIQUE (period_id, work_date, rrn_hash)
            )
            """
        )
        print("Created functional_eval_attendance_entries")
    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
