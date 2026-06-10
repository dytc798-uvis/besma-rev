"""Re-apply latest stored attendance file (rep_name + team leader accounts)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.modules.functional_eval.models import FunctionalEvalAttendanceImportBatch
from app.modules.functional_eval.service import apply_attendance_report_file, get_or_create_active_period


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        period = get_or_create_active_period(db)
        batch = (
            db.query(FunctionalEvalAttendanceImportBatch)
            .filter(FunctionalEvalAttendanceImportBatch.period_id == period.id)
            .order_by(FunctionalEvalAttendanceImportBatch.id.desc())
            .first()
        )
        if batch is None:
            print("no attendance batch")
            return
        path = Path(batch.stored_path)
        print(f"batch_id={batch.id} work_date={batch.work_date} path={path}")
        if not path.is_file():
            print("stored file missing:", path)
            return
        result = apply_attendance_report_file(
            db,
            period,
            path,
            original_filename=batch.original_filename or path.name,
        )
        print("result:", {k: result[k] for k in sorted(result) if k in (
            "work_date", "linked_workers", "created_accounts", "assigned_workers", "site_count"
        )})
        print("created_accounts:", result.get("created_accounts"))
        print("account_rows sample:", (result.get("account_rows") or [])[:5])
    finally:
        db.close()


if __name__ == "__main__":
    main()
