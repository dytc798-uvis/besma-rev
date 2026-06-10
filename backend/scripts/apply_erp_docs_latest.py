"""docs/ 최신 ERP xls 4종 반영 (집계 → 출역, 선택: 일용직·사원리스트).

Usage (on server):
  cd backend && PYTHONPATH=. .venv/bin/python scripts/apply_erp_docs_latest.py
  cd backend && PYTHONPATH=. .venv/bin/python scripts/apply_erp_docs_latest.py --docs /home/ubuntu/besma-rev/docs
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
from app.modules.functional_eval.service import apply_daily_roster_file, get_or_create_active_period


def _latest(docs: Path, pattern: str) -> Path | None:
    files = [p for p in docs.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=str(REPO / "docs"))
    parser.add_argument("--skip-roster", action="store_true")
    args = parser.parse_args()
    docs = Path(args.docs)
    if not docs.is_dir():
        raise SystemExit(f"docs dir not found: {docs}")

    agg = _latest(docs, "월별현장별집계_*.xls")
    att = _latest(docs, "출역일보_*.xls")
    roster = _latest(docs, "일용직사원리스트_*.xls") or _latest(docs, "daily_workers_raw*")
    employee = _latest(docs, "사원리스트_*.xls")

    if not agg or not att:
        raise SystemExit(f"missing aggregate or attendance under {docs}")

    print("aggregate:", agg)
    print("attendance:", att)
    if roster:
        print("roster (optional):", roster)
    if employee:
        print("employee list (optional):", employee)

    init_db()
    db = SessionLocal()
    try:
        period = get_or_create_active_period(db)
        agg_res = apply_monthly_site_aggregate_file(db, period, agg, original_filename=agg.name)
        print("aggregate result:", {k: agg_res[k] for k in ("site_count", "registry_upserted", "sites_upserted") if k in agg_res})

        att_res = apply_attendance_report_file(db, period, att, original_filename=att.name)
        print(
            "attendance result:",
            {
                k: att_res[k]
                for k in (
                    "work_date",
                    "linked_workers",
                    "created_accounts",
                    "assigned_workers",
                    "site_count",
                )
                if k in att_res
            },
        )
        sample = att_res.get("account_rows") or []
        print("account_rows sample:", sample[:8])

        if roster and not args.skip_roster:
            if roster.suffix.lower() == ".xlsx":
                roster_res = apply_daily_roster_file(db, period, roster, original_filename=roster.name)
                print(
                    "roster apply:",
                    {k: roster_res[k] for k in ("new_count", "updated_count", "removed_count") if k in roster_res},
                )
            else:
                print("roster skip: .xls roster is not applied here (use HQ roster xlsx import if needed)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
