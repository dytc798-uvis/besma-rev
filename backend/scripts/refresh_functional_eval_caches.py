#!/usr/bin/env python3
"""Refresh functional-eval cached HQ metrics.

Usage:
  PYTHONPATH=. python scripts/refresh_functional_eval_caches.py --monitoring
  PYTHONPATH=. python scripts/refresh_functional_eval_caches.py --grade-stats
  PYTHONPATH=. python scripts/refresh_functional_eval_caches.py --all

Cron examples:
  # Monitoring snapshot: every hour
  5 * * * * cd /home/ubuntu/besma-rev/backend && PYTHONPATH=. .venv/bin/python scripts/refresh_functional_eval_caches.py --monitoring >> logs/functional_eval_cache.log 2>&1

  # Grade statistics snapshot: once a day before the daily report
  55 20 * * * cd /home/ubuntu/besma-rev/backend && PYTHONPATH=. .venv/bin/python scripts/refresh_functional_eval_caches.py --grade-stats --force-grade-stats >> logs/functional_eval_cache.log 2>&1
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.modules.functional_eval import grade_stats_cache, service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fe_cache_refresh")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh functional-eval HQ cached metrics")
    parser.add_argument("--all", action="store_true", help="Refresh every supported cache")
    parser.add_argument("--monitoring", action="store_true", help="Refresh HQ monitoring summary cache")
    parser.add_argument("--grade-stats", action="store_true", help="Refresh HQ grade stats cache")
    parser.add_argument(
        "--force-grade-stats",
        action="store_true",
        help="Rebuild grade stats even when the daily cache is still valid",
    )
    args = parser.parse_args()

    refresh_monitoring = args.all or args.monitoring
    refresh_grade_stats = args.all or args.grade_stats
    if not refresh_monitoring and not refresh_grade_stats:
        parser.error("choose --monitoring, --grade-stats, or --all")

    init_db()
    db = SessionLocal()
    try:
        period = service.get_or_create_active_period(db)
        if refresh_monitoring:
            payload = service.get_hq_monitoring_summary(db, period)
            cache = payload.get("cache") or {}
            logger.info("OK monitoring mode=%s computed_at=%s", cache.get("mode"), cache.get("computed_at"))
        if refresh_grade_stats:
            if args.force_grade_stats:
                payload = grade_stats_cache.rebuild_and_persist(db, period)
            else:
                payload = grade_stats_cache.get_hq_grade_stats(db, period)
            logger.info(
                "OK grade_stats mode=%s computed_at=%s",
                payload.get("grade_stats_mode"),
                payload.get("computed_at"),
            )
        return 0
    except Exception:
        logger.exception("FAILED")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
