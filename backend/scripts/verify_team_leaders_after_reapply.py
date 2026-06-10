from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.security import verify_password
from app.core.database import SessionLocal, init_db
from app.core.enums import Role
from app.modules.functional_eval.service import _is_primary_site_evaluator, _site_code_for_user
from app.modules.users.models import User


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.role == Role.SITE_FUNCTIONAL_EVAL, User.is_active.is_(True)).all()
        leaders = [u for u in users if not _is_primary_site_evaluator(db, u, _site_code_for_user(u, db))]
        print("team_leaders", len(leaders))
        for u in leaders[:10]:
            print(" ", u.login_id, u.name)
        sample = next((u for u in leaders if "이현재" in (u.login_id or "")), leaders[0] if leaders else None)
        if sample:
            print("sample login:", sample.login_id, "pw730529:", verify_password("730529", sample.password_hash))
    finally:
        db.close()


if __name__ == "__main__":
    main()
