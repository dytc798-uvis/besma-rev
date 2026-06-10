"""Assignment breakdown for functional eval workers."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD
from app.modules.functional_eval.models import FunctionalEvalWorker
from app.modules.functional_eval.service import _manager_login_for_site, get_or_create_active_period


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        period = get_or_create_active_period(db)
        workers = (
            db.query(FunctionalEvalWorker)
            .filter(
                FunctionalEvalWorker.period_id == period.id,
                FunctionalEvalWorker.is_site_manager.is_(False),
                FunctionalEvalWorker.is_active.is_(True),
            )
            .all()
        )
        team_assigned = 0
        mgr_assigned = 0
        other = 0
        by_site_team: Counter[str] = Counter()
        for w in workers:
            assigned = (w.assigned_evaluator_login_id or "").strip()
            mgr = _manager_login_for_site(db, w.site_code)
            if assigned == mgr or assigned == w.site_code or not assigned:
                mgr_assigned += 1
            else:
                team_assigned += 1
                by_site_team[w.site_code] += 1
        print(f"threshold={TEAM_LEADER_SPLIT_THRESHOLD} last_attendance={period.last_attendance_date}")
        print(f"workers={len(workers)} mgr_assigned={mgr_assigned} team_assigned={team_assigned}")
        print("sites with team assignments:", len(by_site_team))
        for site, cnt in by_site_team.most_common(15):
            mgr = _manager_login_for_site(db, site)
            print(f"  site={site} team_workers={cnt} mgr_login={mgr!r}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
