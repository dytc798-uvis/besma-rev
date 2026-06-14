"""6월 11일 업로드 ERP xls(월별집계·출역일보) 재반영 + 등급 통계 스냅샷 재생성.

Usage:
  cd backend && PYTHONPATH=. python scripts/rebuild_fe_erp_grade_stats.py
  cd backend && PYTHONPATH=. python scripts/rebuild_fe_erp_grade_stats.py --docs ../docs
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.modules.functional_eval.eval_provisioning import (
    apply_attendance_report_file,
    apply_monthly_site_aggregate_file,
)
from app.modules.functional_eval import grade_stats_cache
from app.modules.functional_eval.service import get_or_create_active_period


def _pick(docs: Path, pattern: str) -> Path | None:
    files = [p for p in docs.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=str(REPO / "docs"))
    args = parser.parse_args()
    docs = Path(args.docs)
    if not docs.is_dir():
        raise SystemExit(f"docs dir not found: {docs}")

    agg = _pick(docs, "*20260610094015*.xls") or _pick(docs, "월별현장별집계_*.xls")
    att = _pick(docs, "*20260610094137*.xls") or _pick(docs, "출역일보_*.xls")
    if not agg or not att:
        raise SystemExit(f"missing ERP xls under {docs}")

    print("aggregate:", agg.name)
    print("attendance:", att.name)

    init_db()
    db = SessionLocal()
    try:
        period = get_or_create_active_period(db)
        agg_res = apply_monthly_site_aggregate_file(db, period, agg, original_filename=agg.name)
        print("aggregate:", {k: agg_res[k] for k in ("site_count", "erp_headcount_total", "registry_upserted") if k in agg_res})

        att_res = apply_attendance_report_file(db, period, att, original_filename=att.name)
        print(
            "attendance:",
            {k: att_res[k] for k in ("work_date", "linked_workers", "skipped_no_registry", "site_count") if k in att_res},
        )

        db.refresh(period)
        snapshot = grade_stats_cache.rebuild_and_persist(db, period)
        overall = snapshot.get("overall", {}).get("functional", {})
        print(
            "grade stats snapshot:",
            {
                "erp_headcount_total": snapshot.get("erp_headcount_total"),
                "workers_total": overall.get("workers_total"),
                "attendance_workers": overall.get("attendance_workers"),
                "graded_total": overall.get("graded_total"),
                "computed_at_label": snapshot.get("computed_at_label"),
            },
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
