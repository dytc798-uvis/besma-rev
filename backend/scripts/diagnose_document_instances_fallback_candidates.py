from __future__ import annotations

import argparse
import json
import sys
import shutil
import sqlite3
import tempfile
import os
import hashlib
from datetime import datetime
from typing import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config.settings import settings


@dataclass(frozen=True)
class Candidate:
    id: int | None
    site_id: int | None
    document_type_code: str | None
    period_start: str | None
    period_end: str | None
    cycle_code: str | None
    period_basis: str | None
    status: str | None
    status_reason: str | None
    generation_anchor_date: str | None
    due_date: str | None
    document_id: int | None
    error_message: str | None
    reasons: list[str]


def _get_db_path() -> Path:
    override = os.getenv("BESMA_SQLITE_PATH")
    if override:
        return Path(override).resolve()
    return Path(settings.sqlite_path).resolve()


def _connect_copy(db_path: Path) -> sqlite3.Connection:
    # 운영 DB 오염 방지: 원본 DB를 임시 파일로 복사해 사용한다.
    # Windows에서는 파일 핸들이 열려 있으면 삭제가 실패하므로,
    # 호출 측에서 close 후 tmp 파일을 삭제하도록 경로를 함께 관리한다.
    raise RuntimeError("_connect_copy deprecated; use _open_temp_copy()")


def _open_temp_copy(db_path: Path) -> tuple[sqlite3.Connection, Path]:
    fd, tmp_name = tempfile.mkstemp(suffix=".db", prefix="besma_verify_")
    os.close(fd)
    tmp_db = Path(tmp_name)
    shutil.copy2(db_path, tmp_db)
    conn = sqlite3.connect(str(tmp_db))
    conn.row_factory = sqlite3.Row
    return conn, tmp_db


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _col_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}


def _safe_get(row: sqlite3.Row, key: str) -> object | None:
    try:
        return row[key]
    except Exception:
        return None


def _is_empty(v: object | None) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


def candidate_reasons(row: Mapping[str, object | None], cols: set[str]) -> list[str]:
    reasons: list[str] = []

    cycle_code = row.get("cycle_code") if "cycle_code" in cols else None
    period_basis = row.get("period_basis") if "period_basis" in cols else None
    status_reason = row.get("status_reason") if "status_reason" in cols else None
    period_start = row.get("period_start") if "period_start" in cols else None
    period_end = row.get("period_end") if "period_end" in cols else None
    gen_anchor = row.get("generation_anchor_date") if "generation_anchor_date" in cols else None
    due_date = row.get("due_date") if "due_date" in cols else None

    # 1) cycle_code IS NULL/empty
    if _is_empty(cycle_code):
        reasons.append("cycle_code_is_null")

    # 2) period_basis already AS_OF_FALLBACK (after migration or manual fix)
    if isinstance(period_basis, str) and period_basis == "AS_OF_FALLBACK":
        reasons.append("period_basis_is_as_of_fallback")

    # 3) period_start == period_end (as-of 단일일 성격 후보)
    if period_start is not None and period_end is not None and str(period_start) == str(period_end):
        reasons.append("period_is_single_day")

    # 4) status_reason 패턴(자동생성 비대상/결정 불가 경로 후보)
    if isinstance(status_reason, str) and status_reason in {
        "DOC_TYPE_INACTIVE_OR_MISSING",
        "CYCLE_INACTIVE",
        "MISSING_RULE",
        "SLOT_NOT_RESOLVED",
        "EXCEPTION",
        "DOCUMENT_LINK_BROKEN",
    }:
        reasons.append(f"status_reason_{status_reason}")

    # 5) anchor/due 둘 다 비어있으면 "계산 없이 기록" 계열 후보(특히 SKIPPED/FAILED)
    if _is_empty(gen_anchor) and _is_empty(due_date):
        reasons.append("anchor_and_due_empty")

    # 후보를 너무 넓히지 않기 위해, 최소 조건 조합(강한 신호)을 만족할 때만 후보로 취급
    strong = False
    if "period_basis_is_as_of_fallback" in reasons:
        strong = True
    if "cycle_code_is_null" in reasons and "period_is_single_day" in reasons:
        strong = True
    if any(r.startswith("status_reason_") for r in reasons) and "cycle_code_is_null" in reasons:
        strong = True

    return reasons if strong else []


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_reports(report_dir: Path, *, total: int, candidates: list[Candidate]) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    json_path = report_dir / f"fallback_candidates_{ts}.json"
    jsonl_path = report_dir / f"fallback_candidates_{ts}.jsonl"

    json_path.write_text(
        json.dumps(
            {"total": total, "candidates": [asdict(c) for c in candidates]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with jsonl_path.open("w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")

    return json_path, jsonl_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose AS_OF_FALLBACK candidates (read-only; uses DB copy).")
    ap.add_argument("--limit", type=int, default=200, help="max rows to output")
    ap.add_argument("--json", type=str, default="", help="optional path to write JSON report")
    ap.add_argument("--db-path", type=str, default="", help="optional sqlite db path override")
    ap.add_argument("--report-dir", type=str, default="reports", help="directory to write timestamped reports")
    args = ap.parse_args()

    db_path = Path(args.db_path).resolve() if args.db_path else _get_db_path()
    if not db_path.exists():
        print(f"[FAIL] DB not found: {db_path}")
        return 2

    before_stat = db_path.stat()
    before_hash = _sha256(db_path)

    conn, tmp_db = _open_temp_copy(db_path)
    try:
        if not _table_exists(conn, "document_instances"):
            print("[OK] document_instances table not found (no candidates)")
            return 0

        cols = _col_names(conn, "document_instances")
        needed = {"id", "site_id", "document_type_code", "period_start", "period_end", "status", "status_reason"}
        missing = sorted(needed - cols)
        if missing:
            print(f"[FAIL] document_instances missing columns: {missing}")
            return 2

        # 전체 스캔(로컬 SQLite 기준 규모 가정). 필요시 이후 조건/인덱스 기반 최적화 가능.
        rows = conn.execute("SELECT * FROM document_instances").fetchall()
        candidates: list[Candidate] = []
        for r in rows:
            rs = candidate_reasons(dict(r), cols)
            if not rs:
                continue
            candidates.append(
                Candidate(
                    id=_safe_get(r, "id"),  # type: ignore[arg-type]
                    site_id=_safe_get(r, "site_id"),  # type: ignore[arg-type]
                    document_type_code=_safe_get(r, "document_type_code"),  # type: ignore[arg-type]
                    period_start=str(_safe_get(r, "period_start")) if _safe_get(r, "period_start") is not None else None,
                    period_end=str(_safe_get(r, "period_end")) if _safe_get(r, "period_end") is not None else None,
                    cycle_code=_safe_get(r, "cycle_code"),  # type: ignore[arg-type]
                    period_basis=_safe_get(r, "period_basis"),  # type: ignore[arg-type]
                    status=_safe_get(r, "status"),  # type: ignore[arg-type]
                    status_reason=_safe_get(r, "status_reason"),  # type: ignore[arg-type]
                    generation_anchor_date=str(_safe_get(r, "generation_anchor_date"))
                    if ("generation_anchor_date" in cols and _safe_get(r, "generation_anchor_date") is not None)
                    else None,
                    due_date=str(_safe_get(r, "due_date"))
                    if ("due_date" in cols and _safe_get(r, "due_date") is not None)
                    else None,
                    document_id=_safe_get(r, "document_id") if "document_id" in cols else None,  # type: ignore[arg-type]
                    error_message=_safe_get(r, "error_message") if "error_message" in cols else None,  # type: ignore[arg-type]
                    reasons=rs,
                )
            )

        total = len(rows)
        cand_n = len(candidates)
        print(f"[INFO] scanned_rows={total} candidates={cand_n}")

        out = [asdict(c) for c in candidates[: args.limit]]
        if out:
            print("[CANDIDATES] showing up to limit")
            for c in out:
                print(json.dumps(c, ensure_ascii=False))
        else:
            print("[OK] no fallback candidates found")

        if args.json:
            Path(args.json).write_text(
                json.dumps(
                    {"total": total, "candidates": [asdict(c) for c in candidates]},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"[INFO] wrote json report: {args.json}")

        # 운영 흔적 보관: 타임스탬프 파일 저장(항상)
        report_dir = (BACKEND_DIR / args.report_dir).resolve()
        json_path, jsonl_path = _write_reports(report_dir, total=total, candidates=candidates)
        print(f"[INFO] report_json={json_path}")
        print(f"[INFO] report_jsonl={jsonl_path}")

        # 후보가 0건이면 의미 보존 완료 게이트 통과
        return 0 if cand_n == 0 else 3
    finally:
        conn.close()
        try:
            tmp_db.unlink(missing_ok=True)
        except Exception:
            # 임시 파일 삭제 실패는 진단 결과에 영향 없으므로 무시
            pass
        # 원본 DB 비오염 검증(해시/크기/mtime 불변)
        after_stat = db_path.stat()
        after_hash = _sha256(db_path)
        if (
            before_stat.st_size != after_stat.st_size
            or int(before_stat.st_mtime) != int(after_stat.st_mtime)
            or before_hash != after_hash
        ):
            print("[FAIL] original DB changed during diagnosis (should be read-only)")
            print(f"[INFO] before_size={before_stat.st_size} after_size={after_stat.st_size}")
            print(f"[INFO] before_mtime={before_stat.st_mtime} after_mtime={after_stat.st_mtime}")
            return 2


if __name__ == "__main__":
    raise SystemExit(main())

