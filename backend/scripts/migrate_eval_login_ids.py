"""기능인제 SITE_FUNCTIONAL_EVAL 계정 login_id를 별칭-이름 형식으로 일괄 전환 (SQLite 직접).

사용: cd backend && .venv/bin/python scripts/migrate_eval_login_ids.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.modules.functional_eval.eval_provisioning import normalize_erp_site_label
from app.modules.functional_eval.site_alias import build_eval_login_id, derive_site_alias

DB = Path("/home/ubuntu/besma-rev/database/besma.db")


def _ensure_unique_aliases(sites: list[sqlite3.Row]) -> dict[int, str]:
    alias_to_site_id: dict[int, int] = {}
    result: dict[int, str] = {}
    for site in sites:
        base = derive_site_alias(site["site_name"] or "")
        alias = base
        code = (site["site_code"] or "").strip()
        sid = int(site["id"])
        if alias in alias_to_site_id and alias_to_site_id[alias] != sid:
            alias = f"{base}{code[-2:]}" if len(code) >= 2 else f"{base}{sid}"
        alias_to_site_id[alias] = sid
        result[sid] = alias
    return result


def migrate(conn: sqlite3.Connection, *, dry_run: bool) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    users = conn.execute(
        """
        SELECT u.id AS user_id, u.login_id, u.name, u.site_id, s.site_code, s.site_name, s.manager_name
        FROM users u
        JOIN sites s ON s.id = u.site_id
        WHERE u.role = 'SITE_FUNCTIONAL_EVAL' AND u.is_active = 1
        ORDER BY u.login_id
        """
    ).fetchall()

    site_ids = {int(u["site_id"]) for u in users}
    sites = conn.execute(
        f"SELECT id, site_code, site_name FROM sites WHERE id IN ({','.join('?' * len(site_ids))})",
        list(site_ids),
    ).fetchall() if site_ids else []
    alias_by_site = _ensure_unique_aliases(sites)

    stats = {"checked": 0, "updated_users": 0, "registry_upserted": 0, "skipped": 0, "conflicts": 0}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for row in users:
        stats["checked"] += 1
        site_alias = alias_by_site.get(int(row["site_id"]), derive_site_alias(row["site_name"] or ""))
        manager_name = (row["name"] or row["manager_name"] or "").strip()
        if not manager_name:
            stats["skipped"] += 1
            continue

        new_login = build_eval_login_id(site_alias, manager_name)
        old_login = row["login_id"]
        if not new_login or new_login == old_login:
            stats["skipped"] += 1
            continue

        conflict = conn.execute(
            "SELECT id FROM users WHERE login_id = ? AND id != ?",
            (new_login, row["user_id"]),
        ).fetchone()
        if conflict:
            stats["conflicts"] += 1
            print(f"CONFLICT {old_login} -> {new_login}")
            continue

        print(f"MIGRATE {old_login} ({manager_name}) -> {new_login} [site {row['site_code']}]")
        if dry_run:
            stats["updated_users"] += 1
            continue

        conn.execute("UPDATE users SET login_id = ?, updated_at = ? WHERE id = ?", (new_login, now, row["user_id"]))
        conn.execute(
            "UPDATE sites SET manager_name = ?, updated_at = ? WHERE id = ?",
            (manager_name, now, row["site_id"]),
        )

        site_code = row["site_code"]
        erp_label = normalize_erp_site_label(row["site_name"])
        reg = conn.execute(
            "SELECT id FROM functional_eval_site_registry WHERE site_code = ?",
            (site_code,),
        ).fetchone()
        if reg is None:
            conn.execute(
                """
                INSERT INTO functional_eval_site_registry
                (site_code, erp_site_label, site_alias, manager_name, manager_login_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (site_code, erp_label, site_alias, manager_name, new_login, now, now),
            )
            stats["registry_upserted"] += 1
        else:
            conn.execute(
                """
                UPDATE functional_eval_site_registry
                SET erp_site_label = ?, site_alias = ?, manager_name = ?, manager_login_id = ?, updated_at = ?
                WHERE site_code = ?
                """,
                (erp_label, site_alias, manager_name, new_login, now, site_code),
            )

        stats["updated_users"] += 1

    if not dry_run:
        conn.commit()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db", default=str(DB))
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    try:
        stats = migrate(conn, dry_run=args.dry_run)
        print("DONE", stats, "dry_run=", args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
