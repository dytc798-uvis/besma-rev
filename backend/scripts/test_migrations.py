from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config


def _alembic_cfg() -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", "alembic")
    return cfg


def _run_upgrade(db_path: Path) -> None:
    os.environ["BESMA_SQLITE_PATH"] = str(db_path)
    command.upgrade(_alembic_cfg(), "head")


def _create_old_schema(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        # 최소 FK 타겟 테이블
        conn.execute(
            "CREATE TABLE sites (id INTEGER PRIMARY KEY, site_code TEXT NOT NULL, site_name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, login_id TEXT NOT NULL, password_hash TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE documents (id INTEGER PRIMARY KEY, document_no TEXT, title TEXT, document_type TEXT, site_id INTEGER, submitter_user_id INTEGER, current_status TEXT, version_no INTEGER, created_at TEXT, updated_at TEXT)"
        )
        # 구(旧) document_instances( period_basis 없음 + old unique )
        conn.execute(
            """
            CREATE TABLE document_instances (
              id INTEGER PRIMARY KEY,
              site_id INTEGER NOT NULL,
              document_type_code TEXT NOT NULL,
              period_start TEXT NOT NULL,
              period_end TEXT NOT NULL,
              status TEXT NOT NULL,
              status_reason TEXT NOT NULL,
              cycle_code TEXT,
              document_id INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(site_id, document_type_code, period_start, period_end)
            )
            """
        )
        conn.execute(
            "INSERT INTO sites (id, site_code, site_name, created_at, updated_at) VALUES (1,'S1','S1',datetime('now'),datetime('now'))"
        )
        conn.execute(
            """
            INSERT INTO document_instances
              (site_id, document_type_code, period_start, period_end, status, status_reason, cycle_code, document_id, created_at, updated_at)
            VALUES
              (1,'DAILY_DOC','2026-03-17','2026-03-17','SKIPPED','MASTER_DEFAULT','DAILY',NULL,datetime('now'),datetime('now'))
            """
        )
        conn.commit()
    finally:
        conn.close()


def _assert_unique_key(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("PRAGMA index_list('document_instances')").fetchall()
        uniques = [r[1] for r in rows if int(r[2]) == 1]
        assert uniques, "no unique index"
        ok = False
        for idx in uniques:
            cols = [r[2] for r in conn.execute(f"PRAGMA index_info('{idx}')").fetchall()]
            if cols == ["site_id", "document_type_code", "period_basis", "period_start", "period_end"]:
                ok = True
        assert ok, f"unique key mismatch: {uniques}"
    finally:
        conn.close()


def test_upgrade_on_empty_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "empty.db"
        # 현실적인 초기 상태(최소 FK 타겟 테이블) 생성
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                "CREATE TABLE sites (id INTEGER PRIMARY KEY, site_code TEXT NOT NULL, site_name TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, login_id TEXT NOT NULL, password_hash TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE documents (id INTEGER PRIMARY KEY, document_no TEXT, title TEXT, document_type TEXT, site_id INTEGER, submitter_user_id INTEGER, current_status TEXT, version_no INTEGER, created_at TEXT, updated_at TEXT)"
            )
            conn.commit()
        finally:
            conn.close()
        _run_upgrade(db)
        _assert_unique_key(db)


def test_upgrade_on_existing_old_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "old.db"
        _create_old_schema(db)
        _run_upgrade(db)
        _assert_unique_key(db)


def main() -> int:
    try:
        test_upgrade_on_empty_db()
        test_upgrade_on_existing_old_db()
        print("[OK] migration tests passed")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] migration tests failed: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

