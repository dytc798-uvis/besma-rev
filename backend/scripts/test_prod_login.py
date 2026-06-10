"""Quick login test against local API (run on EC2)."""
from __future__ import annotations

import sys
from pathlib import Path

import json
import urllib.parse
import urllib.request

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.security import verify_password
from app.core.database import SessionLocal, init_db
from app.modules.users.models import User


def _post_login(login_id: str, password: str) -> tuple[int, dict]:
    body = urllib.parse.urlencode({"username": login_id, "password": password}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8001/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, json.loads(resp.read().decode())


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(User.role == "SITE_FUNCTIONAL_EVAL")
            .order_by(User.login_id)
            .limit(8)
            .all()
        )
        print("sample FE users:", [(u.login_id, u.name) for u in users])
        if not users:
            print("no SITE_FUNCTIONAL_EVAL users")
            return
        user = users[0]
        login_id = user.login_id
        # verify hash path works
        print("hash verify 1111:", verify_password("1111", user.password_hash))
    finally:
        db.close()

    cases = [
        (login_id, "1111"),
        ("DL전도관구-백대진", "690505"),
        ("대우청주-김승모", "700824"),
    ]
    for lid, pw in cases:
        try:
            status, data = _post_login(lid, pw)
            print(f"api login {lid!r} pw={pw} -> {status}", {k: data.get(k) for k in ("access_token", "must_change_password") if k in data})
        except urllib.error.HTTPError as e:
            print(f"api login {lid!r} pw={pw} -> {e.code}", e.read().decode()[:200])


if __name__ == "__main__":
    main()
