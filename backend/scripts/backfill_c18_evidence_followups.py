"""Reconcile two C18 follow-up comments with the documented communication.

The displayed event time is taken from an existing 2026-07-11 database event:
the site uploader's next-day checklist upload or HQ's next-day approval.  A full
SQLite backup and manifest preserve when this corrective reconciliation ran.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


CONFIRM_TOKEN = "RECONCILE_C18_FOLLOWUPS"
LEGACY_SYSTEM_LOGIN_ID = "system-c18-evidence"

FOLLOWUPS = (
    {
        "source_document_id": 360,
        "evidence_document_id": 365,
        "source_type": "SUPERVISOR_CHECKLIST",
        "source_date": "2026-07-10",
        "evidence_type": "SUPERVISOR_CHECKLIST",
        "evidence_date": "2026-07-11",
        "actor_id": 13,
        "actor_login_id": "site03",
        "actor_name": "박규철",
        "user_role": "SITE",
        "time_source": "evidence_upload",
        "comment": "확인하였습니다. 작업전 점검하였고, 유도자 배치한 것을 소장님이 점검하셨습니다.",
        "legacy_comment": (
            "이행확인(문서근거): 2026-07-11 관리감독자 점검표의 점검 결과에서 "
            "고소작업대 사용 전 점검, 작업구간 구획설정 및 유도자 배치가 확인되었습니다. "
            "(근거 문서 #365)"
        ),
    },
    {
        "source_document_id": 361,
        "evidence_document_id": 364,
        "source_type": "SITE_MANAGER_CHECKLIST",
        "source_date": "2026-07-10",
        "evidence_type": "SITE_MANAGER_CHECKLIST",
        "evidence_date": "2026-07-11",
        "actor_id": 8,
        "actor_login_id": "hq01",
        "actor_name": "정상익",
        "user_role": "HQ",
        "time_source": "evidence_approval",
        "comment": "순회점검표 확인하였습니다. 감사합니다.",
        "legacy_comment": (
            "이행확인(문서근거): 2026-07-11 소장 순회점검표의 점검 결과에서 "
            "고소작업대 작업 전 점검, 구획설정 및 유도자 배치 상태가 확인되었습니다. "
            "(근거 문서 #364)"
        ),
    },
)


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _validate_actor(db: sqlite3.Connection, item: dict) -> None:
    actor = db.execute(
        "SELECT id, name, login_id, is_active FROM users WHERE id = ?",
        (item["actor_id"],),
    ).fetchone()
    if not actor:
        raise RuntimeError(f"missing actor: {item['actor_id']}")
    actual = (actor["login_id"], actor["name"], bool(actor["is_active"]))
    expected = (item["actor_login_id"], item["actor_name"], True)
    if actual != expected:
        raise RuntimeError(f"actor mismatch: {actual} != {expected}")


def _validate_documents(db: sqlite3.Connection, item: dict) -> tuple[int | None, int, sqlite3.Row]:
    source = db.execute(
        """
        SELECT id, instance_id, document_type, period_start, site_id
        FROM documents WHERE id = ?
        """,
        (item["source_document_id"],),
    ).fetchone()
    evidence = db.execute(
        """
        SELECT id, document_type, period_start, site_id, uploaded_by_user_id, uploaded_at
        FROM documents WHERE id = ?
        """,
        (item["evidence_document_id"],),
    ).fetchone()
    if not source or not evidence:
        raise RuntimeError(f"missing source/evidence document: {item}")
    actual_source = (source["document_type"], str(source["period_start"]))
    expected_source = (item["source_type"], item["source_date"])
    actual_evidence = (evidence["document_type"], str(evidence["period_start"]))
    expected_evidence = (item["evidence_type"], item["evidence_date"])
    if actual_source != expected_source:
        raise RuntimeError(f"source mismatch: {actual_source} != {expected_source}")
    if actual_evidence != expected_evidence:
        raise RuntimeError(f"evidence mismatch: {actual_evidence} != {expected_evidence}")
    if int(source["site_id"]) != int(evidence["site_id"]):
        raise RuntimeError("source and evidence site differ")
    instance_id = int(source["instance_id"]) if source["instance_id"] is not None else None
    return instance_id, int(source["site_id"]), evidence


def _documented_event_time(db: sqlite3.Connection, item: dict, evidence: sqlite3.Row) -> str:
    if item["time_source"] == "evidence_upload":
        if int(evidence["uploaded_by_user_id"] or 0) != int(item["actor_id"]):
            raise RuntimeError("evidence uploader does not match the requested site actor")
        if not evidence["uploaded_at"]:
            raise RuntimeError("evidence upload time is missing")
        return str(evidence["uploaded_at"])

    if item["time_source"] == "evidence_approval":
        rows = db.execute(
            """
            SELECT action_at
            FROM approval_histories
            WHERE document_id = ? AND action_by_user_id = ? AND action_type = 'APPROVE'
            ORDER BY action_at
            """,
            (item["evidence_document_id"], item["actor_id"]),
        ).fetchall()
        if len(rows) != 1:
            raise RuntimeError(f"expected one documented evidence approval, found {len(rows)}")
        return str(rows[0]["action_at"])

    raise RuntimeError(f"unknown time source: {item['time_source']}")


def build_plan(db: sqlite3.Connection) -> list[dict]:
    db.row_factory = sqlite3.Row
    plan: list[dict] = []
    for item in FOLLOWUPS:
        _validate_actor(db, item)
        instance_id, site_id, evidence = _validate_documents(db, item)
        event_at = _documented_event_time(db, item, evidence)

        exact = db.execute(
            """
            SELECT id FROM document_comments
            WHERE document_id = ? AND instance_id IS ? AND user_id = ?
              AND user_role = ? AND comment_text = ? AND created_at = ?
            """,
            (
                item["source_document_id"],
                instance_id,
                item["actor_id"],
                item["user_role"],
                item["comment"],
                event_at,
            ),
        ).fetchone()
        if exact:
            continue

        legacy = db.execute(
            """
            SELECT c.id, c.created_at
            FROM document_comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.document_id = ? AND u.login_id = ? AND c.comment_text = ?
            ORDER BY c.id
            """,
            (item["source_document_id"], LEGACY_SYSTEM_LOGIN_ID, item["legacy_comment"]),
        ).fetchall()
        if len(legacy) > 1:
            raise RuntimeError(f"multiple legacy comments found for document {item['source_document_id']}")
        action = "update" if legacy else "insert"
        plan.append(
            {
                **item,
                "action": action,
                "comment_id": int(legacy[0]["id"]) if legacy else None,
                "previous_created_at": str(legacy[0]["created_at"]) if legacy else None,
                "instance_id": instance_id,
                "site_id": site_id,
                "event_at": event_at,
            }
        )
    return plan


def apply_plan(db: sqlite3.Connection, plan: list[dict]) -> dict[str, list[int]]:
    db.execute("BEGIN IMMEDIATE")
    updated_ids: list[int] = []
    inserted_ids: list[int] = []
    try:
        for item in plan:
            if item["action"] == "update":
                cursor = db.execute(
                    """
                    UPDATE document_comments
                    SET instance_id = ?, user_id = ?, user_role = ?, comment_text = ?, created_at = ?
                    WHERE id = ?
                    """,
                    (
                        item["instance_id"],
                        item["actor_id"],
                        item["user_role"],
                        item["comment"],
                        item["event_at"],
                        item["comment_id"],
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"comment update failed: {item['comment_id']}")
                updated_ids.append(int(item["comment_id"]))
            else:
                cursor = db.execute(
                    """
                    INSERT INTO document_comments (
                        document_id, instance_id, user_id, user_role, comment_text, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["source_document_id"],
                        item["instance_id"],
                        item["actor_id"],
                        item["user_role"],
                        item["comment"],
                        item["event_at"],
                    ),
                )
                inserted_ids.append(int(cursor.lastrowid))
        db.commit()
        return {"updated_ids": updated_ids, "inserted_ids": inserted_ids}
    except Exception:
        db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/home/ubuntu/besma-rev/database/besma.db"))
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path("/home/ubuntu/besma-ops-backups/c18-evidence-followups"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")

    db = sqlite3.connect(args.db, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        plan = build_plan(db)
        summary = {
            "mode": "apply" if args.apply else "dry-run",
            "planned_updates": sum(item["action"] == "update" for item in plan),
            "planned_inserts": sum(item["action"] == "insert" for item in plan),
            "followups": plan,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        if not args.apply or not plan:
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_followup_reconcile_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_followup_reconcile_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        result = apply_plan(db, plan)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                    "database": str(args.db),
                    "backup_db": str(backup_path),
                    **result,
                    "followups": plan,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
