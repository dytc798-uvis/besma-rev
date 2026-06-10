"""Per-site attendance counts on latest work date."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD
from app.modules.functional_eval.models import FunctionalEvalAttendanceEntry
from app.modules.functional_eval.service import get_latest_attendance_date, get_or_create_active_period


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        period = get_or_create_active_period(db)
        wd = get_latest_attendance_date(db, period.id)
        print(f"work_date={wd}")
        if not wd:
            return
        rows = (
            db.query(FunctionalEvalAttendanceEntry)
            .filter(
                FunctionalEvalAttendanceEntry.period_id == period.id,
                FunctionalEvalAttendanceEntry.work_date == wd,
            )
            .all()
        )
        by_site: Counter[str] = Counter()
        reps: Counter[tuple[str, str]] = Counter()
        for r in rows:
            by_site[r.site_code] += 1
            rep = (r.rep_name or "").strip()
            if rep:
                reps[(r.site_code, rep)] += 1
        big = [(s, c) for s, c in by_site.items() if c > TEAM_LEADER_SPLIT_THRESHOLD]
        print(f"entries={len(rows)} sites={len(by_site)} sites>{TEAM_LEADER_SPLIT_THRESHOLD}={len(big)}")
        for site, cnt in sorted(big, key=lambda x: -x[1])[:10]:
            site_reps = [rep for (s, rep), _ in reps.items() if s == site]
            print(f"  site={site} count={cnt} distinct_reps={len(set(site_reps))} sample_reps={list(set(site_reps))[:5]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
