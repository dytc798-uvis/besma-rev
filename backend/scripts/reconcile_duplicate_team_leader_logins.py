"""팀장 login_id 중복 통일."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry
from app.modules.functional_eval.team_leader_login import (
    normalize_login_to_person_name,
    reconcile_team_leader_assignments,
    resolve_canonical_team_leader_login,
)
from app.modules.sites.models import Site
from app.modules.users.models import User


def _import_models() -> None:
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401


def main() -> int:
    parser = argparse.ArgumentParser(description="팀장 login_id 중복 통일")
    parser.add_argument("--db", default="/home/ubuntu/besma-rev/database/besma.db")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(f"sqlite:///{args.db}", connect_args={"check_same_thread": False})
    _import_models()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    period = (
        db.query(FunctionalEvalPeriod)
        .filter(FunctionalEvalPeriod.is_active.is_(True))
        .order_by(FunctionalEvalPeriod.id.desc())
        .first()
    )
    if period is None:
        print("active period not found")
        return 1

    site_codes = [
        row.site_code
        for row in db.query(FunctionalEvalSiteRegistry.site_code)
        .order_by(FunctionalEvalSiteRegistry.site_code)
        .all()
    ]

    worker_changed = 0
    for site_code in site_codes:
        worker_changed += reconcile_team_leader_assignments(db, period, site_code)

    user_changed = 0
    eval_users = (
        db.query(User)
        .filter(User.role == Role.SITE_FUNCTIONAL_EVAL.value, User.is_active.is_(True))
        .order_by(User.name, User.login_id)
        .all()
    )
    by_name: dict[str, list[User]] = defaultdict(list)
    for user in eval_users:
        key = normalize_login_to_person_name(user.login_id or "") or (user.name or "").strip()
        if key:
            by_name[key].append(user)

    for users in by_name.values():
        if len(users) <= 1:
            continue
        by_site: dict[int | None, list[User]] = defaultdict(list)
        for user in users:
            by_site[user.site_id].append(user)

        for site_users in by_site.values():
            if len(site_users) <= 1:
                continue
            display_name = (site_users[0].name or "").strip()
            logins = sorted({(u.login_id or "").strip() for u in site_users if (u.login_id or "").strip()})
            site = None
            if site_users[0].site_id:
                site = db.query(Site).filter(Site.id == site_users[0].site_id).first()
            site_code = (site.site_code if site else "") or ""
            canonical = resolve_canonical_team_leader_login(
                db,
                site_code=site_code,
                person_name=display_name,
                candidate_logins=logins,
                period_id=period.id,
            )
            for user in site_users:
                if (user.login_id or "").strip() == canonical:
                    continue
                print(f"deactivate user id={user.id} login={user.login_id} -> canonical={canonical}")
                if not args.dry_run:
                    user.is_active = False
                    db.add(user)
                user_changed += 1

    print(f"worker_assignments_changed={worker_changed} users_deactivated={user_changed}")
    if args.dry_run:
        db.rollback()
    else:
        db.commit()
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
