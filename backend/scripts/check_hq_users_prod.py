"""List HQ Korean login users (run on EC2)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path("/home/ubuntu/besma-rev/database/besma.db")

def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT login_id, name, role, ui_type, is_active, department
            FROM users
            WHERE login_id LIKE '안전보건-%'
               OR login_id IN ('hq01','hq02','hq03','hq04','hq05')
            ORDER BY login_id
            """
        ).fetchall()
        for r in rows:
            print(dict(r))
    finally:
        conn.close()

if __name__ == "__main__":
    main()
