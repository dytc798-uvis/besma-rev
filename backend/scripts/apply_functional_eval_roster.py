"""Apply 기능인제 일용직 명부 xlsx (HQ DIFF apply 와 동일). Usage:
  cd backend && PYTHONPATH=. python scripts/apply_functional_eval_roster.py /path/to/roster.xlsx
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.functional_eval import service  # noqa: E402
from app.modules.sites import models as site_models  # noqa: F401
from app.modules.users import models as user_models  # noqa: F401
from app.modules.functional_eval import models as fe_models  # noqa: F401


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: apply_functional_eval_roster.py <roster.xlsx>", file=sys.stderr)
        raise SystemExit(2)
    path = Path(sys.argv[1]).resolve()
    if not path.is_file():
        print(f"file not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    init_db()
    db = SessionLocal()
    try:
        period = service.get_or_create_active_period(db)
        result = service.apply_daily_roster_file(
            db, period, path, original_filename=path.name
        )
        print(result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
