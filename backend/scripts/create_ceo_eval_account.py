"""기능인제 대표이사 최종승인 계정 생성.

Usage:
  cd backend && PYTHONPATH=. python scripts/create_ceo_eval_account.py
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.security import get_password_hash  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.enums import Role, UIType  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
from app.modules.functional_eval.constants import CEO_EVAL_LOGIN_IDS  # noqa: E402
from app.modules.users.models import User  # noqa: E402

CEO_LOGIN_ID = next(iter(CEO_EVAL_LOGIN_IDS))
CEO_NAME = "김홍수"
CEO_PASSWORD = "611001"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.login_id == CEO_LOGIN_ID).first()
        if user is None:
            user = User(
                name=CEO_NAME,
                login_id=CEO_LOGIN_ID,
                password_hash=get_password_hash(CEO_PASSWORD),
                role=Role.HQ_SAFE_ADMIN,
                ui_type=UIType.HQ_SAFE,
                site_id=None,
                must_change_password=False,
                is_active=True,
            )
            db.add(user)
            action = "created"
        else:
            user.name = CEO_NAME
            user.password_hash = get_password_hash(CEO_PASSWORD)
            user.role = Role.HQ_SAFE_ADMIN
            user.ui_type = UIType.HQ_SAFE
            user.site_id = None
            user.must_change_password = False
            user.is_active = True
            db.add(user)
            action = "updated"
        db.commit()
        print(f"{action} login_id={CEO_LOGIN_ID} role={user.role.value} ui_type={user.ui_type.value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
