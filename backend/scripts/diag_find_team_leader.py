"""Find team leader name across functional eval tables (production)."""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

DB = Path("/home/ubuntu/besma-rev/database/besma.db")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--site-code", default="24025")
    parser.add_argument("--db", default=str(DB))
    args = parser.parse_args()

    name = args.name.strip()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%functional_eval%' ORDER BY name"
        )]
        print("tables:", tables)

        for table in tables:
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            text_cols = [c for c in cols if any(k in c.lower() for k in ("name", "login", "leader", "rep", "rrn"))]
            if not text_cols:
                continue
            clauses = " OR ".join(f"{c} LIKE ?" for c in text_cols)
            params = [f"%{name}%"] * len(text_cols)
            if "site_code" in cols:
                clauses = f"site_code = ? AND ({clauses})"
                params = [args.site_code, *params]
            sql = f"SELECT * FROM {table} WHERE {clauses} LIMIT 5"
            rows = conn.execute(sql, params).fetchall()
            if rows:
                print(f"\n{table}:")
                for row in rows:
                    d = {k: row[k] for k in text_cols if k in row.keys()}
                    print(" ", d)

        print("\n--- team leaders @ site ---")
        users = conn.execute(
            """
            SELECT u.login_id, u.name, COUNT(w.id) AS assigned
            FROM users u
            LEFT JOIN functional_eval_workers w
              ON w.assigned_evaluator_login_id = u.login_id AND w.site_code = ?
            WHERE u.role = 'SITE_FUNCTIONAL_EVAL' AND u.site_id IN (
              SELECT id FROM sites WHERE site_code = ?
            )
            GROUP BY u.id
            ORDER BY assigned DESC, u.login_id
            """,
            (args.site_code, args.site_code),
        ).fetchall()
        for u in users:
            print(dict(u))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
