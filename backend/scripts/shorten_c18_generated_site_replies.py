"""Shorten only the SITE replies generated for C18 on 2026-07-13.

The operation is intentionally limited to document comment IDs 18..212.  IDs
1..17 are the pre-existing, manually entered discussion and are never changed.
Exactly two rain replies retain the requested detailed electrical-leakage text;
all other generated replies are distributed across short acknowledgement texts.
"""

from __future__ import annotations

import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import app.main  # noqa: F401

from app.config.settings import settings
from app.core.database import SessionLocal
from app.modules.documents.models import Document, DocumentComment
from app.modules.sites.models import Site
from scripts.repair_c18_corrupted_approval_comments import (
    _backup_sqlite,
    _capture_target_state,
    _site_status_counts,
    _site_workflow_counts,
    _table_counts,
    _write_json,
)


CONFIRM_TOKEN = "SHORTEN_C18_GENERATED_SITE_REPLIES"
SITE_CODE = "24025"
FIRST_GENERATED_COMMENT_ID = 18
LAST_GENERATED_COMMENT_ID = 212
EXPECTED_GENERATED_COMMENT_COUNT = 195
PRESERVED_LONG_REPLY_IDS = frozenset({50, 51})
PRESERVED_LONG_REPLY = "네 알겠습니다. 배수상태와 누전방지 조치까지 확인했습니다."
EXPECTED_LONG_REPLY_COUNT = 2
MAX_SHORT_REPLY_FREQUENCY = 9

SHORT_REPLIES = (
    "네, 알겠습니다.",
    "네 알겠습니다.",
    "알겠습니다.",
    "네, 확인했습니다.",
    "확인했습니다.",
    "네, 그렇게 하겠습니다.",
    "그렇게 하겠습니다.",
    "네, 반영하겠습니다.",
    "알겠습니다. 반영하겠습니다.",
    "네, 조치하겠습니다.",
    "확인 후 조치하겠습니다.",
    "네, 유의하겠습니다.",
    "알겠습니다. 유의하겠습니다.",
    "네, 재확인하겠습니다.",
    "확인해 보겠습니다.",
    "네, 점검하겠습니다.",
    "알겠습니다. 점검하겠습니다.",
    "네, 보완하겠습니다.",
    "알겠습니다. 보완하겠습니다.",
    "네, 전달하겠습니다.",
    "현장에 전달하겠습니다.",
    "네, 확인하겠습니다.",
    "알겠습니다. 확인하겠습니다.",
    "네, 그렇게 진행하겠습니다.",
)

# A small, fixed subset intentionally retains natural spacing/typing slips.
# Keeping these as one-off overrides avoids turning the same typo into another
# visibly repeated template.
TYPO_AND_SPACING_OVERRIDES = {
    29: "네알겠습니다.",
    47: "네, 확인햇습니다.",
    73: "네 그렇게 하겟습니다.",
    96: "알겠습니다  확인하겠습니다.",
    123: "네, 반영하겟습니다.",
    151: "확인후 조치하겠습니다.",
    177: "네 알겠습니니다.",
    205: "네  점검하겠습니다.",
}


def _desired_text(comment_id: int) -> str:
    if comment_id in PRESERVED_LONG_REPLY_IDS:
        return PRESERVED_LONG_REPLY
    if comment_id in TYPO_AND_SPACING_OVERRIDES:
        return TYPO_AND_SPACING_OVERRIDES[comment_id]
    # 17 is coprime with 24, so consecutive IDs cycle through every variant
    # before repeating.  Removing IDs 50/51 still keeps the distribution even.
    return SHORT_REPLIES[((comment_id - FIRST_GENERATED_COMMENT_ID) * 17) % len(SHORT_REPLIES)]


def _rows(db, *, site: Site) -> list[tuple[DocumentComment, Document]]:
    rows = (
        db.query(DocumentComment, Document)
        .join(Document, Document.id == DocumentComment.document_id)
        .filter(
            DocumentComment.id.between(FIRST_GENERATED_COMMENT_ID, LAST_GENERATED_COMMENT_ID),
            Document.site_id == site.id,
        )
        .order_by(DocumentComment.id)
        .all()
    )
    ids = [int(comment.id) for comment, _ in rows]
    expected = list(range(FIRST_GENERATED_COMMENT_ID, LAST_GENERATED_COMMENT_ID + 1))
    if ids != expected or len(rows) != EXPECTED_GENERATED_COMMENT_COUNT:
        raise RuntimeError(f"generated reply ID drift: count={len(rows)}, ids={ids[:3]}..{ids[-3:] if ids else []}")
    for comment, document in rows:
        if str(comment.user_role) != "SITE":
            raise RuntimeError(f"comment {comment.id}: expected SITE role")
        if int(comment.user_id) not in {4, 13}:
            raise RuntimeError(f"comment {comment.id}: unexpected generated reply user {comment.user_id}")
        if comment.instance_id is None or int(comment.instance_id) != int(document.instance_id):
            raise RuntimeError(f"comment {comment.id}: document/instance mismatch")
    return rows


def build_plan(db, *, site: Site) -> list[dict[str, Any]]:
    rows = _rows(db, site=site)
    desired_counts = Counter(_desired_text(int(comment.id)) for comment, _ in rows)
    if desired_counts[PRESERVED_LONG_REPLY] != EXPECTED_LONG_REPLY_COUNT:
        raise RuntimeError("detailed rain reply target count is not exactly two")
    short_max = max(count for text, count in desired_counts.items() if text != PRESERVED_LONG_REPLY)
    if short_max > MAX_SHORT_REPLY_FREQUENCY:
        raise RuntimeError(f"short reply distribution too repetitive: max={short_max}")
    return [
        {
            "comment_id": int(comment.id),
            "document_id": int(comment.document_id),
            "instance_id": int(comment.instance_id),
            "user_id": int(comment.user_id),
            "created_at": comment.created_at,
            "old_text": str(comment.comment_text),
            "new_text": _desired_text(int(comment.id)),
        }
        for comment, _ in rows
        if str(comment.comment_text) != _desired_text(int(comment.id))
    ]


def _plan_payload(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        **plan,
        "created_at": plan["created_at"].isoformat(),
    }


def _baseline(db, *, site: Site, plans: list[dict[str, Any]]) -> dict[str, Any]:
    document_ids = sorted({int(plan["document_id"]) for plan in plans})
    manual_rows = (
        db.query(DocumentComment)
        .filter(DocumentComment.id < FIRST_GENERATED_COMMENT_ID)
        .order_by(DocumentComment.id)
        .all()
    )
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(Path(settings.sqlite_path).resolve()),
        "site": {"id": int(site.id), "site_code": str(site.site_code), "site_name": str(site.site_name)},
        "plans": [_plan_payload(plan) for plan in plans],
        "counts": _table_counts(db),
        "site_status_counts": _site_status_counts(db, site_id=int(site.id)),
        "site_workflow_counts": _site_workflow_counts(db, site_id=int(site.id)),
        "target_state": _capture_target_state(db, target_document_ids=document_ids),
        "manual_comment_rows": [
            {
                "id": int(row.id),
                "document_id": int(row.document_id),
                "instance_id": int(row.instance_id) if row.instance_id is not None else None,
                "user_id": int(row.user_id),
                "user_role": str(row.user_role),
                "comment_text": str(row.comment_text),
                "created_at": row.created_at.isoformat(),
            }
            for row in manual_rows
        ],
    }


def apply_plan(db, *, plans: list[dict[str, Any]]) -> None:
    for plan in plans:
        row = db.query(DocumentComment).filter(DocumentComment.id == plan["comment_id"]).one()
        if (
            int(row.document_id) != plan["document_id"]
            or int(row.instance_id) != plan["instance_id"]
            or int(row.user_id) != plan["user_id"]
            or row.created_at != plan["created_at"]
            or str(row.comment_text) != plan["old_text"]
        ):
            raise RuntimeError(f"comment {row.id}: changed after planning")
        row.comment_text = plan["new_text"]
        db.add(row)


def verify(db, *, site: Site, plans: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    db.flush()
    document_ids = sorted({int(plan["document_id"]) for plan in plans})
    current = _capture_target_state(db, target_document_ids=document_ids)
    before = baseline["target_state"]
    errors: list[str] = []
    for key in ("documents", "instances", "upload_histories", "approval_histories", "review_histories"):
        if current[key] != before[key]:
            errors.append(f"{key}_changed")

    expected_text = {int(plan["comment_id"]): str(plan["new_text"]) for plan in plans}
    before_comments = {int(row["id"]): row for row in before["document_comments"]}
    after_comments = {int(row["id"]): row for row in current["document_comments"]}
    if before_comments.keys() != after_comments.keys():
        errors.append("document_comment_ids_changed")
    else:
        for row_id, original in before_comments.items():
            expected = dict(original)
            if row_id in expected_text:
                expected["comment_text"] = expected_text[row_id]
            if after_comments[row_id] != expected:
                errors.append(f"comment_{row_id}_unexpected_change")

    manual_rows = (
        db.query(DocumentComment)
        .filter(DocumentComment.id < FIRST_GENERATED_COMMENT_ID)
        .order_by(DocumentComment.id)
        .all()
    )
    manual_payload = [
        {
            "id": int(row.id),
            "document_id": int(row.document_id),
            "instance_id": int(row.instance_id) if row.instance_id is not None else None,
            "user_id": int(row.user_id),
            "user_role": str(row.user_role),
            "comment_text": str(row.comment_text),
            "created_at": row.created_at.isoformat(),
        }
        for row in manual_rows
    ]
    if manual_payload != baseline["manual_comment_rows"]:
        errors.append("manual_comments_changed")

    rows = _rows(db, site=site)
    text_counts = Counter(str(comment.comment_text) for comment, _ in rows)
    long_count = text_counts[PRESERVED_LONG_REPLY]
    short_max = max(count for text, count in text_counts.items() if text != PRESERVED_LONG_REPLY)
    if long_count != EXPECTED_LONG_REPLY_COUNT:
        errors.append("detailed_rain_reply_count")
    if short_max > MAX_SHORT_REPLY_FREQUENCY:
        errors.append("short_reply_frequency")
    if any(str(comment.comment_text) != _desired_text(int(comment.id)) for comment, _ in rows):
        errors.append("reply_text_plan_mismatch")

    counts = _table_counts(db)
    status_counts = _site_status_counts(db, site_id=int(site.id))
    workflow_counts = _site_workflow_counts(db, site_id=int(site.id))
    if counts != baseline["counts"]:
        errors.append("table_counts_changed")
    if status_counts != baseline["site_status_counts"]:
        errors.append("site_status_counts_changed")
    if workflow_counts != baseline["site_workflow_counts"]:
        errors.append("site_workflow_counts_changed")

    result = {
        "updated_reply_count": len(plans),
        "detailed_rain_reply_count": long_count,
        "short_reply_variant_count": len(text_counts) - 1,
        "maximum_short_reply_frequency": short_max,
        "counts": counts,
        "site_status_counts": status_counts,
        "site_workflow_counts": workflow_counts,
        "errors": errors,
    }
    if errors:
        raise RuntimeError(f"verification failed: {result}")
    return result


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--snapshot-dir",
        default="/home/ubuntu/besma-ops-backups/c18-generated-reply-shortening",
    )
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        parser.error(f"--apply requires --confirm {CONFIRM_TOKEN}")
    return args


def main() -> int:
    args = _args()
    db = SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_code == SITE_CODE).one_or_none()
        if site is None or "C18" not in str(site.site_name).upper() or "청라" not in str(site.site_name):
            raise RuntimeError("refusing unexpected site")
        plans = build_plan(db, site=site)
        rows = _rows(db, site=site)
        desired_counts = Counter(_desired_text(int(comment.id)) for comment, _ in rows)
        print(f"database={Path(settings.sqlite_path).resolve()}")
        print(f"site={site.id}/{site.site_code}/{site.site_name}")
        print(f"generated_replies={len(rows)}")
        print(f"updates={len(plans)}")
        print(f"desired_detailed_rain_replies={desired_counts[PRESERVED_LONG_REPLY]}")
        print(f"desired_short_variants={len(desired_counts) - 1}")
        print(f"desired_max_short_frequency={max(count for text, count in desired_counts.items() if text != PRESERVED_LONG_REPLY)}")

        if not plans:
            db.rollback()
            print("NOOP_ALREADY_SHORTENED")
            return 0
        if args.dry_run:
            db.rollback()
            print("DRY_RUN_OK")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = Path(args.snapshot_dir).expanduser().resolve()
        before_json = snapshot_dir / f"before_c18_generated_reply_shortening_{stamp}.json"
        before_db = snapshot_dir / f"besma_before_c18_generated_reply_shortening_{stamp}.db"
        manifest_json = snapshot_dir / f"c18_generated_reply_shortening_{stamp}.json"
        baseline = _baseline(db, site=site, plans=plans)
        _write_json(before_json, baseline)
        _backup_sqlite(before_db)
        prepared = {
            "state": "prepared",
            "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
            "before_json": str(before_json),
            "before_db": str(before_db),
            "plans": [_plan_payload(plan) for plan in plans],
        }
        _write_json(manifest_json, prepared)
        print(f"before_json={before_json}")
        print(f"before_db={before_db}")
        print(f"prepared_manifest={manifest_json}")

        apply_plan(db, plans=plans)
        before_commit = verify(db, site=site, plans=plans, baseline=baseline)
        db.commit()
        after_commit = verify(db, site=site, plans=plans, baseline=baseline)
        manifest = copy.deepcopy(prepared)
        manifest.update(
            {
                "state": "applied",
                "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                "verification_before_commit": before_commit,
                "verification_after_commit": after_commit,
            }
        )
        _write_json(manifest_json, manifest)
        print(f"verification={after_commit}")
        print(f"manifest={manifest_json}")
        print("APPLY_OK")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
