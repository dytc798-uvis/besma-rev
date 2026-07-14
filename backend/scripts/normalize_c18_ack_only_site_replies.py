"""Normalize generated C18 replies to acknowledgement-only HQ feedback.

Only generated SITE comment IDs are eligible.  Directly entered comments, the
two evidence-linked corrections, and replies to substantive HQ requests are
excluded.  Existing timestamps, authors, rows, and all non-comment data remain
unchanged.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


CONFIRM_TOKEN = "NORMALIZE_C18_ACK_ONLY_SITE_REPLIES"
SITE_CODE = "24025"
TARGET_COMMENT_IDS = tuple(range(18, 213)) + tuple(range(215, 281))
THANK_REPLIES = (
    "감사합니다.",
    "네, 감사합니다.",
    "확인해주셔서 감사합니다.",
    "네 감사합니다.",
)

TYPE_LABELS = (
    "TBM",
    "위험성평가",
    "수시위험성평가",
    "안전회의",
    "관리감독자 점검표",
    "소장점검표",
    "안전관리자 일지",
    "비상훈련 보고서",
    "MSDS 교육자료",
    "정기교육 자료",
    "특별교육 자료",
    "근로자 의견자료",
    "문서",
)


def _ack_only_feedbacks() -> set[str]:
    values = {
        "확인하였습니다. 감사합니다.",
        "확인했습니다.",
        "감사합니다.",
        "수고하셨습니다.",
        "HQ 승인",
    }
    for label in TYPE_LABELS:
        values.update(
            {
                f"{label} 확인했습니다.",
                f"{label} 내용 확인했습니다.",
                f"{label} 검토했습니다.",
                f"{label} 확인했습니다. 감사합니다.",
                f"{label} 검토 완료했습니다.",
                f"확인했습니다. {label} 내용 이상 없습니다.",
                f"수고하셨습니다. {label} 확인했습니다.",
            }
        )
    return values


ACK_ONLY_FEEDBACKS = _ack_only_feedbacks()


def _normalize(value: object) -> str:
    return " ".join(str(value or "").split())


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _feedback_turn(db: sqlite3.Connection, reply: sqlite3.Row) -> list[dict]:
    previous_site_at = db.execute(
        """
        SELECT MAX(created_at) FROM document_comments
        WHERE document_id = ? AND user_role = 'SITE' AND created_at < ?
        """,
        (reply["document_id"], reply["created_at"]),
    ).fetchone()[0]
    events: list[dict] = []
    approval_params: list[object] = [reply["document_id"], reply["created_at"]]
    approval_after = ""
    if previous_site_at is not None:
        approval_after = " AND action_at > ?"
        approval_params.append(previous_site_at)
    for row in db.execute(
        """
        SELECT id, action_at AS created_at, comment AS text
        FROM approval_histories
        WHERE document_id = ? AND action_at < ?
          AND comment IS NOT NULL AND TRIM(comment) != ''
        """
        + approval_after,
        approval_params,
    ).fetchall():
        events.append(
            {
                "source": "approval",
                "row_id": int(row["id"]),
                "created_at": str(row["created_at"]),
                "text": str(row["text"]),
            }
        )

    comment_params: list[object] = [reply["document_id"], reply["created_at"]]
    comment_after = ""
    if previous_site_at is not None:
        comment_after = " AND created_at > ?"
        comment_params.append(previous_site_at)
    for row in db.execute(
        """
        SELECT id, created_at, comment_text AS text
        FROM document_comments
        WHERE document_id = ? AND user_role != 'SITE' AND created_at < ?
        """
        + comment_after,
        comment_params,
    ).fetchall():
        events.append(
            {
                "source": "document_comment",
                "row_id": int(row["id"]),
                "created_at": str(row["created_at"]),
                "text": str(row["text"]),
            }
        )
    events.sort(key=lambda row: (row["created_at"], row["source"], row["row_id"]))
    return events


def build_plan(db: sqlite3.Connection, *, site_code: str) -> tuple[dict, list[dict]]:
    db.row_factory = sqlite3.Row
    site = db.execute("SELECT id, site_name FROM sites WHERE site_code = ?", (site_code,)).fetchone()
    if not site or "C18" not in str(site["site_name"]).upper() or "청라" not in str(site["site_name"]):
        raise RuntimeError(f"unexpected site: {site_code}")
    placeholders = ",".join("?" for _ in TARGET_COMMENT_IDS)
    replies = db.execute(
        f"""
        SELECT c.id, c.document_id, c.user_id, c.user_role, c.comment_text, c.created_at,
               u.name AS user_name
        FROM document_comments c
        JOIN documents d ON d.id = c.document_id
        JOIN users u ON u.id = c.user_id
        WHERE d.site_id = ? AND c.id IN ({placeholders}) AND c.user_role = 'SITE'
        ORDER BY c.id
        """,
        (int(site["id"]), *TARGET_COMMENT_IDS),
    ).fetchall()

    plans: list[dict] = []
    action_turn_count = 0
    no_feedback_ids: list[int] = []
    already_thanks_count = 0
    for reply in replies:
        feedback = _feedback_turn(db, reply)
        if not feedback:
            no_feedback_ids.append(int(reply["id"]))
            continue
        acknowledgement_only = all(_normalize(row["text"]) in ACK_ONLY_FEEDBACKS for row in feedback)
        if not acknowledgement_only:
            action_turn_count += 1
            continue
        if str(reply["comment_text"]) in THANK_REPLIES:
            already_thanks_count += 1
            continue
        new_text = THANK_REPLIES[(int(reply["id"]) * 17) % len(THANK_REPLIES)]
        plans.append(
            {
                "comment_id": int(reply["id"]),
                "document_id": int(reply["document_id"]),
                "user_id": int(reply["user_id"]),
                "user_name": str(reply["user_name"]),
                "created_at": str(reply["created_at"]),
                "old_text": str(reply["comment_text"]),
                "new_text": new_text,
                "feedback": feedback,
            }
        )

    meta = {
        "site_id": int(site["id"]),
        "site_name": site["site_name"],
        "eligible_generated_replies": len(replies),
        "planned_updates": len(plans),
        "action_request_replies_preserved": action_turn_count,
        "already_thanks_count": already_thanks_count,
        "no_feedback_ids": no_feedback_ids,
        "old_text_counts": dict(Counter(row["old_text"] for row in plans)),
        "new_text_counts": dict(Counter(row["new_text"] for row in plans)),
    }
    return meta, plans


def apply_plan(db: sqlite3.Connection, plans: list[dict]) -> None:
    counts_before = {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("documents", "approval_histories", "document_review_histories", "document_comments")
    }
    db.execute("BEGIN IMMEDIATE")
    try:
        for row in plans:
            cursor = db.execute(
                "UPDATE document_comments SET comment_text = ? WHERE id = ? AND comment_text = ?",
                (row["new_text"], row["comment_id"], row["old_text"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"reply changed concurrently: {row['comment_id']}")
        counts_after = {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("documents", "approval_histories", "document_review_histories", "document_comments")
        }
        if counts_before != counts_after:
            raise RuntimeError(f"row counts changed: {counts_before} != {counts_after}")
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
        default=Path("/home/ubuntu/besma-ops-backups/c18-ack-only-site-replies"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")

    db = sqlite3.connect(args.db, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        meta, plans = build_plan(db, site_code=args.site_code)
        print(json.dumps({"mode": "apply" if args.apply else "dry-run", **meta}, ensure_ascii=False, indent=2))
        for row in plans[-20:]:
            print(
                f"comment={row['comment_id']} doc={row['document_id']} {row['user_name']}\n"
                f"  feedback={row['feedback'][-1]['text']}\n"
                f"  old={row['old_text']}\n  new={row['new_text']}"
            )
        if not args.apply or not plans:
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_ack_reply_normalization_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_ack_reply_normalization_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        apply_plan(db, plans)
        after_meta, remaining = build_plan(db, site_code=args.site_code)
        if remaining:
            raise RuntimeError(f"post-apply plan is not empty: {after_meta}")
        manifest = {
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": str(args.db),
            "backup_db": str(backup_path),
            "before": meta,
            "after": after_meta,
            "updates": plans,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
