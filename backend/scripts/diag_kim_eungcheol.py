"""Deep diag for 김응철 team leader provisioning gap."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config.security import verify_password
from app.modules.functional_eval.site_alias import build_eval_login_id

DB = Path("/home/ubuntu/besma-rev/database/besma.db")
SITE = "24025"
NAME = "김응철"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        login = build_eval_login_id("대우청라", NAME)
        print("expected login_id:", login)

        w = conn.execute(
            "SELECT * FROM functional_eval_workers WHERE site_code=? AND name=?",
            (SITE, NAME),
        ).fetchone()
        print("worker self:", dict(w) if w else None)

        reps = conn.execute(
            """
            SELECT name, rep_name, rrn_hash, work_date
            FROM functional_eval_attendance_entries
            WHERE site_code=? AND rep_name=?
            """,
            (SITE, NAME),
        ).fetchall()
        print("as rep_name count:", len(reps))
        for r in reps[:5]:
            print(" ", dict(r))

        # leader RRN from attendance - find 김응철 as worker row on same day
        period = conn.execute(
            "SELECT id, last_attendance_date FROM functional_eval_periods WHERE is_active=1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        print("period:", dict(period) if period else None)

        site_count = conn.execute(
            """
            SELECT COUNT(DISTINCT rrn_hash) AS c
            FROM functional_eval_attendance_entries
            WHERE period_id=? AND site_code=? AND work_date=?
            """,
            (period["id"], SITE, period["last_attendance_date"]),
        ).fetchone()["c"]
        print("attendance count site:", site_count)

        leaders = conn.execute(
            """
            SELECT DISTINCT rep_name FROM functional_eval_attendance_entries
            WHERE period_id=? AND site_code=? AND work_date=? AND rep_name IS NOT NULL AND rep_name != ''
            ORDER BY rep_name
            """,
            (period["id"], SITE, period["last_attendance_date"]),
        ).fetchall()
        print("distinct rep_names:", [r[0] for r in leaders])

        for rep in leaders:
            rep_name = rep[0]
            lid = build_eval_login_id("대우청라", rep_name)
            u = conn.execute("SELECT login_id, name FROM users WHERE login_id=?", (lid,)).fetchone()
            print(f"  {rep_name!r} -> {lid!r} user:", dict(u) if u else "MISSING")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
