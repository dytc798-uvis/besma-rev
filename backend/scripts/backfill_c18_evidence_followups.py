"""Add current-time, system-labelled C18 implementation evidence notes.

This does not impersonate a site worker and does not backdate comments. The two
links below are limited to next-day checklists whose result columns explicitly
show the same requested control measures as implemented/maintained.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


CONFIRM_TOKEN = "ADD_C18_EVIDENCE_FOLLOWUPS"
SYSTEM_LOGIN_ID = "system-c18-evidence"
SYSTEM_NAME = "이행확인(문서근거)"

EVIDENCE_LINKS = (
    {
        "source_document_id": 360,
        "evidence_document_id": 365,
        "source_type": "SUPERVISOR_CHECKLIST",
        "source_date": "2026-07-10",
        "evidence_type": "SUPERVISOR_CHECKLIST",
        "evidence_date": "2026-07-11",
        "comment": (
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
        "comment": (
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


def _validate_link(db: sqlite3.Connection, link: dict) -> tuple[int, int]:
    source = db.execute(
        "SELECT id, instance_id, document_type, period_start, site_id FROM documents WHERE id = ?",
        (link["source_document_id"],),
    ).fetchone()
    evidence = db.execute(
        "SELECT id, document_type, period_start, site_id FROM documents WHERE id = ?",
        (link["evidence_document_id"],),
    ).fetchone()
    if not source or not evidence:
        raise RuntimeError(f"missing source/evidence document: {link}")
    actual_source = (source["document_type"], str(source["period_start"]))
    expected_source = (link["source_type"], link["source_date"])
    actual_evidence = (evidence["document_type"], str(evidence["period_start"]))
    expected_evidence = (link["evidence_type"], link["evidence_date"])
    if actual_source != expected_source:
        raise RuntimeError(f"source mismatch: {actual_source} != {expected_source}")
    if actual_evidence != expected_evidence:
        raise RuntimeError(f"evidence mismatch: {actual_evidence} != {expected_evidence}")
    if int(source["site_id"]) != int(evidence["site_id"]):
        raise RuntimeError("source and evidence site differ")
    return int(source["instance_id"]) if source["instance_id"] is not None else 0, int(source["site_id"])


def build_plan(db: sqlite3.Connection) -> list[dict]:
    db.row_factory = sqlite3.Row
    plan = []
    for link in EVIDENCE_LINKS:
        instance_id, site_id = _validate_link(db, link)
        existing = db.execute(
            """
            SELECT c.id
            FROM document_comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.document_id = ? AND u.login_id = ? AND c.comment_text = ?
            """,
            (link["source_document_id"], SYSTEM_LOGIN_ID, link["comment"]),
        ).fetchone()
        if not existing:
            plan.append({**link, "instance_id": instance_id or None, "site_id": site_id})
    return plan


def _ensure_system_user(db: sqlite3.Connection, now: str) -> int:
    row = db.execute(
        "SELECT id, name, is_active FROM users WHERE login_id = ?", (SYSTEM_LOGIN_ID,)
    ).fetchone()
    if row:
        if row["name"] != SYSTEM_NAME or bool(row["is_active"]):
            raise RuntimeError("system evidence user exists with unexpected attributes")
        return int(row["id"])
    cursor = db.execute(
        """
        INSERT INTO users (
            name, login_id, password_hash, department, role, ui_type, site_id,
            is_active, map_preference, must_change_password, initial_password_issued,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, 0, ?, 0, 0, ?, ?)
        """,
        (
            SYSTEM_NAME,
            SYSTEM_LOGIN_ID,
            "DISABLED_SYSTEM_ACCOUNT",
            "SYSTEM",
            "HQ_SAFE",
            "HQ_SAFE",
            "NAVER",
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def apply_plan(db: sqlite3.Connection, plan: list[dict]) -> list[int]:
    now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")
    db.execute("BEGIN IMMEDIATE")
    inserted_ids: list[int] = []
    try:
        system_user_id = _ensure_system_user(db, now)
        for item in plan:
            cursor = db.execute(
                """
                INSERT INTO document_comments (
                    document_id, instance_id, user_id, user_role, comment_text, created_at
                ) VALUES (?, ?, ?, 'HQ', ?, ?)
                """,
                (
                    item["source_document_id"],
                    item["instance_id"],
                    system_user_id,
                    item["comment"],
                    now,
                ),
            )
            inserted_ids.append(int(cursor.lastrowid))
        db.commit()
        return inserted_ids
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
        print(
            json.dumps(
                {
                    "mode": "apply" if args.apply else "dry-run",
                    "planned_inserts": len(plan),
                    "links": plan,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        if not args.apply or not plan:
            return 0
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_evidence_followups_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_evidence_followups_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        inserted_ids = apply_plan(db, plan)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                    "database": str(args.db),
                    "backup_db": str(backup_path),
                    "inserted_comment_ids": inserted_ids,
                    "links": plan,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        print(f"inserted_comment_ids={inserted_ids}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
