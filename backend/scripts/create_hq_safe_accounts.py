"""안전보건실 HQ 계정 생성 (기존 hq01~hq05 데모 계정과 별도).

Usage:
  cd backend && PYTHONPATH=. python scripts/create_hq_safe_accounts.py
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
from app.modules.users.hq_safe_accounts import HQ_SAFE_ACCOUNT_SPECS  # noqa: E402
from app.modules.users.models import User  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for spec in HQ_SAFE_ACCOUNT_SPECS:
            login_id = spec.login_id
            user = db.query(User).filter(User.login_id == login_id).first()
            department = "안전보건실"
            if spec.title:
                department = f"{department}({spec.title})"
            if user is None:
                user = User(
                    name=spec.name,
                    login_id=login_id,
                    password_hash=get_password_hash(spec.password),
                    role=Role.HQ_SAFE,
                    ui_type=UIType.HQ_SAFE,
                    site_id=None,
                    department=department,
                    must_change_password=False,
                    is_active=True,
                )
                db.add(user)
                action = "created"
            else:
                user.name = spec.name
                user.password_hash = get_password_hash(spec.password)
                user.role = Role.HQ_SAFE
                user.ui_type = UIType.HQ_SAFE
                user.site_id = None
                user.department = department
                user.must_change_password = False
                user.is_active = True
                db.add(user)
                action = "updated"
            db.flush()
            web = "FE+삼성" if spec.fe_samsung_web else "-"
            print(f"{action} login_id={login_id} name={spec.name} title={spec.title} web={web}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
