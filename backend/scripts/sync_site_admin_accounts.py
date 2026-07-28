from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.modules.sites import models as site_models  # noqa: F401, E402
from app.modules.users.site_admin_account_service import (  # noqa: E402
    apply_site_admin_plan,
    build_site_admin_plan,
    summarize_site_admin_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("site_source", type=Path)
    parser.add_argument("employee_source", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.apply:
            result = apply_site_admin_plan(
                db,
                site_source=args.site_source,
                employee_source=args.employee_source,
                as_of=args.as_of,
            )
        else:
            plans, excluded = build_site_admin_plan(
                db,
                site_source=args.site_source,
                employee_source=args.employee_source,
                as_of=args.as_of,
            )
            result = {
                **summarize_site_admin_plan(plans, excluded),
                "mode": "dry_run",
            }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
