"""Check team-leader assignments vs User accounts (production diagnostic)."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal, init_db
from app.modules.functional_eval.models import FunctionalEvalSiteRegistry, FunctionalEvalWorker
from app.modules.functional_eval.service import _manager_login_for_site, get_or_create_active_period
from app.modules.users.models import User


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
        user_logins = {u.login_id for u in db.query(User).filter(User.is_active.is_(True)).all()}
        missing: dict[str, set[str]] = {}
        for w in workers:
            assigned = (w.assigned_evaluator_login_id or "").strip()
            if not assigned:
                continue
            mgr = _manager_login_for_site(db, w.site_code)
            if assigned == mgr or assigned == w.site_code:
                continue
            if assigned not in user_logins:
                missing.setdefault(assigned, set()).add(w.site_code)
        print(f"period={period.id} workers={len(workers)}")
        print(f"missing team-leader User accounts: {len(missing)}")
        for login, sites in sorted(missing.items())[:40]:
            print(f"  {login!r} sites={sorted(sites)}")
        if len(missing) > 40:
            print(f"  ... +{len(missing) - 40} more")
    finally:
        db.close()


if __name__ == "__main__":
    main()
