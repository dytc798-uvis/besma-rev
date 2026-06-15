#!/usr/bin/env python3
"""기능인인정제 일일 진행현황 보고서 자동 생성 CLI.

Usage (backend 디렉터리):
  PYTHONPATH=. python scripts/generate_functional_eval_daily_report.py
  PYTHONPATH=. python scripts/generate_functional_eval_daily_report.py --date 2026-06-16
  PYTHONPATH=. python scripts/generate_functional_eval_daily_report.py --force

Cron (서버 timezone=Asia/Seoul):
  0 21 * * * cd /path/to/backend && PYTHONPATH=. python scripts/generate_functional_eval_daily_report.py >> logs/functional_eval_daily_report.log 2>&1

Cron (서버 timezone=UTC, 21:00 KST = 12:00 UTC):
  0 12 * * * cd /path/to/backend && PYTHONPATH=. python scripts/generate_functional_eval_daily_report.py >> logs/functional_eval_daily_report.log 2>&1
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.core.datetime_utils import kst_today
from app.modules.functional_eval import daily_report_service, service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fe_daily_report")


def main() -> int:
    parser = argparse.ArgumentParser(description="기능인인정제 일일 진행현황 보고서 생성")
    parser.add_argument("--date", type=str, default=None, help="보고일 YYYY-MM-DD (기본: KST 오늘)")
    parser.add_argument("--force", action="store_true", help="같은 날짜 보고서 재생성")
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else kst_today()
    init_db()
    db = SessionLocal()
    try:
        period = service.get_or_create_active_period(db)
        row = daily_report_service.generate_daily_report(
            db,
            period,
            report_date=report_date,
            generated_by="system" if not args.force else "manual",
            force=args.force,
        )
        logger.info(
            "OK report_id=%s date=%s completion=%.1f%% path=%s",
            row.id,
            row.report_date,
            row.completion_rate,
            row.report_path,
        )
        return 0
    except ValueError as exc:
        if str(exc) == "REPORT_ALREADY_EXISTS":
            logger.info("SKIP already exists for %s", report_date)
            return 0
        logger.exception("FAILED %s", exc)
        return 1
    except Exception:
        logger.exception("FAILED")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
