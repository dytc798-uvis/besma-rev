"""Reconcile C18 safety-meeting communication authors and event times.

Rules implemented for DAILY_SAFETY_MEETING_LOG only:
- the communication date is the document period date;
- HQ review starts after 16:30 KST and normally stays within 16:30-17:00;
- a late upload or a multi-message exchange may move the last event slightly past 17:00;
- every site reply follows all HQ feedback for the same document;
- pre-backfill authors are preserved;
- a generated approval author is corrected only when the pre-backfill database
  has unambiguous same-day HQ activity by a different named user.

No row is inserted or deleted.  Apply mode requires a confirmation token and
creates a full SQLite backup plus a JSON manifest before changing data.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


CONFIRM_TOKEN = "RECONCILE_C18_SAFETY_MEETING_COMMUNICATIONS"
SAFETY_MEETING_TYPE = "DAILY_SAFETY_MEETING_LOG"
KST_OFFSET = timedelta(hours=9)
MEETING_COMMENT_START_UTC = time(7, 30)  # 16:30 KST


def _backup_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)


def _dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value)).replace(tzinfo=None)


def _same(value: object, target: datetime) -> bool:
    return _dt(value) == target


def _site(db: sqlite3.Connection, site_code: str) -> sqlite3.Row:
    row = db.execute("SELECT id, site_code, site_name FROM sites WHERE site_code = ?", (site_code,)).fetchone()
    if not row:
        raise RuntimeError(f"site not found: {site_code}")
    return row


def _baseline_actor_evidence(
    baseline: sqlite3.Connection,
    *,
    site_id: int,
    work_date: str,
) -> Counter[int]:
    counts: Counter[int] = Counter()
    for row in baseline.execute(
        """
        SELECT h.action_by_user_id AS user_id, COUNT(*) AS n
        FROM approval_histories h
        JOIN documents d ON d.id = h.document_id
        JOIN users u ON u.id = h.action_by_user_id
        WHERE d.site_id = ?
          AND u.role != 'SITE'
          AND date(h.action_at, '+9 hours') = ?
        GROUP BY h.action_by_user_id
        """,
        (site_id, work_date),
    ).fetchall():
        counts[int(row["user_id"])] += int(row["n"])
    for row in baseline.execute(
        """
        SELECT c.user_id, COUNT(*) AS n
        FROM document_comments c
        JOIN documents d ON d.id = c.document_id
        JOIN users u ON u.id = c.user_id
        WHERE d.site_id = ?
          AND u.role != 'SITE'
          AND date(c.created_at, '+9 hours') = ?
        GROUP BY c.user_id
        """,
        (site_id, work_date),
    ).fetchall():
        counts[int(row["user_id"])] += int(row["n"])
    return counts


def _evidence_actor(
    baseline: sqlite3.Connection,
    *,
    site_id: int,
    work_date: str,
    current_actor_id: int,
) -> tuple[int, str]:
    counts = _baseline_actor_evidence(baseline, site_id=site_id, work_date=work_date)
    if not counts:
        return current_actor_id, "no_same_day_baseline_actor"
    ranked = counts.most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return current_actor_id, "ambiguous_same_day_baseline_actor"
    return int(ranked[0][0]), "same_day_baseline_activity"


def _document_start(document_id: int, work_date: date, uploaded_at: object | None) -> datetime:
    # Stable per-document variation: 16:30-16:50 KST for normal uploads.
    target = datetime.combine(work_date, MEETING_COMMENT_START_UTC) + timedelta(
        minutes=(document_id * 11) % 21,
        seconds=(document_id * 17) % 50,
    )
    if uploaded_at is not None:
        uploaded = _dt(uploaded_at)
        minimum_after_upload = uploaded + timedelta(minutes=2 + (document_id % 3))
        if minimum_after_upload > target:
            target = minimum_after_upload
    return target


def _review_history_for_approval(
    db: sqlite3.Connection,
    *,
    document_id: int,
    action_type: str,
    comment: object,
) -> sqlite3.Row | None:
    rows = db.execute(
        """
        SELECT id, action_by_user_id, action_at
        FROM document_review_histories
        WHERE document_id = ? AND action_type = ? AND COALESCE(comment, '') = COALESCE(?, '')
        ORDER BY id
        """,
        (document_id, action_type, comment),
    ).fetchall()
    if len(rows) > 1:
        raise RuntimeError(f"multiple matching review histories for document {document_id}")
    return rows[0] if rows else None


def build_plan(
    db: sqlite3.Connection,
    baseline: sqlite3.Connection,
    *,
    site_code: str,
) -> tuple[dict, list[dict], list[dict], list[dict]]:
    db.row_factory = sqlite3.Row
    baseline.row_factory = sqlite3.Row
    site = _site(db, site_code)
    site_id = int(site["id"])
    baseline_site = _site(baseline, site_code)
    if int(baseline_site["id"]) != site_id:
        raise RuntimeError("baseline site id differs")

    baseline_approval_ids = {
        int(row["id"]) for row in baseline.execute("SELECT id FROM approval_histories").fetchall()
    }
    documents = db.execute(
        """
        SELECT id, period_start, uploaded_at, reviewed_at
        FROM documents
        WHERE site_id = ? AND document_type = ?
        ORDER BY period_start, id
        """,
        (site_id, SAFETY_MEETING_TYPE),
    ).fetchall()

    approval_updates: list[dict] = []
    comment_updates: list[dict] = []
    document_updates: list[dict] = []
    actor_changes: list[dict] = []
    actor_counts_before: Counter[str] = Counter()
    actor_counts_after: Counter[str] = Counter()

    for document in documents:
        document_id = int(document["id"])
        work_date = date.fromisoformat(str(document["period_start"]))
        work_date_text = work_date.isoformat()
        cursor = _document_start(document_id, work_date, document["uploaded_at"])

        approvals = db.execute(
            """
            SELECT h.id, h.action_by_user_id, h.action_type, h.comment, h.action_at,
                   u.name AS actor_name, u.login_id AS actor_login_id
            FROM approval_histories h
            JOIN users u ON u.id = h.action_by_user_id
            WHERE h.document_id = ? AND h.comment IS NOT NULL AND TRIM(h.comment) != ''
            ORDER BY h.id
            """,
            (document_id,),
        ).fetchall()
        latest_approval_target: datetime | None = None
        for index, approval in enumerate(approvals):
            current_actor_id = int(approval["action_by_user_id"])
            target_actor_id = current_actor_id
            actor_reason = "pre_backfill_actor_preserved"
            if int(approval["id"]) not in baseline_approval_ids:
                target_actor_id, actor_reason = _evidence_actor(
                    baseline,
                    site_id=site_id,
                    work_date=work_date_text,
                    current_actor_id=current_actor_id,
                )
            target_actor = db.execute(
                "SELECT id, name, login_id, is_active FROM users WHERE id = ?", (target_actor_id,)
            ).fetchone()
            if not target_actor or not bool(target_actor["is_active"]):
                raise RuntimeError(f"invalid target actor: {target_actor_id}")

            target_at = cursor + timedelta(minutes=index * 4)
            latest_approval_target = target_at
            review = _review_history_for_approval(
                db,
                document_id=document_id,
                action_type=str(approval["action_type"]),
                comment=approval["comment"],
            )
            review_needs_update = bool(
                review
                and (
                    int(review["action_by_user_id"]) != target_actor_id
                    or not _same(review["action_at"], target_at)
                )
            )
            needs_update = (
                current_actor_id != target_actor_id
                or not _same(approval["action_at"], target_at)
                or review_needs_update
            )
            actor_counts_before[str(approval["actor_name"])] += 1
            actor_counts_after[str(target_actor["name"])] += 1
            if current_actor_id != target_actor_id:
                actor_changes.append(
                    {
                        "approval_history_id": int(approval["id"]),
                        "document_id": document_id,
                        "work_date": work_date_text,
                        "old_actor_id": current_actor_id,
                        "old_actor_name": approval["actor_name"],
                        "new_actor_id": target_actor_id,
                        "new_actor_name": target_actor["name"],
                        "reason": actor_reason,
                    }
                )
            if needs_update:
                approval_updates.append(
                    {
                        "approval_history_id": int(approval["id"]),
                        "document_id": document_id,
                        "work_date": work_date_text,
                        "old_actor_id": current_actor_id,
                        "new_actor_id": target_actor_id,
                        "old_actor_name": approval["actor_name"],
                        "new_actor_name": target_actor["name"],
                        "old_action_at": str(approval["action_at"]),
                        "new_action_at": target_at.isoformat(sep=" "),
                        "review_history_id": int(review["id"]) if review else None,
                        "old_review_actor_id": int(review["action_by_user_id"]) if review else None,
                        "old_review_action_at": str(review["action_at"]) if review else None,
                        "comment": approval["comment"],
                        "actor_reason": actor_reason,
                    }
                )
        if approvals:
            cursor = (latest_approval_target or cursor) + timedelta(minutes=4)

        comments = db.execute(
            """
            SELECT c.id, c.user_id, c.user_role, c.created_at, c.comment_text, u.name
            FROM document_comments c
            JOIN users u ON u.id = c.user_id
            WHERE c.document_id = ?
            ORDER BY c.id
            """,
            (document_id,),
        ).fetchall()
        hq_comments = [row for row in comments if str(row["user_role"]) != "SITE"]
        site_comments = [row for row in comments if str(row["user_role"]) == "SITE"]
        for row in hq_comments:
            target_at = cursor
            cursor += timedelta(minutes=4)
            if not _same(row["created_at"], target_at):
                comment_updates.append(
                    {
                        "comment_id": int(row["id"]),
                        "document_id": document_id,
                        "work_date": work_date_text,
                        "user_id": int(row["user_id"]),
                        "user_name": row["name"],
                        "user_role": row["user_role"],
                        "old_created_at": str(row["created_at"]),
                        "new_created_at": target_at.isoformat(sep=" "),
                        "comment_text": row["comment_text"],
                    }
                )
        if site_comments:
            cursor += timedelta(minutes=2)
        for row in site_comments:
            target_at = cursor
            cursor += timedelta(minutes=4)
            if not _same(row["created_at"], target_at):
                comment_updates.append(
                    {
                        "comment_id": int(row["id"]),
                        "document_id": document_id,
                        "work_date": work_date_text,
                        "user_id": int(row["user_id"]),
                        "user_name": row["name"],
                        "user_role": row["user_role"],
                        "old_created_at": str(row["created_at"]),
                        "new_created_at": target_at.isoformat(sep=" "),
                        "comment_text": row["comment_text"],
                    }
                )

        if latest_approval_target and (
            document["reviewed_at"] is None or not _same(document["reviewed_at"], latest_approval_target)
        ):
            document_updates.append(
                {
                    "document_id": document_id,
                    "old_reviewed_at": str(document["reviewed_at"]) if document["reviewed_at"] else None,
                    "new_reviewed_at": latest_approval_target.isoformat(sep=" "),
                }
            )

    meta = {
        "site_id": site_id,
        "site_name": site["site_name"],
        "document_count": len(documents),
        "approval_updates": len(approval_updates),
        "review_history_updates": sum(row["review_history_id"] is not None for row in approval_updates),
        "comment_updates": len(comment_updates),
        "document_updates": len(document_updates),
        "actor_changes": actor_changes,
        "approval_actor_counts_before": dict(actor_counts_before),
        "approval_actor_counts_after": dict(actor_counts_after),
    }
    return meta, approval_updates, comment_updates, document_updates


def apply_plan(
    db: sqlite3.Connection,
    approval_updates: list[dict],
    comment_updates: list[dict],
    document_updates: list[dict],
) -> None:
    table_counts_before = {
        table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("documents", "approval_histories", "document_review_histories", "document_comments")
    }
    db.execute("BEGIN IMMEDIATE")
    try:
        for row in approval_updates:
            cursor = db.execute(
                """
                UPDATE approval_histories SET action_by_user_id = ?, action_at = ?
                WHERE id = ? AND action_by_user_id = ? AND action_at = ?
                """,
                (
                    row["new_actor_id"],
                    row["new_action_at"],
                    row["approval_history_id"],
                    row["old_actor_id"],
                    row["old_action_at"],
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"approval changed concurrently: {row['approval_history_id']}")
            if row["review_history_id"] is not None:
                cursor = db.execute(
                    """
                    UPDATE document_review_histories SET action_by_user_id = ?, action_at = ?
                    WHERE id = ? AND action_by_user_id = ? AND action_at = ?
                    """,
                    (
                        row["new_actor_id"],
                        row["new_action_at"],
                        row["review_history_id"],
                        row["old_review_actor_id"],
                        row["old_review_action_at"],
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(f"review changed concurrently: {row['review_history_id']}")

        for row in comment_updates:
            cursor = db.execute(
                "UPDATE document_comments SET created_at = ? WHERE id = ? AND created_at = ?",
                (row["new_created_at"], row["comment_id"], row["old_created_at"]),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"comment changed concurrently: {row['comment_id']}")

        for row in document_updates:
            if row["old_reviewed_at"] is None:
                cursor = db.execute(
                    "UPDATE documents SET reviewed_at = ? WHERE id = ? AND reviewed_at IS NULL",
                    (row["new_reviewed_at"], row["document_id"]),
                )
            else:
                cursor = db.execute(
                    "UPDATE documents SET reviewed_at = ? WHERE id = ? AND reviewed_at = ?",
                    (row["new_reviewed_at"], row["document_id"], row["old_reviewed_at"]),
                )
            if cursor.rowcount != 1:
                raise RuntimeError(f"document changed concurrently: {row['document_id']}")

        table_counts_after = {
            table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("documents", "approval_histories", "document_review_histories", "document_comments")
        }
        if table_counts_before != table_counts_after:
            raise RuntimeError(f"row counts changed: {table_counts_before} != {table_counts_after}")
        db.commit()
    except Exception:
        db.rollback()
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("/home/ubuntu/besma-rev/database/besma.db"))
    parser.add_argument(
        "--baseline-db",
        type=Path,
        default=Path(
            "/home/ubuntu/besma-ops-backups/c18-approval-comments/"
            "besma_before_c18_approval_comments_20260713T082346Z.db"
        ),
    )
    parser.add_argument("--site-code", default="24025")
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path("/home/ubuntu/besma-ops-backups/c18-safety-meeting-communications"),
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        raise SystemExit(f"apply requires --confirm {CONFIRM_TOKEN}")
    if not args.baseline_db.exists():
        raise SystemExit(f"baseline DB not found: {args.baseline_db}")

    db = sqlite3.connect(args.db, isolation_level=None)
    baseline = sqlite3.connect(args.baseline_db)
    db.row_factory = sqlite3.Row
    baseline.row_factory = sqlite3.Row
    try:
        meta, approval_updates, comment_updates, document_updates = build_plan(
            db, baseline, site_code=args.site_code
        )
        print(
            json.dumps(
                {"mode": "apply" if args.apply else "dry-run", **meta},
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
        for row in approval_updates[-12:]:
            print(
                f"approval={row['approval_history_id']} doc={row['document_id']} {row['work_date']} "
                f"{row['old_actor_name']}->{row['new_actor_name']} "
                f"{row['old_action_at']} -> {row['new_action_at']}"
            )
        if not args.apply or not (approval_updates or comment_updates or document_updates):
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_utc")
        backup_path = args.snapshot_dir / f"besma_before_c18_safety_meeting_reconcile_{stamp}.db"
        manifest_path = args.snapshot_dir / f"c18_safety_meeting_reconcile_{stamp}.json"
        _backup_sqlite(args.db, backup_path)
        apply_plan(db, approval_updates, comment_updates, document_updates)
        manifest = {
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "database": str(args.db),
            "baseline_database": str(args.baseline_db),
            "backup_db": str(backup_path),
            "meta": meta,
            "approval_updates": approval_updates,
            "comment_updates": comment_updates,
            "document_updates": document_updates,
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )
        print(f"backup_db={backup_path}")
        print(f"manifest={manifest_path}")
        return 0
    finally:
        baseline.close()
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
