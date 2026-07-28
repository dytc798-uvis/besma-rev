from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.datetime_utils import utc_now  # noqa: E402
from app.modules.new_site_deployment.deployment_alias import (  # noqa: E402
    derive_deployment_site_alias,
)
from app.modules.new_site_deployment.models import (  # noqa: E402
    NewSiteDeployment,
    NewSiteDeploymentAdministrator,
)
from app.modules.sites.models import Site  # noqa: E402
from app.modules.sites.latest_sync import (  # noqa: E402
    is_current_missing_site,
    site_attrs,
)
from app.modules.sites.service import parse_amount  # noqa: E402
from app.modules.users.models import User  # noqa: F401, E402
from app.utils.file_ingestion import parse_excel_with_fallback  # noqa: E402


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def load_rows(path: Path) -> list[dict[str, str]]:
    parsed = parse_excel_with_fallback(path)
    headers = [clean(value) for value in parsed.headers]
    result: list[dict[str, str]] = []
    for values in parsed.rows:
        row = {
            header: clean(values[index]) if index < len(values) else ""
            for index, header in enumerate(headers)
            if header
        }
        if row.get("현장코드") or row.get("현장명"):
            result.append(row)
    return result


def ensure_deployment(db, site: Site, row: dict[str, str]) -> bool:
    existing = (
        db.query(NewSiteDeployment)
        .filter(NewSiteDeployment.site_code == site.site_code)
        .order_by(NewSiteDeployment.id.desc())
        .first()
    )
    if existing is not None:
        return False
    deployment = NewSiteDeployment(
        site_id=site.id,
        site_code=site.site_code,
        site_alias=derive_deployment_site_alias(
            row.get("도급사명"), row.get("현장명", "")
        ),
        contractor=row.get("도급사명") or None,
        site_name=row.get("현장명", "")[:300],
        construction_amount=parse_amount(row.get("도급금액")),
        construction_period=row.get("공사기간") or None,
        site_manager_name=row.get("소장") or None,
        gongmu_name=row.get("공무") or None,
        safety_checks_json={},
        is_complete=False,
    )
    db.add(deployment)
    db.flush()
    for index, (role, name) in enumerate(
        (
            ("SITE_MANAGER", row.get("소장")),
            ("GONGMU", row.get("공무")),
            ("OTHER", row.get("기타")),
        )
    ):
        if name:
            db.add(
                NewSiteDeploymentAdministrator(
                    deployment_id=deployment.id,
                    role=role,
                    name=name,
                    login_id=None,
                    sort_order=index,
                )
            )
    return True


def run(source: Path, *, as_of: date, apply: bool) -> dict[str, Any]:
    rows = load_rows(source)
    db = SessionLocal()
    created_codes: list[str] = []
    deployments_created = 0
    existing_manager_updates = 0
    skipped: dict[str, int] = {}
    try:
        sites = {site.site_code: site for site in db.query(Site).all()}
        for row in rows:
            code = row.get("현장코드", "")
            site = sites.get(code)
            if site is not None:
                changed = False
                for field, value in (
                    ("project_manager", row.get("소장")),
                    ("site_manager", row.get("공무")),
                ):
                    if value and getattr(site, field) != value:
                        if apply:
                            setattr(site, field, value)
                            site.updated_at = utc_now()
                            db.add(site)
                        changed = True
                if changed:
                    existing_manager_updates += 1
                continue

            include, reason = is_current_missing_site(row, as_of)
            if not include:
                if reason:
                    skipped[reason] = skipped.get(reason, 0) + 1
                continue
            created_codes.append(code)
            if apply:
                site = Site(**site_attrs(row))
                db.add(site)
                db.flush()
                sites[code] = site
                if ensure_deployment(db, site, row):
                    deployments_created += 1
        if apply:
            db.commit()
        else:
            db.rollback()
        return {
            "mode": "apply" if apply else "dry_run",
            "source": source.name,
            "as_of": as_of.isoformat(),
            "source_rows": len(rows),
            "site_create_count": len(created_codes),
            "site_create_codes": created_codes,
            "deployment_create_count": (
                deployments_created if apply else len(created_codes)
            ),
            "existing_manager_update_count": existing_manager_updates,
            "skipped_missing_site_reasons": skipped,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.source, as_of=args.as_of, apply=args.apply),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
