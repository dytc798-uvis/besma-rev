from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.seed.demo_login_users import ensure_demo_login_users  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create temporary BESMA demo login users")
    parser.add_argument("--password", default="temp@12", help="Temporary password for all demo users")
    parser.add_argument("--site-code", default="SITE002", help="Preferred site code for SITE demo users")
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        result = ensure_demo_login_users(
            db,
            password=args.password,
            site_code=args.site_code,
        )
        print(
            "[demo-login-users] site="
            f"{result.site_code} (id={result.site_id}, created={result.created_site})"
        )
        for user in result.users:
            print(
                "[demo-login-users] "
                f"{user.login_id} | {user.name} | {user.role} | "
                f"site_id={user.site_id} | password_ok={user.verified_password} | {user.action}"
            )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
