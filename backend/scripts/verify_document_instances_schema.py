from __future__ import annotations

import sqlite3
import shutil
import sys
import tempfile
from pathlib import Path
import os

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.settings import settings


EXPECTED_UNIQUE_COLS = [
    "site_id",
    "document_type_code",
    "period_basis",
    "period_start",
    "period_end",
]


def _get_unique_indexes(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA index_list('{table}')").fetchall()
    # columns: (seq, name, unique, origin, partial)
    return [r[1] for r in rows if int(r[2]) == 1]


def _get_index_cols(conn: sqlite3.Connection, index_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA index_info('{index_name}')").fetchall()
    # columns: (seqno, cid, name)
    return [r[2] for r in rows]


def _ensure_site_exists(conn: sqlite3.Connection, site_id: int = 1) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    row = conn.execute("SELECT id FROM sites WHERE id=?", (site_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO sites (id, site_code, site_name, created_at, updated_at) VALUES (?, ?, ?, datetime('now'), datetime('now'))",
            (site_id, f"S{site_id}", f"S{site_id}"),
        )


def _try_insert_instance(
    conn: sqlite3.Connection,
    *,
    site_id: int,
    document_type_code: str,
    period_basis: str,
    period_start: str,
    period_end: str,
) -> None:
    conn.execute(
        """
        INSERT INTO document_instances (
            site_id, document_type_code, period_basis, period_start, period_end,
            generation_anchor_date, due_date,
            status, status_reason, selected_requirement_id,
            rule_is_required, cycle_code,
            rule_generation_rule, rule_generation_value, rule_due_offset_days,
            resolved_from, resolved_cycle_source,
            master_cycle_id, master_cycle_code,
            override_cycle_id, override_cycle_code,
            document_id, error_message,
            created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            NULL, NULL,
            'SKIPPED', 'MASTER_DEFAULT', NULL,
            0, NULL,
            NULL, NULL, NULL,
            NULL, NULL,
            NULL, NULL,
            NULL, NULL,
            NULL, NULL,
            datetime('now'), datetime('now')
        )
        """,
        (site_id, document_type_code, period_basis, period_start, period_end),
    )


def main() -> int:
    db_path = Path(settings.sqlite_path).resolve()
    if not db_path.exists():
        print(f"[FAIL] DB not found: {db_path}")
        return 2

    # 운영 DB 오염 방지: 원본 DB를 임시 복사본으로 검증한다.
    fd, tmp_name = tempfile.mkstemp(suffix=".db", prefix="besma_verify_")
    os.close(fd)
    tmp_db = Path(tmp_name)
    shutil.copy2(db_path, tmp_db)

    conn = sqlite3.connect(str(tmp_db))
    conn.row_factory = sqlite3.Row
    try:
        # 1) 유니크 인덱스 컬럼 검증
        unique_indexes = _get_unique_indexes(conn, "document_instances")
        if not unique_indexes:
            print("[FAIL] No UNIQUE index found on document_instances")
            return 2

        ok = False
        for idx in unique_indexes:
            cols = _get_index_cols(conn, idx)
            if cols == EXPECTED_UNIQUE_COLS:
                ok = True
                break

        if not ok:
            print("[FAIL] UNIQUE index does not match expected key")
            for idx in unique_indexes:
                print(f" - {idx}: {_get_index_cols(conn, idx)}")
            print(f" expected: {EXPECTED_UNIQUE_COLS}")
            return 2

        # 2) 공존/중복 차단 검증(임시 DB에서 insert + rollback)
        _ensure_site_exists(conn, 1)
        conn.execute("BEGIN")
        try:
            _try_insert_instance(
                conn,
                site_id=1,
                document_type_code="VERIFY_DOC",
                period_basis="CYCLE",
                period_start="2026-03-17",
                period_end="2026-03-17",
            )
            _try_insert_instance(
                conn,
                site_id=1,
                document_type_code="VERIFY_DOC",
                period_basis="AS_OF_FALLBACK",
                period_start="2026-03-17",
                period_end="2026-03-17",
            )

            # 동일 키(basis 포함) 중복은 실패해야 함
            try:
                _try_insert_instance(
                    conn,
                    site_id=1,
                    document_type_code="VERIFY_DOC",
                    period_basis="CYCLE",
                    period_start="2026-03-17",
                    period_end="2026-03-17",
                )
                print("[FAIL] Duplicate insert unexpectedly succeeded")
                return 2
            except sqlite3.IntegrityError:
                pass
        finally:
            conn.execute("ROLLBACK")

        # 3) 컬럼 nullability/default 검증(핵심 컬럼)
        cols = {r["name"]: r for r in conn.execute("PRAGMA table_info('document_instances')").fetchall()}
        for required in ("period_basis", "site_id", "document_type_code", "period_start", "period_end", "status", "status_reason"):
            if required not in cols:
                print(f"[FAIL] Missing column: {required}")
                return 2
        if int(cols["period_basis"]["notnull"]) != 1:
            print("[FAIL] period_basis is not NOT NULL")
            return 2

        # 4) FK 존재 여부(핵심)
        fks = conn.execute("PRAGMA foreign_key_list('document_instances')").fetchall()
        fk_targets = {(r[2], r[3], r[4]) for r in fks}  # (table, from, to)
        if ("sites", "site_id", "id") not in fk_targets:
            print("[FAIL] Missing FK: document_instances.site_id -> sites.id")
            return 2
        if ("documents", "document_id", "id") not in fk_targets:
            print("[FAIL] Missing FK: document_instances.document_id -> documents.id")
            return 2

        print("[OK] document_instances schema/key verified")
        return 0
    finally:
        conn.close()
        try:
            tmp_db.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

