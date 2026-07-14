"""Backfill missing C18 site replies for HQ feedback dated from 2026-06-30.

The earlier manual-feedback reply operation intentionally excluded approval
comments created by the approval backfill.  This operation fills only that
remaining recent gap.  Existing comments are never modified or deleted.

Apply mode requires a confirmation token and writes a complete SQLite backup
and JSON manifest before inserting any reply.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


CONFIRM_TOKEN = "ADD_C18_RECENT_SITE_REPLIES"
SITE_CODE = "24025"
START_DATE = "2026-06-30"
MANAGER_DOCUMENT_TYPE = "SITE_MANAGER_CHECKLIST"
MANAGER_LOGIN = "site02"
MANAGER_NAME = "박명식"
SAFETY_MANAGER_LOGIN = "site03"
SAFETY_MANAGER_NAME = "박규철"
KST = timezone(timedelta(hours=9), name="KST")
EXPECTED_FEEDBACK_DOCUMENTS = 67
EXPECTED_EXISTING_REPLIES = 1
EXPECTED_MISSING_REPLIES = 66


GENERIC_REPLIES: dict[str, tuple[str, ...]] = {
    "DAILY_TBM": (
        "네 확인했습니다. TBM에 반영하겠습니다.",
        "확인했습니다. 작업 전 교육하겠습니다.",
        "그렇게 하겠습니다.",
    ),
    "DAILY_RISK_ASSESSMENT": (
        "확인했습니다. 위험성평가에 반영하겠습니다.",
        "네 확인했습니다. 필요한 부분은 조치하겠습니다.",
        "조치하겠습니다.",
    ),
    "DAILY_SAFETY_MEETING_LOG": (
        "네 확인했습니다.",
        "확인했습니다.",
        "그렇게 하겠습니다.",
    ),
    "SUPERVISOR_CHECKLIST": (
        "확인했습니다. 점검사항은 조치하겠습니다.",
        "네 확인했습니다. 작업 전에 다시 점검하겠습니다.",
        "조치하겠습니다.",
    ),
    "SITE_MANAGER_CHECKLIST": (
        "확인했습니다. 순회점검에 반영하겠습니다.",
        "네 확인했습니다. 현장 조치상태를 다시 보겠습니다.",
        "이미 조치하였습니다.",
    ),
    "SAFETY_MANAGER_DAILY_LOG": (
        "네 확인했습니다. 조치사항을 관리하겠습니다.",
        "확인했습니다. 필요한 부분은 처리하겠습니다.",
        "처리하겠습니다.",
    ),
    "REGULAR_EDUCATION": (
        "네 확인했습니다. 교육자료에 반영하겠습니다.",
        "확인했습니다. 교육 시 전달하겠습니다.",
    ),
}


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value)).replace(tzinfo=None)


def _is_lunch_kst(value: datetime) -> bool:
    local = value.replace(tzinfo=timezone.utc).astimezone(KST)
    minutes = local.hour * 60 + local.minute
    return 11 * 60 + 30 <= minutes < 13 * 60


def _reply_at(latest_feedback_at: datetime, document_id: int, document_type: str) -> datetime:
    if document_type == "DAILY_SAFETY_MEETING_LOG":
        delay = timedelta(minutes=6 + (document_id * 7) % 10)
    else:
        delays = (8, 12, 17, 24, 33, 41)
        delay = timedelta(minutes=delays[(document_id * 13) % len(delays)])
    candidate = latest_feedback_at + delay
    if _is_lunch_kst(candidate):
        local = candidate.replace(tzinfo=timezone.utc).astimezone(KST)
        local = local.replace(hour=13, minute=5 + document_id % 24, second=(document_id * 11) % 60)
        candidate = local.astimezone(timezone.utc).replace(tzinfo=None)
    if candidate <= latest_feedback_at or _is_lunch_kst(candidate):
        raise RuntimeError(f"invalid reply time for document {document_id}")
    return candidate


def _reply_text(document_type: str, feedback_text: str, approval_id: int) -> tuple[str, str]:
    compact = " ".join(feedback_text.split())
    if "2인 1조" in compact or "대차 사용" in compact:
        return "네 확인했습니다. 2인 1조와 대차 사용을 지키겠습니다.", "specific_feedback"
    if "고소작업대 내부 정리정돈" in compact:
        return "네 확인했습니다. 고소작업대 내부 정리정돈은 이미 조치하였습니다.", "specific_feedback"
    if "작업 전 점검" in compact and "유도자" in compact:
        return "확인했습니다. 작업 전 점검과 유도자 배치는 이미 조치하였습니다.", "specific_feedback"
    if "공도구" in compact and "정리정돈" in compact:
        return "네 확인했습니다. 공도구와 작업구간 정리정돈을 조치하겠습니다.", "specific_feedback"
    if "과상승" in compact:
        return "네 확인했습니다. 구획설정과 과상승 방지조치를 계속 확인하겠습니다.", "specific_feedback"
    if "추락·낙하" in compact or "추락, 낙하" in compact:
        return "네 확인했습니다. 작업 전 추락·낙하 방지대책을 재확인하겠습니다.", "specific_feedback"
    if "계속 확인" in compact or "계속 점검" in compact:
        return "네 확인했습니다. 계속 점검하겠습니다.", "specific_feedback"
    if "유지" in compact:
        return "확인했습니다. 해당 조치를 유지하겠습니다.", "specific_feedback"

    pool = GENERIC_REPLIES.get(
        document_type,
        ("네 확인했습니다.", "조치하겠습니다.", "처리하겠습니다.", "이미 조치하였습니다."),
    )
    return pool[(approval_id * 17) % len(pool)], "document_type_generic"


def _site_user(db: sqlite3.Connection, site_id: int, login_id: str, expected_name: str) -> sqlite3.Row:
    row = db.execute(
        """
        SELECT id, name, login_id, role, site_id, is_active
        FROM users WHERE login_id = ?
        """,
        (login_id,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"missing site user: {login_id}")
    actual = (row["name"], row["role"], int(row["site_id"] or 0), bool(row["is_active"]))
    expected = (expected_name, "SITE", site_id, True)
    if actual != expected:
        raise RuntimeError(f"site user mismatch for {login_id}: {actual} != {expected}")
    return row


def build_plan(db: sqlite3.Connection, *, site_code: str, start_date: str) -> tuple[dict, list[dict]]:
    db.row_factory = sqlite3.Row
    site = db.execute("SELECT id, site_name FROM sites WHERE site_code = ?", (site_code,)).fetchone()
    if not site or "C18" not in str(site["site_name"]).upper() or "청라" not in str(site["site_name"]):
        raise RuntimeError(f"unexpected site: {site_code}")
    site_id = int(site["id"])
    manager = _site_user(db, site_id, MANAGER_LOGIN, MANAGER_NAME)
    safety_manager = _site_user(db, site_id, SAFETY_MANAGER_LOGIN, SAFETY_MANAGER_NAME)

    feedback_rows = db.execute(
        """
        SELECT h.id AS approval_history_id, h.document_id, h.action_at, h.comment,
               d.instance_id, d.document_type, d.period_start
        FROM approval_histories h
        JOIN documents d ON d.id = h.document_id
        WHERE d.site_id = ? AND d.period_start >= ?
          AND h.comment IS NOT NULL AND TRIM(h.comment) != ''
          AND h.action_type IN ('APPROVE', 'REJECT')
        ORDER BY d.period_start, d.id, h.action_at, h.id
        """,
        (site_id, start_date),
    ).fetchall()
    document_ids = {int(row["document_id"]) for row in feedback_rows}
    if len(feedback_rows) != len(document_ids):
        raise RuntimeError("expected exactly one HQ approval feedback row per recent document")

    plans: list[dict] = []
    covered_document_ids: list[int] = []
    for row in feedback_rows:
        document_id = int(row["document_id"])
        if row["instance_id"] is None:
            raise RuntimeError(f"document {document_id} has no instance")
        feedback: list[tuple[str, int, str, datetime]] = [
            (
                "approval",
                int(row["approval_history_id"]),
                str(row["comment"]),
                _dt(row["action_at"]),
            )
        ]
        for comment in db.execute(
            """
            SELECT id, comment_text, created_at
            FROM document_comments
            WHERE document_id = ? AND user_role != 'SITE'
            ORDER BY created_at, id
            """,
            (document_id,),
        ).fetchall():
            feedback.append(
                ("document_comment", int(comment["id"]), str(comment["comment_text"]), _dt(comment["created_at"]))
            )
        latest_feedback_at = max(item[3] for item in feedback)
        existing = db.execute(
            """
            SELECT id FROM document_comments
            WHERE document_id = ? AND user_role = 'SITE' AND created_at > ?
            ORDER BY created_at, id LIMIT 1
            """,
            (document_id, latest_feedback_at.isoformat(sep=" ")),
        ).fetchone()
        if existing:
            covered_document_ids.append(document_id)
            continue

        document_type = str(row["document_type"])
        actor = manager if document_type == MANAGER_DOCUMENT_TYPE else safety_manager
        feedback_text = "\n".join(item[2] for item in feedback)
        reply_text, basis = _reply_text(document_type, feedback_text, int(row["approval_history_id"]))
        reply_at = _reply_at(latest_feedback_at, document_id, document_type)
        plans.append(
            {
                "document_id": document_id,
                "instance_id": int(row["instance_id"]),
                "document_type": document_type,
                "period_start": str(row["period_start"]),
                "approval_history_id": int(row["approval_history_id"]),
                "feedback": [
                    {"source": source, "row_id": row_id, "text": text, "created_at": created.isoformat(sep=" ")}
                    for source, row_id, text, created in feedback
                ],
                "latest_feedback_at": latest_feedback_at.isoformat(sep=" "),
                "reply_user_id": int(actor["id"]),
                "reply_user_login": str(actor["login_id"]),
                "reply_user_name": str(actor["name"]),
                "reply_text": reply_text,
                "reply_basis": basis,
                "reply_at": reply_at.isoformat(sep=" "),
            }
        )

    if len(feedback_rows) == EXPECTED_FEEDBACK_DOCUMENTS:
        if len(covered_document_ids) not in (EXPECTED_EXISTING_REPLIES, EXPECTED_FEEDBACK_DOCUMENTS):
            raise RuntimeError(f"unexpected covered count: {len(covered_document_ids)}")
        if plans and len(plans) != EXPECTED_MISSING_REPLIES:
            raise RuntimeError(f"unexpected missing reply count: {len(plans)}")
    meta = {
        "site_id": site_id,
        "site_name": site["site_name"],
        "start_date": start_date,
        "feedback_document_count": len(feedback_rows),
        "covered_document_count": len(covered_document_ids),
        "covered_document_ids": covered_document_ids,
        "planned_replies": len(plans),
        "reply_actor_counts": dict(Counter(plan["reply_user_name"] for plan in plans)),
        "reply_type_counts": dict(Counter(plan["document_type"] for plan in plans)),
        "reply_basis_counts": dict(Counter(plan["reply_basis"] for plan in plans)),
    }
    return meta, plans


def apply_plan(db: sqlite3.Connection, plans: list[dict]) -> list[int]:
    before_counts = {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("documents", "approval_histories", "document_review_histories", "document_comments")
    }
    created_ids: list[int] = []
    db.execute("BEGIN IMMEDIATE")
    try:
        for plan in plans:
            duplicate = db.execute(
                """
                SELECT id FROM document_comments
                WHERE document_id = ? AND user_role = 'SITE' AND created_at > ?
                LIMIT 1
                """,
                (plan["document_id"], plan["latest_feedback_at"]),
            ).fetchone()
            if duplicate:
                raise RuntimeError(f"reply appeared after planning for document {plan['document_id']}")
            cursor = db.execute(
                """
                INSERT INTO document_comments (
                    document_id, instance_id, user_id, user_role, comment_text, created_at
                ) VALUES (?, ?, ?, 'SITE', ?, ?)
                """,
                (
                    plan["document_id"],
                    plan["instance_id"],
                    plan["reply_user_id"],
                    plan["reply_text"],
                    plan["reply_at"],
                ),
            )
            created_ids.append(int(cursor.lastrowid))

        after_counts = {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("documents", "approval_histories", "document_review_histories", "document_comments")
        }
        expected = dict(before_counts)
        expected["document_comments"] += len(plans)
        if after_counts != expected:
            raise RuntimeError(f"row counts mismatch: {after_counts} != {expected}")
        db.commit()
        return created_ids
    except Exception:
        db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/home/ubuntu/besma-rev/database/besma.db"))
    parser.add_argument("--site-code", default=SITE_CODE)
    parser.add_argument("--start-date", default=START_DATE)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path("/home/ubuntu/besma-ops-backups/c18-recent-site-replies"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")

    db = sqlite3.connect(args.db, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        meta, plans = build_plan(db, site_code=args.site_code, start_date=args.start_date)
        print(json.dumps({"mode": "apply" if args.apply else "dry-run", **meta}, ensure_ascii=False, indent=2))
        for plan in plans[-18:]:
            print(
                f"doc={plan['document_id']} {plan['period_start']} {plan['document_type']} "
                f"actor={plan['reply_user_name']} at={plan['reply_at']} basis={plan['reply_basis']}\n"
                f"  feedback={plan['feedback'][-1]['text']}\n  reply={plan['reply_text']}"
            )
        if not args.apply or not plans:
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_recent_site_replies_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_recent_site_replies_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        created_ids = apply_plan(db, plans)
        after_meta, remaining = build_plan(db, site_code=args.site_code, start_date=args.start_date)
        if remaining or after_meta["covered_document_count"] != EXPECTED_FEEDBACK_DOCUMENTS:
            raise RuntimeError(f"post-apply coverage failed: {after_meta}")
        manifest = {
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": str(args.db),
            "backup_db": str(backup_path),
            "created_comment_ids": created_ids,
            "before": meta,
            "after": after_meta,
            "plans": plans,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        print(f"created_comment_ids={created_ids}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
