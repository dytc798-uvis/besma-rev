"""docs/ 최신 ERP xls 4종 반영 (집계 → 출역 → 일용직·사원리스트).

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
from app.modules.functional_eval.roster import parse_daily_roster
from app.modules.functional_eval.service import (
    apply_daily_roster_diff,
    get_or_create_active_period,
)
from app.modules.workers.service import import_sawon_list_from_path


def _latest(docs: Path, pattern: str) -> Path | None:
    files = [p for p in docs.glob(pattern) if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--docs", default=str(REPO / "docs"))
    parser.add_argument("--skip-roster", action="store_true")
    parser.add_argument("--skip-sawon", action="store_true")
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

        if employee and not args.skip_sawon:
            batch, ingestion = import_sawon_list_from_path(db, employee)
            print(
                "employee list:",
                {
                    "batch_id": batch.id,
                    "imported_rows": ingestion.get("imported_employee_rows"),
                    "file": employee.name,
                },
            )

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
            parsed_roster = parse_daily_roster(roster)
            if not parsed_roster:
                print("roster skip: no rows parsed from", roster.name)
            else:
                roster_res = apply_daily_roster_diff(
                    db,
                    period,
                    parsed_roster,
                    original_filename=roster.name,
                    stored_path=str(roster),
                )
                print(
                    "roster apply:",
                    {
                        k: roster_res[k]
                        for k in ("new_count", "updated_count", "removed_count", "total_rows")
                        if k in roster_res
                    },
                )
    finally:
        db.close()


if __name__ == "__main__":
    main()
