"""기존 sites 테이블(소장·공무) → 신규현장 배포(new_site_deployments) 초기 이관.

Usage (from backend/):
  PYTHONPATH=. python scripts/seed_new_site_deployments_from_sites.py
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.new_site_deployment import models as nsd_models  # noqa: F401, E402
from app.modules.new_site_deployment.deployment_alias import derive_deployment_site_alias  # noqa: E402
from app.modules.new_site_deployment.models import NewSiteDeployment  # noqa: E402
from app.modules.new_site_deployment.service import (  # noqa: E402
    _default_safety_checks,
    _recompute_complete,
    _sync_administrators,
)
from app.modules.sites.models import Site  # noqa: E402
from app.modules.users import models as user_models  # noqa: F401, E402
from app.modules.users.models import User  # noqa: E402


def _seed_user(db) -> User:
    user = db.query(User).filter(User.login_id == "hq01").first()
    if user:
        return user
    user = db.query(User).filter(User.role == "SUPER_ADMIN").first()
    if user:
        return user
    user = db.query(User).order_by(User.id.asc()).first()
    if user is None:
        raise RuntimeError("no users in database")
    return user


def main() -> None:
    init_db()
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        actor = _seed_user(db)
        sites = (
            db.query(Site)
            .filter(Site.site_manager.isnot(None))
            .filter(Site.site_manager != "")
            .order_by(Site.site_name.asc())
            .all()
        )
        for site in sites:
            existing = (
                db.query(NewSiteDeployment)
                .filter(NewSiteDeployment.site_id == site.id)
                .first()
            )
            if existing:
                skipped += 1
                continue

            site_name = (site.site_name or "").strip()
            if not site_name:
                skipped += 1
                continue

            contractor = (site.contractor_name or "").strip() or None
            alias = derive_deployment_site_alias(contractor, site_name)
            admins: list[dict[str, str]] = []
            mgr = (site.site_manager or "").strip()
            if mgr:
                admins.append({"role": "SITE_MANAGER", "name": mgr})
            gongmu = (site.project_manager or "").strip()
            if gongmu and gongmu != mgr:
                admins.append({"role": "GONGMU", "name": gongmu})

            row = NewSiteDeployment(
                site_id=site.id,
                site_code=site.site_code,
                site_alias=alias,
                contractor=contractor,
                site_name=site_name,
                construction_amount=site.project_amount,
                safety_checks_json=_default_safety_checks(),
                created_by_user_id=actor.id,
                updated_by_user_id=actor.id,
            )
            db.add(row)
            db.flush()
            _sync_administrators(db, row, site, admins)
            row.is_complete = _recompute_complete(row)
            db.add(row)
            created += 1

        db.commit()
        print(f"created: {created}, skipped: {skipped}, total_sites: {len(sites)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
