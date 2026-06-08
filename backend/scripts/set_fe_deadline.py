"""활성 기능인제 회차 마감일 변경. Usage: cd backend && PYTHONPATH=. python scripts/set_fe_deadline.py 2026-06-26"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.functional_eval.models import FunctionalEvalPeriod  # noqa: E402


def main() -> None:
    raw = sys.argv[1] if len(sys.argv) > 1 else "2026-06-26"
    y, m, d = [int(x) for x in raw.split("-")]
    target = date(y, m, d)

    init_db()
    db = SessionLocal()
    try:
        period = (
            db.query(FunctionalEvalPeriod)
            .filter(FunctionalEvalPeriod.is_active.is_(True))
            .order_by(FunctionalEvalPeriod.id.desc())
            .first()
        )
        if period is None:
            print("no active period")
            raise SystemExit(1)
        old = period.deadline_date
        period.deadline_date = target
        db.add(period)
        db.commit()
        print(f"period_id={period.id} deadline {old} -> {target}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
