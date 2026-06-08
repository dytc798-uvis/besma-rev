#!/usr/bin/env python3
"""Production functional-eval HQ overview diagnostics."""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8001"


def post_login(username: str, password: str) -> str:
    data = urllib.parse.urlencode({"username": username, "password": password}).encode()
    req = urllib.request.Request(
        f"{BASE}/auth/login",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["access_token"]


def get_json(path: str, token: str) -> dict:
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def main() -> int:
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:////home/ubuntu/besma-rev/database/besma.db")
    with engine.connect() as conn:
        periods = conn.execute(
            text("SELECT id, is_active, deadline_date FROM functional_eval_periods ORDER BY id")
        ).fetchall()
        print("=== DB periods ===")
        for p in periods:
            pid = p[0]
            n = conn.execute(
                text(
                    "SELECT COUNT(*) FROM functional_eval_workers "
                    "WHERE period_id=:pid AND is_site_manager=0 AND is_active=1"
                ),
                {"pid": pid},
            ).scalar()
            sites = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT site_code) FROM functional_eval_workers "
                    "WHERE period_id=:pid AND is_site_manager=0 AND is_active=1"
                ),
                {"pid": pid},
            ).scalar()
            print(f"  period {pid} active={p[1]} deadline={p[2]} workers={n} sites={sites}")

    for user, pw in [("hq01", "1111"), ("hqsafe1", "1111"), ("hqsafe1", "besma123!")]:
        try:
            token = post_login(user, pw)
            print(f"\n=== API hq/summary as {user} ===")
            body = get_json("/functional-eval/hq/summary", token)
            print("totals", body.get("totals"))
            print("sites len", len(body.get("sites") or []))
            if body.get("sites"):
                print("first site", body["sites"][0])
            return 0
        except Exception as exc:
            print(f"login {user} failed: {exc}")

    print("No HQ login succeeded")
    return 1


if __name__ == "__main__":
    sys.exit(main())
