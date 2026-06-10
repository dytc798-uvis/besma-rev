"""안전보건 HQ 계정 존재·로그인 검증."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.security import verify_password  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.modules.users.models import User  # noqa: E402
from app.modules.users.hq_safe_accounts import HQ_SAFE_ACCOUNTS  # noqa: E402


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        for name, login_id, password in HQ_SAFE_ACCOUNTS:
            user = db.query(User).filter(User.login_id == login_id).first()
            if user is None:
                print(f"MISSING {login_id}")
                continue
            ok = verify_password(password, user.password_hash)
            print(f"{'OK' if ok else 'BAD_PW'} {login_id} role={user.role.value} active={user.is_active}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
