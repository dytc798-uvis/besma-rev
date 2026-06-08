"""현장별 근로자 순번(row_no) 재부여 — 명부 일괄 반영 시 1로 고정된 데이터 수정.

Usage:
  cd backend && PYTHONPATH=. python scripts/resequence_fe_row_numbers.py
  cd backend && PYTHONPATH=. python scripts/resequence_fe_row_numbers.py --site 26025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.functional_eval import service  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
from app.modules.functional_eval.models import FunctionalEvalWorker  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="특정 현장코드만 재부여")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        period = service.get_or_create_active_period(db)
        q = db.query(FunctionalEvalWorker.site_code).filter(
            FunctionalEvalWorker.period_id == period.id,
            FunctionalEvalWorker.is_active.is_(True),
        )
        if args.site:
            q = q.filter(FunctionalEvalWorker.site_code == args.site.strip())
        site_codes = sorted({row[0] for row in q.distinct().all() if row[0]})
        for site_code in site_codes:
            service.resequence_site_row_numbers(db, period.id, site_code)
            print(f"resequenced site_code={site_code}")
        db.commit()
        print(f"done period_id={period.id} sites={len(site_codes)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
