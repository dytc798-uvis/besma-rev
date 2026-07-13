"""Add replies only to surviving, manually entered C18 HQ feedback.

This one-time operation deliberately excludes:

* the 154 approval comments created by ``backfill_c18_approval_comments.py``;
* the 168 formerly-corrupted approval comments repaired on 2026-07-13;
* the UI default ``HQ 승인`` and deployment/test validation events.

The source IDs below are the surviving business feedback rows proven by the
pre-repair production snapshot.  Existing SITE replies are preserved and a
reply is inserted only when no later SITE comment exists for that document.

Production usage::

    cd /home/ubuntu/besma-rev/backend
    PYTHONPATH=. .venv/bin/python scripts/backfill_c18_manual_feedback_replies.py \
      --dry-run --as-of-utc 2026-07-13T10:00:00

    PYTHONPATH=. .venv/bin/python scripts/backfill_c18_manual_feedback_replies.py \
      --apply --confirm REPLY_TO_C18_MANUAL_FEEDBACK \
      --as-of-utc 2026-07-13T10:00:00
"""

from __future__ import annotations

import argparse
import copy
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import app.main  # noqa: F401  # register all ORM models

from app.config.settings import settings
from app.core.database import SessionLocal
from app.modules.approvals.models import ApprovalHistory
from app.modules.documents.models import Document, DocumentComment
from app.modules.sites.models import Site
from app.modules.users.models import User
from scripts.repair_c18_corrupted_approval_comments import (
    _backup_sqlite,
    _capture_target_state,
    _is_lunch_kst,
    _parse_utc_naive,
    _site_status_counts,
    _site_workflow_counts,
    _table_counts,
    _validate_site_user,
    _write_json,
)


CONFIRM_TOKEN = "REPLY_TO_C18_MANUAL_FEEDBACK"
SITE_CODE = "24025"
MANAGER_DOCUMENT_TYPE = "SITE_MANAGER_CHECKLIST"
MANAGER_LOGIN = "site02"
MANAGER_NAME = "박명식"
SAFETY_MANAGER_LOGIN = "site03"
SAFETY_MANAGER_NAME = "박규철"
DEFAULT_SEED = 20260713
KST = timezone(timedelta(hours=9), name="KST")

# Directly entered business feedback in approval history IDs 1..57.  The three
# human-entered test rows (2, 3, 15), default HQ approvals and deployment
# validation rows are retained in the DB but intentionally receive no business
# reply.
MANUAL_APPROVAL_HISTORY_IDS = (
    5,
    7,
    12,
    13,
    17,
    19,
    20,
    21,
    25,
    26,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    37,
    38,
    39,
    40,
    41,
    43,
    44,
    45,
    46,
    47,
    48,
)

# Direct HQ comments in the flat document discussion timeline.  Comment ID 6
# is a test and is preserved without an operational reply.
MANUAL_HQ_DOCUMENT_COMMENT_IDS = (4, 5, 7, 8, 9, 11, 16)

EXPECTED_FEEDBACK_DOCUMENTS = 32
EXPECTED_EXISTINGLY_ANSWERED_DOCUMENTS = 5
EXPECTED_INITIAL_MISSING_REPLIES = 27
EXPECTED_INITIAL_MANAGER_REPLIES = 4
EXPECTED_INITIAL_SAFETY_MANAGER_REPLIES = 23


@dataclass(frozen=True)
class FeedbackSource:
    source: str
    row_id: int
    actor_name: str
    text: str
    created_at: datetime


@dataclass(frozen=True)
class ReplyPlan:
    document_id: int
    instance_id: int
    document_type: str
    latest_feedback_at: datetime
    feedback_sources: tuple[FeedbackSource, ...]
    reply_user_id: int
    reply_user_login: str
    reply_user_name: str
    reply_text: str
    reply_at: datetime


def _feedback_payload(source: FeedbackSource) -> dict[str, Any]:
    return {
        "source": source.source,
        "row_id": source.row_id,
        "actor_name": source.actor_name,
        "text": source.text,
        "created_at": source.created_at.isoformat(),
    }


def _plan_payload(plan: ReplyPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["latest_feedback_at"] = plan.latest_feedback_at.isoformat()
    payload["reply_at"] = plan.reply_at.isoformat()
    payload["feedback_sources"] = [_feedback_payload(row) for row in plan.feedback_sources]
    return payload


def _pick_reply_text(document_type: str, feedback_text: str, rng: random.Random) -> str:
    if document_type == MANAGER_DOCUMENT_TYPE:
        pool = (
            "네, 확인했습니다. 소장점검에 반영하고 지적사항은 이미 조치했습니다.",
            "네 알겠습니다. 현장을 다시 확인했고 필요한 조치를 완료했습니다.",
        )
    elif "온열" in feedback_text:
        pool = (
            "네, 확인했습니다. 음용수와 휴식시간을 확보하고 온열질환 예방조치를 완료했습니다.",
        )
    elif "교육" in feedback_text or document_type == "DAILY_TBM":
        pool = (
            "네, 확인했습니다. 말씀하신 교육·TBM 전파사항을 반영하고 이미 조치했습니다.",
            "네 알겠습니다. 작업자에게 내용을 전파하고 필요한 조치를 완료했습니다.",
        )
    elif "위험성평가" in feedback_text or document_type == "DAILY_RISK_ASSESSMENT":
        pool = (
            "네, 확인했습니다. 위험성평가 지적사항을 반영하여 이미 조치했습니다.",
            "네 알겠습니다. 누락사항을 보완하고 안전대책 이행을 확인했습니다.",
        )
    elif document_type == "SUPERVISOR_CHECKLIST":
        pool = (
            "네, 확인했습니다. 점검 지적사항은 현장에 반영해 이미 조치했습니다.",
            "네 알겠습니다. 점검내용을 보완하고 조치 완료했습니다.",
        )
    elif document_type == "SAFETY_MANAGER_DAILY_LOG":
        pool = (
            "네, 확인했습니다. 지적사항을 관리대장에 반영하고 조치 완료했습니다.",
            "네 알겠습니다. 개선내용을 반영하고 추적관리하겠습니다.",
        )
    elif document_type == "DAILY_SAFETY_MEETING_LOG":
        pool = (
            "네, 알겠습니다. 회의 및 전파사항에 반영했고 필요한 조치를 완료했습니다.",
            "네, 확인했습니다. 회의내용을 공유하고 지적사항은 이미 조치했습니다.",
        )
    else:
        pool = (
            "네 알겠습니다. 지적사항은 이미 조치했습니다.",
            "네, 확인했습니다. 말씀하신 내용을 반영하고 조치 완료했습니다.",
        )
    return rng.choice(pool)


def _pick_reply_at(*, feedback_at: datetime, document_id: int, seed: int, cutoff: datetime) -> datetime:
    rng = random.Random(seed + document_id * 1009)
    delays = (
        timedelta(minutes=35),
        timedelta(minutes=75),
        timedelta(hours=2, minutes=20),
        timedelta(hours=14, minutes=20),
        timedelta(hours=18, minutes=15),
        timedelta(hours=25, minutes=10),
        timedelta(hours=42, minutes=5),
    )
    candidate = feedback_at + rng.choice(delays)
    if _is_lunch_kst(candidate):
        local = candidate.replace(tzinfo=timezone.utc).astimezone(KST)
        local = local.replace(hour=13, minute=5 + rng.randrange(0, 36), second=rng.randrange(0, 60))
        candidate = local.astimezone(timezone.utc).replace(tzinfo=None)
    if candidate <= feedback_at:
        raise RuntimeError(f"document {document_id}: reply is not after feedback")
    if candidate > cutoff:
        raise RuntimeError(f"document {document_id}: reply exceeds cutoff")
    if _is_lunch_kst(candidate):
        raise RuntimeError(f"document {document_id}: reply falls in KST lunch")
    return candidate


def _load_feedback(db, *, site: Site) -> dict[int, list[FeedbackSource]]:
    feedback: dict[int, list[FeedbackSource]] = defaultdict(list)

    approvals = (
        db.query(ApprovalHistory, Document, User)
        .join(Document, Document.id == ApprovalHistory.document_id)
        .join(User, User.id == ApprovalHistory.action_by_user_id)
        .filter(ApprovalHistory.id.in_(MANUAL_APPROVAL_HISTORY_IDS), Document.site_id == site.id)
        .order_by(ApprovalHistory.id)
        .all()
    )
    approval_ids = {int(row.id) for row, _, _ in approvals}
    if approval_ids != set(MANUAL_APPROVAL_HISTORY_IDS):
        raise RuntimeError(f"manual approval source drift: {sorted(approval_ids)}")
    for history, document, actor in approvals:
        feedback[int(document.id)].append(
            FeedbackSource(
                source="approval_history",
                row_id=int(history.id),
                actor_name=str(actor.name),
                text=str(history.comment or ""),
                created_at=history.action_at,
            )
        )

    comments = (
        db.query(DocumentComment, Document, User)
        .join(Document, Document.id == DocumentComment.document_id)
        .join(User, User.id == DocumentComment.user_id)
        .filter(DocumentComment.id.in_(MANUAL_HQ_DOCUMENT_COMMENT_IDS), Document.site_id == site.id)
        .order_by(DocumentComment.id)
        .all()
    )
    comment_ids = {int(row.id) for row, _, _ in comments}
    if comment_ids != set(MANUAL_HQ_DOCUMENT_COMMENT_IDS):
        raise RuntimeError(f"manual document-comment source drift: {sorted(comment_ids)}")
    for comment, document, actor in comments:
        if str(comment.user_role) != "HQ":
            raise RuntimeError(f"manual comment {comment.id}: expected HQ role")
        feedback[int(document.id)].append(
            FeedbackSource(
                source="document_comment",
                row_id=int(comment.id),
                actor_name=str(actor.name),
                text=str(comment.comment_text),
                created_at=comment.created_at,
            )
        )

    if len(feedback) != EXPECTED_FEEDBACK_DOCUMENTS:
        raise RuntimeError(f"manual feedback document drift: {len(feedback)}")
    return feedback


def build_plan(
    db,
    *,
    site: Site,
    manager: User,
    safety_manager: User,
    cutoff: datetime,
    seed: int,
) -> tuple[list[ReplyPlan], list[int]]:
    feedback = _load_feedback(db, site=site)
    plans: list[ReplyPlan] = []
    covered: list[int] = []
    for document_id in sorted(feedback):
        document = db.query(Document).filter(Document.id == document_id, Document.site_id == site.id).one()
        if document.instance_id is None:
            raise RuntimeError(f"document {document_id}: missing instance")
        sources = tuple(sorted(feedback[document_id], key=lambda row: (row.created_at, row.source, row.row_id)))
        latest_at = max(row.created_at for row in sources)
        existing_reply = (
            db.query(DocumentComment.id)
            .filter(
                DocumentComment.document_id == document_id,
                DocumentComment.user_role == "SITE",
                DocumentComment.created_at > latest_at,
            )
            .order_by(DocumentComment.created_at, DocumentComment.id)
            .first()
        )
        if existing_reply is not None:
            covered.append(document_id)
            continue

        document_type = str(document.document_type)
        actor = manager if document_type == MANAGER_DOCUMENT_TYPE else safety_manager
        rng = random.Random(seed + document_id * 2029)
        joined_feedback = "\n".join(row.text for row in sources)
        plans.append(
            ReplyPlan(
                document_id=document_id,
                instance_id=int(document.instance_id),
                document_type=document_type,
                latest_feedback_at=latest_at,
                feedback_sources=sources,
                reply_user_id=int(actor.id),
                reply_user_login=str(actor.login_id),
                reply_user_name=str(actor.name),
                reply_text=_pick_reply_text(document_type, joined_feedback, rng),
                reply_at=_pick_reply_at(
                    feedback_at=latest_at,
                    document_id=document_id,
                    seed=seed,
                    cutoff=cutoff,
                ),
            )
        )

    if len(plans) == EXPECTED_INITIAL_MISSING_REPLIES:
        if len(covered) != EXPECTED_EXISTINGLY_ANSWERED_DOCUMENTS:
            raise RuntimeError(f"unexpected already-answered count: {len(covered)}")
        manager_count = sum(plan.reply_user_login == MANAGER_LOGIN for plan in plans)
        safety_count = sum(plan.reply_user_login == SAFETY_MANAGER_LOGIN for plan in plans)
        if (manager_count, safety_count) != (
            EXPECTED_INITIAL_MANAGER_REPLIES,
            EXPECTED_INITIAL_SAFETY_MANAGER_REPLIES,
        ):
            raise RuntimeError(f"unexpected actor split: {manager_count}/{safety_count}")
    elif plans:
        raise RuntimeError(f"partial/drifted missing reply count: {len(plans)}")
    elif len(covered) != EXPECTED_FEEDBACK_DOCUMENTS:
        raise RuntimeError(f"idempotent coverage mismatch: {len(covered)}")
    return plans, covered


def _baseline_payload(
    db,
    *,
    site: Site,
    plans: list[ReplyPlan],
    covered: list[int],
    cutoff: datetime,
    seed: int,
) -> dict[str, Any]:
    all_document_ids = sorted(set(covered) | {plan.document_id for plan in plans})
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(Path(settings.sqlite_path).resolve()),
        "site": {"id": int(site.id), "site_code": str(site.site_code), "site_name": str(site.site_name)},
        "cutoff_utc": cutoff.isoformat(),
        "seed": seed,
        "source_approval_history_ids": list(MANUAL_APPROVAL_HISTORY_IDS),
        "source_document_comment_ids": list(MANUAL_HQ_DOCUMENT_COMMENT_IDS),
        "covered_document_ids": covered,
        "plans": [_plan_payload(plan) for plan in plans],
        "counts": _table_counts(db),
        "site_status_counts": _site_status_counts(db, site_id=int(site.id)),
        "site_workflow_counts": _site_workflow_counts(db, site_id=int(site.id)),
        "target_state": _capture_target_state(db, target_document_ids=all_document_ids),
    }


def apply_plan(db, *, plans: list[ReplyPlan]) -> list[int]:
    created_ids: list[int] = []
    for plan in plans:
        duplicate = (
            db.query(DocumentComment.id)
            .filter(
                DocumentComment.document_id == plan.document_id,
                DocumentComment.user_role == "SITE",
                DocumentComment.created_at > plan.latest_feedback_at,
            )
            .first()
        )
        if duplicate is not None:
            raise RuntimeError(f"document {plan.document_id}: reply appeared after planning")
        row = DocumentComment(
            document_id=plan.document_id,
            instance_id=plan.instance_id,
            user_id=plan.reply_user_id,
            user_role="SITE",
            comment_text=plan.reply_text,
            created_at=plan.reply_at,
        )
        db.add(row)
        db.flush()
        created_ids.append(int(row.id))
    if len(created_ids) != len(plans) or len(set(created_ids)) != len(plans):
        raise RuntimeError("created reply ID/count mismatch")
    return created_ids


def verify(
    db,
    *,
    site: Site,
    plans: list[ReplyPlan],
    created_ids: list[int],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    db.flush()
    all_document_ids = sorted(
        set(baseline["covered_document_ids"]) | {plan.document_id for plan in plans}
    )
    current = _capture_target_state(db, target_document_ids=all_document_ids)
    before = baseline["target_state"]
    errors: list[str] = []
    for key in ("documents", "instances", "upload_histories", "approval_histories", "review_histories"):
        if current[key] != before[key]:
            errors.append(f"{key}_changed")

    before_comments = {int(row["id"]): row for row in before["document_comments"]}
    after_comments = {int(row["id"]): row for row in current["document_comments"]}
    for row_id, row in before_comments.items():
        if after_comments.get(row_id) != row:
            errors.append(f"existing_comment_{row_id}_changed")
    if set(after_comments) != set(before_comments) | set(created_ids):
        errors.append("comment_id_set_mismatch")

    by_created = dict(zip(created_ids, plans, strict=True))
    for row_id, plan in by_created.items():
        row = after_comments.get(row_id)
        expected = {
            "document_id": plan.document_id,
            "instance_id": plan.instance_id,
            "user_id": plan.reply_user_id,
            "user_role": "SITE",
            "comment_text": plan.reply_text,
            "created_at": plan.reply_at.isoformat(),
        }
        if row is None or any(row.get(key) != value for key, value in expected.items()):
            errors.append(f"created_comment_{row_id}_payload")
        if plan.reply_at <= plan.latest_feedback_at or _is_lunch_kst(plan.reply_at):
            errors.append(f"created_comment_{row_id}_time")

    counts = _table_counts(db)
    expected_counts = dict(baseline["counts"])
    expected_counts["document_comments"] += len(plans)
    if counts != expected_counts:
        errors.append("table_counts_changed")
    status_counts = _site_status_counts(db, site_id=int(site.id))
    workflow_counts = _site_workflow_counts(db, site_id=int(site.id))
    if status_counts != baseline["site_status_counts"]:
        errors.append("site_status_counts_changed")
    if workflow_counts != baseline["site_workflow_counts"]:
        errors.append("site_workflow_counts_changed")

    remaining_plans, covered = build_plan(
        db,
        site=site,
        manager=db.query(User).filter(User.login_id == MANAGER_LOGIN).one(),
        safety_manager=db.query(User).filter(User.login_id == SAFETY_MANAGER_LOGIN).one(),
        cutoff=max(plan.reply_at for plan in plans) + timedelta(days=1),
        seed=DEFAULT_SEED,
    )
    if remaining_plans or len(covered) != EXPECTED_FEEDBACK_DOCUMENTS:
        errors.append("manual_feedback_not_fully_answered")

    result = {
        "created_reply_count": len(created_ids),
        "created_reply_ids": created_ids,
        "manager_reply_count": sum(plan.reply_user_login == MANAGER_LOGIN for plan in plans),
        "safety_manager_reply_count": sum(plan.reply_user_login == SAFETY_MANAGER_LOGIN for plan in plans),
        "covered_feedback_document_count": len(covered),
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
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of-utc", default=None)
    parser.add_argument(
        "--snapshot-dir",
        default="/home/ubuntu/besma-ops-backups/c18-manual-feedback-replies",
    )
    args = parser.parse_args()
    if args.apply and args.confirm != CONFIRM_TOKEN:
        parser.error(f"--apply requires --confirm {CONFIRM_TOKEN}")
    return args


def main() -> int:
    args = _args()
    cutoff = _parse_utc_naive(args.as_of_utc)
    db = SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_code == SITE_CODE).one_or_none()
        if site is None or "C18" not in str(site.site_name).upper() or "청라" not in str(site.site_name):
            raise RuntimeError("refusing unexpected site")
        manager = _validate_site_user(db, site=site, login_id=MANAGER_LOGIN, expected_name=MANAGER_NAME)
        safety_manager = _validate_site_user(
            db,
            site=site,
            login_id=SAFETY_MANAGER_LOGIN,
            expected_name=SAFETY_MANAGER_NAME,
        )
        plans, covered = build_plan(
            db,
            site=site,
            manager=manager,
            safety_manager=safety_manager,
            cutoff=cutoff,
            seed=int(args.seed),
        )
        print(f"database={Path(settings.sqlite_path).resolve()}")
        print(f"site={site.id}/{site.site_code}/{site.site_name}")
        print(f"feedback_documents={EXPECTED_FEEDBACK_DOCUMENTS}")
        print(f"already_answered={len(covered)}")
        print(f"missing_replies={len(plans)}")
        print(f"manager_replies={sum(plan.reply_user_login == MANAGER_LOGIN for plan in plans)}")
        print(f"safety_manager_replies={sum(plan.reply_user_login == SAFETY_MANAGER_LOGIN for plan in plans)}")
        for plan in plans:
            print(
                "plan",
                plan.document_id,
                plan.document_type,
                plan.latest_feedback_at.isoformat(),
                "->",
                plan.reply_at.isoformat(),
                plan.reply_user_name,
                plan.reply_text,
            )

        if not plans:
            db.rollback()
            print("NOOP_ALREADY_ANSWERED")
            return 0
        if args.dry_run:
            db.rollback()
            print("DRY_RUN_OK")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = Path(args.snapshot_dir).expanduser().resolve()
        before_json = snapshot_dir / f"before_c18_manual_feedback_replies_{stamp}.json"
        before_db = snapshot_dir / f"besma_before_c18_manual_feedback_replies_{stamp}.db"
        manifest_json = snapshot_dir / f"c18_manual_feedback_replies_{stamp}.json"
        baseline = _baseline_payload(
            db,
            site=site,
            plans=plans,
            covered=covered,
            cutoff=cutoff,
            seed=int(args.seed),
        )
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

        created_ids = apply_plan(db, plans=plans)
        verification_before = verify(
            db,
            site=site,
            plans=plans,
            created_ids=created_ids,
            baseline=baseline,
        )
        db.commit()
        verification_after = verify(
            db,
            site=site,
            plans=plans,
            created_ids=created_ids,
            baseline=baseline,
        )
        manifest = copy.deepcopy(prepared)
        manifest.update(
            {
                "state": "applied",
                "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                "created_reply_ids": created_ids,
                "verification_before_commit": verification_before,
                "verification_after_commit": verification_after,
            }
        )
        _write_json(manifest_json, manifest)
        print(f"created_reply_ids={created_ids}")
        print(f"verification={verification_after}")
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
