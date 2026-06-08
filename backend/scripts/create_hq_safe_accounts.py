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
from app.modules.users.models import User  # noqa: E402

HQ_SAFE_ACCOUNTS: list[tuple[str, str, str]] = [
    ("조동문", "안전보건-조동문", "600321"),
    ("김복수", "안전보건-김복수", "721228"),
    ("권학상", "안전보건-권학상", "620215"),
    ("정상익", "안전보건-정상익", "790808"),
    ("엄재복", "안전보건-엄재복", "920619"),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for name, login_id, password in HQ_SAFE_ACCOUNTS:
            user = db.query(User).filter(User.login_id == login_id).first()
            if user is None:
                user = User(
                    name=name,
                    login_id=login_id,
                    password_hash=get_password_hash(password),
                    role=Role.HQ_SAFE,
                    ui_type=UIType.HQ_SAFE,
                    site_id=None,
                    department="안전보건실",
                    must_change_password=False,
                    is_active=True,
                )
                db.add(user)
                action = "created"
            else:
                user.name = name
                user.password_hash = get_password_hash(password)
                user.role = Role.HQ_SAFE
                user.ui_type = UIType.HQ_SAFE
                user.site_id = None
                user.department = "안전보건실"
                user.must_change_password = False
                user.is_active = True
                db.add(user)
                action = "updated"
            db.flush()
            print(f"{action} login_id={login_id} name={name} role={user.role.value}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
