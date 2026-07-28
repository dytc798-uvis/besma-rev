from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.modules.sites import models as site_models  # noqa: F401, E402
from app.modules.users.hq_erp_account_service import (  # noqa: E402
    apply_account_plan,
    build_account_plan,
    summarize_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.apply:
            result = apply_account_plan(db, args.source)
        else:
            plans, excluded, _rows, label = build_account_plan(db, args.source)
            result = summarize_plan(plans, excluded, label)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
