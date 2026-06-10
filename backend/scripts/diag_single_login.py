"""Diagnose a single login_id on production (run on server)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.security import verify_password

DB = Path("/home/ubuntu/besma-rev/database/besma.db")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("login_id")
    parser.add_argument("--passwords", nargs="*", default=["1111"])
    parser.add_argument("--db", default=str(DB))
    parser.add_argument("--site-code", default="24025")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        login = args.login_id.strip()
        name_part = login.split("-", 1)[1] if "-" in login else login

        user = conn.execute(
            "SELECT id, login_id, name, role, is_active, site_id, password_hash FROM users WHERE login_id = ?",
            (login,),
        ).fetchone()
        print("exact:", dict(user) if user else "NOT FOUND")
        if user:
            for pw in args.passwords:
                print(f"  pw {pw!r}: {verify_password(pw, user['password_hash'])}")

        like = conn.execute(
            "SELECT id, login_id, name, role, is_active FROM users WHERE login_id LIKE ? OR name LIKE ?",
            (f"%{name_part}%", f"%{name_part}%"),
        ).fetchall()
        print("similar users:", [dict(r) for r in like])

        site_code = args.site_code
        evaluators = conn.execute(
            """
            SELECT DISTINCT assigned_evaluator_login_id
            FROM functional_eval_workers
            WHERE site_code = ? AND assigned_evaluator_login_id IS NOT NULL
            ORDER BY assigned_evaluator_login_id
            """,
            (site_code,),
        ).fetchall()
        print(f"distinct evaluators @ {site_code}:", [r[0] for r in evaluators])

        assigned = conn.execute(
            """
            SELECT COUNT(*) AS c FROM functional_eval_workers
            WHERE site_code = ? AND assigned_evaluator_login_id = ?
            """,
            (site_code, login),
        ).fetchone()["c"]
        print(f"workers assigned to {login!r} @ {site_code}:", assigned)

        worker_cols = [r[1] for r in conn.execute("PRAGMA table_info(functional_eval_workers)")]
        print("worker columns:", worker_cols)

        if "rep_name" in worker_cols:
            roster = conn.execute(
                """
                SELECT name, rep_name, rrn_masked, assigned_evaluator_login_id
                FROM functional_eval_workers
                WHERE site_code = ? AND (rep_name LIKE ? OR name LIKE ?)
                LIMIT 10
                """,
                (site_code, f"%{name_part}%", f"%{name_part}%"),
            ).fetchall()
            print("roster match:", [dict(r) for r in roster])

        att_cols = [r[1] for r in conn.execute("PRAGMA table_info(functional_eval_attendance)")]
        print("attendance columns:", att_cols)
        leader_col = next((c for c in ("rep_name", "team_leader_name", "leader_name") if c in att_cols), None)
        if leader_col:
            att = conn.execute(
                f"""
                SELECT worker_name, {leader_col}, rrn_masked, work_date
                FROM functional_eval_attendance
                WHERE site_code = ? AND ({leader_col} LIKE ? OR worker_name LIKE ?)
                ORDER BY work_date DESC LIMIT 8
                """,
                (site_code, f"%{name_part}%", f"%{name_part}%"),
            ).fetchall()
            print("attendance match:", [dict(r) for r in att])

        fe_users = conn.execute(
            """
            SELECT login_id, name FROM users
            WHERE role = 'SITE_FUNCTIONAL_EVAL' AND (login_id LIKE ? OR name LIKE ?)
            ORDER BY login_id
            """,
            (f"%{name_part}%", f"%{name_part}%"),
        ).fetchall()
        print("SITE_FUNCTIONAL_EVAL match:", [dict(r) for r in fe_users])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
