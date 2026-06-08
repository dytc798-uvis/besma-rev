"""Diagnose functional-eval site manager login (run on server)."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.security import verify_password

DB = Path("/home/ubuntu/besma-rev/database/besma.db")
TARGET_LOGINS = ["대우청라-박명식", "24025"]
PASSWORDS = ["661123", "1111"]


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        for login in TARGET_LOGINS:
            user = conn.execute(
                "SELECT id, login_id, name, role, is_active, site_id, password_hash FROM users WHERE login_id = ?",
                (login,),
            ).fetchone()
            if not user:
                print(f"{login}: NOT FOUND")
                continue
            print(f"{login}: id={user['id']} name={user['name']} site_id={user['site_id']} active={user['is_active']}")
            for pw in PASSWORDS:
                print(f"  pw {pw}: {verify_password(pw, user['password_hash'])}")

        site = conn.execute("SELECT id, site_code, site_name, manager_name FROM sites WHERE site_code='24025'").fetchone()
        print("site 24025:", dict(site) if site else None)

        reg_count = conn.execute("SELECT COUNT(*) AS c FROM functional_eval_site_registry").fetchone()["c"]
        print("registry rows:", reg_count)

        worker = conn.execute(
            "SELECT name, rrn_masked, is_site_manager FROM functional_eval_workers WHERE site_code='24025' AND is_site_manager=1 LIMIT 3"
        ).fetchall()
        print("managers in roster:", [dict(w) for w in worker])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
