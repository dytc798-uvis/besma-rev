"""Repair C18 risk-library demo duplicates and worker-voice test rows.

Dry-run is the default.  Apply requires an explicit confirmation token and
creates a full SQLite backup plus a JSON manifest before changing production
data.  Referenced risk-library rows are preserved; duplicate demo items are
only made inactive.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


CONFIRM_TOKEN = "REPAIR_C18_RISK_LIBRARY_WORKER_VOICE"
SITE_CODE = "24025"
TEST_OPINION_IDS = (5, 6)
DEMO_RISK_FACTORS = (
    "충전부 접촉에 의한 감전",
    "전선 피복 손상에 의한 누전·화재",
    "중량물 취급 시 협착·끼임",
    "사다리 전도에 의한 추락",
    "공구·자재 낙하에 의한 타격",
)


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _placeholders(values: tuple[object, ...] | list[object]) -> str:
    return ",".join("?" for _ in values)


def build_plan(db: sqlite3.Connection, *, site_code: str) -> dict:
    db.row_factory = sqlite3.Row
    site = db.execute(
        "SELECT id, site_name FROM sites WHERE site_code = ?", (site_code,)
    ).fetchone()
    if not site or "C18" not in str(site["site_name"]).upper() or "청라" not in str(site["site_name"]):
        raise RuntimeError(f"unexpected site: {site_code}")

    test_rows = [
        dict(row)
        for row in db.execute(
            f"""
            SELECT i.id, i.ledger_id, i.row_no, i.opinion_text
            FROM worker_voice_items i
            JOIN worker_voice_ledgers l ON l.id = i.ledger_id
            WHERE l.site_id = ? AND i.id IN ({_placeholders(TEST_OPINION_IDS)})
              AND i.opinion_text LIKE 'deploy worker voice %'
            ORDER BY i.id
            """,
            (int(site["id"]), *TEST_OPINION_IDS),
        ).fetchall()
    ]
    found_test_ids = [row["id"] for row in test_rows]
    if found_test_ids and found_test_ids != list(TEST_OPINION_IDS):
        raise RuntimeError(f"worker-voice test rows are only partially present: {test_rows}")
    test_comment_count = int(
        db.execute(
            f"SELECT COUNT(*) FROM worker_voice_comments WHERE item_id IN ({_placeholders(TEST_OPINION_IDS)})",
            TEST_OPINION_IDS,
        ).fetchone()[0]
    )
    if test_comment_count:
        raise RuntimeError("test worker-voice rows unexpectedly have comments")

    risk_rows = db.execute(
        f"""
        SELECT r.id AS revision_id, r.item_id, r.risk_factor, r.countermeasure
        FROM risk_library_item_revisions r
        JOIN risk_library_items i ON i.id = r.item_id
        WHERE i.is_active = 1 AND r.is_current = 1 AND r.source_file IS NULL
          AND r.risk_factor IN ({_placeholders(DEMO_RISK_FACTORS)})
        ORDER BY lower(trim(r.risk_factor)), lower(trim(r.countermeasure)), r.id
        """,
        DEMO_RISK_FACTORS,
    ).fetchall()
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in risk_rows:
        key = (str(row["risk_factor"]).strip().lower(), str(row["countermeasure"]).strip().lower())
        groups.setdefault(key, []).append(row)

    risk_duplicate_groups: list[dict] = []
    deactivate_item_ids: list[int] = []
    for rows in groups.values():
        if len(rows) < 2:
            continue
        keep = rows[0]
        duplicates = rows[1:]
        deactivate_item_ids.extend(int(row["item_id"]) for row in duplicates)
        risk_duplicate_groups.append(
            {
                "risk_factor": keep["risk_factor"],
                "countermeasure": keep["countermeasure"],
                "keep_revision_id": int(keep["revision_id"]),
                "keep_item_id": int(keep["item_id"]),
                "deactivate_revision_ids": [int(row["revision_id"]) for row in duplicates],
                "deactivate_item_ids": [int(row["item_id"]) for row in duplicates],
            }
        )

    legacy_rows = [
        dict(row)
        for row in db.execute(
            """
            SELECT i.id, i.site_approved_by_user_id, i.site_approved_at,
                   i.receipt_decision, i.risk_db_request_status, i.risk_db_hq_status
            FROM worker_voice_items i
            JOIN worker_voice_ledgers l ON l.id = i.ledger_id
            WHERE l.site_id = ? AND i.site_approved = 1 AND i.site_rejected = 0
              AND i.receipt_decision = 'pending'
              AND i.risk_db_request_status = 'pending'
              AND i.risk_db_hq_status = 'pending'
            ORDER BY i.id
            """,
            (int(site["id"]),),
        ).fetchall()
    ]

    counts = {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in (
            "risk_library_items",
            "risk_library_item_revisions",
            "worker_voice_ledgers",
            "worker_voice_items",
            "worker_voice_comments",
        )
    }
    return {
        "site_id": int(site["id"]),
        "site_name": str(site["site_name"]),
        "test_worker_voice_rows_to_delete": test_rows,
        "risk_duplicate_groups": risk_duplicate_groups,
        "risk_items_to_deactivate": sorted(deactivate_item_ids),
        "legacy_worker_voice_rows_to_normalize": legacy_rows,
        "counts": counts,
    }


def apply_plan(db: sqlite3.Connection, plan: dict) -> None:
    test_ids = [int(row["id"]) for row in plan["test_worker_voice_rows_to_delete"]]
    risk_item_ids = [int(value) for value in plan["risk_items_to_deactivate"]]
    legacy_ids = [int(row["id"]) for row in plan["legacy_worker_voice_rows_to_normalize"]]
    before = plan["counts"]

    db.execute("BEGIN IMMEDIATE")
    try:
        if test_ids:
            deleted = db.execute(
                f"DELETE FROM worker_voice_items WHERE id IN ({_placeholders(test_ids)})",
                test_ids,
            ).rowcount
            if deleted != len(test_ids):
                raise RuntimeError(f"worker-voice delete mismatch: {deleted} != {len(test_ids)}")

        if risk_item_ids:
            deactivated = db.execute(
                f"UPDATE risk_library_items SET is_active = 0 WHERE id IN ({_placeholders(risk_item_ids)}) AND is_active = 1",
                risk_item_ids,
            ).rowcount
            if deactivated != len(risk_item_ids):
                raise RuntimeError(f"risk deactivation mismatch: {deactivated} != {len(risk_item_ids)}")

        if legacy_ids:
            normalized = db.execute(
                f"""
                UPDATE worker_voice_items
                SET receipt_decision = 'accepted',
                    risk_db_request_status = 'requested',
                    risk_db_requested_at = COALESCE(site_approved_at, updated_at, created_at),
                    risk_db_requested_by_user_id = site_approved_by_user_id
                WHERE id IN ({_placeholders(legacy_ids)})
                  AND site_approved = 1 AND site_rejected = 0
                  AND receipt_decision = 'pending' AND risk_db_request_status = 'pending'
                """,
                legacy_ids,
            ).rowcount
            if normalized != len(legacy_ids):
                raise RuntimeError(f"legacy normalization mismatch: {normalized} != {len(legacy_ids)}")

        after = {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in before
        }
        expected = dict(before)
        expected["worker_voice_items"] -= len(test_ids)
        if after != expected:
            raise RuntimeError(f"unexpected row-count change: {after} != {expected}")
        db.commit()
    except Exception:
        db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/home/ubuntu/besma-rev/database/besma.db"))
    parser.add_argument("--site-code", default=SITE_CODE)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path("/home/ubuntu/besma-ops-backups/c18-risk-library-worker-voice"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")

    db = sqlite3.connect(args.db, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        plan = build_plan(db, site_code=args.site_code)
        print(json.dumps({"mode": "apply" if args.apply else "dry-run", **plan}, ensure_ascii=False, indent=2))
        if not args.apply:
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_risk_worker_voice_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_risk_worker_voice_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        apply_plan(db, plan)
        post = build_plan(db, site_code=args.site_code)
        if post["test_worker_voice_rows_to_delete"]:
            raise RuntimeError("test worker-voice rows remain after apply")
        if post["risk_items_to_deactivate"]:
            raise RuntimeError("active duplicate demo risks remain after apply")
        if post["legacy_worker_voice_rows_to_normalize"]:
            raise RuntimeError("legacy worker-voice status rows remain after apply")
        manifest = {
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": str(args.db),
            "backup_db": str(backup_path),
            "before": plan,
            "after": post,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
