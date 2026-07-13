"""Repair corrupted C18 approval comments and add the requested site replies.

This is a deliberately narrow, one-time production backfill.  It only targets
the C18 site (site_code 24025) and approval comments whose stored value is the
literal ASCII text ``?? ?? ??``.  It never changes approval actors, timestamps,
actions, document/workflow statuses, uploads, or existing document comments.

Production usage::

    cd /home/ubuntu/besma-rev/backend
    PYTHONPATH=. .venv/bin/python scripts/repair_c18_corrupted_approval_comments.py \
      --dry-run --as-of-utc 2026-07-13T09:00:00

    PYTHONPATH=. .venv/bin/python scripts/repair_c18_corrupted_approval_comments.py \
      --apply --confirm REPAIR_C18_CORRUPTED_APPROVAL_COMMENTS \
      --as-of-utc 2026-07-13T09:00:00

The first apply requires exactly 168 targets.  A later dry-run (or confirmed
apply) with zero targets is an idempotent no-op.  Any partial/drifted target
count is rejected before a snapshot or mutation is attempted.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import app.main  # noqa: F401  # register every ORM model before querying

from app.config.settings import settings
from app.core.database import SessionLocal
from app.core.enums import Role
from app.modules.approvals.models import ApprovalAction, ApprovalHistory
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_settings.models import DocumentRequirement
from app.modules.document_submissions.models import DocumentReviewHistory, ReviewAction
from app.modules.documents.models import (
    Document,
    DocumentComment,
    DocumentCommentSiteAck,
    DocumentStatus,
    DocumentUploadHistory,
)
from app.modules.sites.models import Site
from app.modules.users.models import User
from scripts.backfill_c18_approval_comments import RAIN_MM_BY_DATE as _SOURCE_RAIN_MM_BY_DATE


CONFIRM_TOKEN = "REPAIR_C18_CORRUPTED_APPROVAL_COMMENTS"
SITE_CODE = "24025"
CORRUPTED_COMMENT = "?? ?? ??"
EXPECTED_INITIAL_TARGETS = 168
EXPECTED_MANAGER_TARGETS = 28
EXPECTED_OTHER_TARGETS = 140
EXPECTED_MATCHED_CORRUPTED_REVIEWS = 1
MANAGER_REQUIREMENT_CODE = "SITE_MANAGER_CHECKLIST"
MANAGER_LOGIN = "site02"
MANAGER_NAME = "박명식"
SAFETY_MANAGER_LOGIN = "site03"
SAFETY_MANAGER_NAME = "박규철"
DEFAULT_SEED = 20260713
KST = timezone(timedelta(hours=9), name="KST")
REVIEW_MATCH_TOLERANCE_SECONDS = 1.0

# Copy the already-reviewed Cheongna/Open-Meteo map rather than redefining or
# mutating the source constant.  This keeps both C18 scripts on the same rain
# dates while making this script's use read-only and deterministic.
CHEONGNA_RAIN_MM_BY_DATE: dict[date, float] = dict(_SOURCE_RAIN_MM_BY_DATE)


GENERAL_HQ_COMMENTS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "DAILY_TBM": (
        "TBM 내용 확인했습니다. 작업 전 주요 위험요인과 예방대책을 근로자에게 충분히 전파해 주세요.",
        "TBM 확인했습니다. 작업순서와 상호 신호체계를 다시 한번 공유하고 안전하게 작업해 주세요.",
        "내용 확인했습니다. 작업 시작 전 보호구 착용과 작업구간 정리 상태를 점검해 주세요.",
    ),
    "DAILY_RISK_ASSESSMENT": (
        "일일위험성평가 확인했습니다. 도출된 위험요인별 안전대책을 작업 전에 이행해 주세요.",
        "위험성평가 내용 확인했습니다. 작업 변경사항을 반영하고 근로자에게 예방대책을 공유해 주세요.",
        "검토했습니다. 위험요인의 원인과 결과를 구분하고 현장에서 대책 이행 여부를 확인해 주세요.",
    ),
    "ADHOC_RISK_ASSESSMENT": (
        "수시위험성평가 확인했습니다. 변경된 작업조건에 따른 추가 위험요인과 대책을 즉시 공유해 주세요.",
        "검토했습니다. 작업 변경 전 수시위험성평가 대책을 현장에 반영해 주세요.",
    ),
    "DAILY_SAFETY_MEETING_LOG": (
        "안전회의 내용 확인했습니다. 회의에서 정한 조치사항을 TBM 때 빠짐없이 전파해 주세요.",
        "회의일지 확인했습니다. 논의된 위험요인과 안전대책을 작업자에게 공유하고 이행 여부를 점검해 주세요.",
        "검토했습니다. 회의 조치사항의 담당자와 이행 결과를 현장에서 확인해 주세요.",
    ),
    "SUPERVISOR_CHECKLIST": (
        "관리감독자 점검표 확인했습니다. 지적사항을 조치하고 작업구간 안전상태를 재확인해 주세요.",
        "점검내용 확인했습니다. 불안전한 상태가 남지 않도록 즉시 개선하고 결과를 공유해 주세요.",
        "검토했습니다. 관리감독자 순회점검과 작업 전 안전조치 확인을 철저히 해 주세요.",
    ),
    "SAFETY_MANAGER_DAILY_LOG": (
        "안전관리자 업무일지 확인했습니다. 현장 순회점검과 지적사항 조치 여부를 계속 확인해 주세요.",
        "업무일지 검토했습니다. 작업구간별 안전시설과 보호구 착용 상태를 점검해 주세요.",
        "내용 확인했습니다. 발견된 위험요인은 즉시 개선하고 조치 결과를 확인해 주세요.",
    ),
    MANAGER_REQUIREMENT_CODE: (
        "현장소장 점검표 확인했습니다. 점검 지적사항을 조치하고 현장 전반의 안전상태를 재확인해 주세요.",
        "소장점검 내용 검토했습니다. 주요 위험요인의 개선 결과와 안전조치 이행 여부를 확인해 주세요.",
        "점검표 확인했습니다. 공정별 위험요인과 안전시설 상태를 소장점검 시 다시 확인해 주세요.",
    ),
    "EMERGENCY_DRILL_REPORT": (
        "비상사태 훈련보고서 확인했습니다. 훈련 중 확인된 개선사항을 비상대응 절차에 반영해 주세요.",
    ),
    "MSDS_EDUCATION": (
        "MSDS 교육자료 확인했습니다. 취급물질의 유해성과 보호구 사용방법을 근로자에게 충분히 안내해 주세요.",
    ),
    "REGULAR_EDUCATION": (
        "정기교육 자료 확인했습니다. 교육내용이 실제 작업 안전수칙으로 이어지도록 현장에서 확인해 주세요.",
    ),
    "SPECIAL_EDUCATION": (
        "특별교육 자료 확인했습니다. 해당 작업의 주요 위험요인과 안전작업 절차를 철저히 준수해 주세요.",
    ),
}

FALLBACK_HQ_COMMENTS = (
    "문서 확인했습니다. 작업 전 위험요인을 공유하고 안전수칙을 철저히 준수해 주세요.",
    "내용 검토했습니다. 현장 안전조치 이행 여부를 다시 한번 확인해 주세요.",
    "확인했습니다. 보호구 착용과 작업구간 정리정돈을 철저히 해 주세요.",
)

RAIN_HQ_COMMENTS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "DAILY_TBM": (
        "TBM 내용 확인했습니다. 우천으로 통로가 미끄러울 수 있으니 빗물 제거와 미끄럼방지 대책을 작업자에게 전파해 주세요.",
        "TBM 확인했습니다. 비 온 뒤 작업발판과 계단의 물기를 제거하고 근로자 이동 시 주의사항을 공유해 주세요.",
    ),
    "DAILY_RISK_ASSESSMENT": (
        "일일위험성평가 확인했습니다. 빗물 고임과 미끄럼 위험을 반영하고 배수·미끄럼방지 조치를 이행해 주세요.",
        "위험성평가 검토했습니다. 우천에 따른 감전과 근로자 미끄럼 위험의 예방대책을 현장에 반영해 주세요.",
    ),
    "ADHOC_RISK_ASSESSMENT": (
        "수시위험성평가 확인했습니다. 우천으로 변경된 작업조건과 미끄럼 위험에 대한 추가 대책을 이행해 주세요.",
    ),
    "DAILY_SAFETY_MEETING_LOG": (
        "안전회의 내용 확인했습니다. 빗물에 근로자가 미끄러지지 않도록 통행로 정리와 배수조치를 공유해 주세요.",
        "회의일지 확인했습니다. 우천 시 미끄럼방지와 전기기계·기구 누전방지 대책을 TBM에 전파해 주세요.",
    ),
    "SUPERVISOR_CHECKLIST": (
        "관리감독자 점검표 확인했습니다. 빗물 고임을 제거하고 작업발판·계단의 미끄럼방지 상태를 점검해 주세요.",
        "점검내용 확인했습니다. 우천 후 근로자 통행로와 작업구간의 배수상태를 재확인해 주세요.",
    ),
    "SAFETY_MANAGER_DAILY_LOG": (
        "안전관리자 업무일지 확인했습니다. 우천 후 빗물 제거와 근로자 미끄럼방지 조치 상태를 순회점검해 주세요.",
        "업무일지 검토했습니다. 젖은 작업발판과 통행로를 정리하고 누전 위험도 함께 확인해 주세요.",
    ),
    MANAGER_REQUIREMENT_CODE: (
        "현장소장 점검표 확인했습니다. 우천 후 배수상태와 근로자 통행로의 미끄럼방지 조치를 재확인해 주세요.",
        "소장점검 내용 확인했습니다. 빗물 고임 제거와 작업발판·계단의 미끄럼방지 상태를 점검해 주세요.",
    ),
}

FALLBACK_RAIN_HQ_COMMENTS = (
    "문서 확인했습니다. 빗물에 근로자 미끄럼방지 부탁드립니다.",
    "확인했습니다. 우천 후 배수상태와 작업자 통행로의 미끄럼 위험을 점검해 주세요.",
    "검토했습니다. 젖은 작업발판과 계단의 물기를 제거하고 누전방지 조치도 확인해 주세요.",
)

GENERAL_SITE_REPLIES = (
    "네, 알겠습니다.",
    "네, 확인했습니다. 조치하겠습니다.",
    "네 알겠습니다. 이미 조치했습니다.",
    "네, 말씀하신 사항은 이미 조치했습니다.",
    "네, 확인 후 현장에 반영했습니다.",
)

MANAGER_SITE_REPLIES = (
    "네, 알겠습니다. 소장점검 시 다시 확인하겠습니다.",
    "네, 점검 결과에 반영하고 조치했습니다.",
    "네 알겠습니다. 지적사항은 이미 조치했습니다.",
    "네, 현장 전반을 다시 확인하겠습니다.",
)

RAIN_SITE_REPLIES = (
    "네, 알겠습니다. 빗물 고임 제거와 미끄럼방지 조치를 완료했습니다.",
    "네, 통행로 물기를 제거하고 근로자 미끄럼방지 조치를 했습니다.",
    "네 알겠습니다. 배수상태와 누전방지 조치까지 확인했습니다.",
    "네, 우천 작업구간을 점검했고 필요한 조치를 이미 완료했습니다.",
)

MANAGER_RAIN_SITE_REPLIES = (
    "네, 알겠습니다. 소장점검으로 배수와 미끄럼방지 조치를 확인했습니다.",
    "네, 빗물 고임을 제거하고 통행로 안전조치를 완료했습니다.",
    "네 알겠습니다. 우천 관련 지적사항은 이미 조치했습니다.",
)


@dataclass(frozen=True)
class RepairPlan:
    approval_history_id: int
    document_id: int
    instance_id: int
    requirement_id: int
    requirement_code: str
    work_date: date
    rainfall_mm: float
    approval_action_by_user_id: int
    approval_action_type: str
    approval_action_at: datetime
    old_approval_comment: str
    corrected_hq_comment: str
    matching_review_history_id: int | None
    reply_user_id: int
    reply_user_login: str
    reply_user_name: str
    reply_text: str
    reply_at: datetime


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _parse_utc_naive(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _is_lunch_kst(value: datetime) -> bool:
    local = value.replace(tzinfo=timezone.utc).astimezone(KST)
    minute = local.hour * 60 + local.minute
    return 11 * 60 + 30 <= minute <= 13 * 60


def _work_date(document: Document, instance: DocumentInstance) -> date:
    if document.period_start is not None:
        return document.period_start
    if instance.period_start is not None:
        return instance.period_start
    source = document.uploaded_at or document.created_at
    return source.replace(tzinfo=timezone.utc).astimezone(KST).date()


def _pick_hq_comment(*, requirement_code: str, rain_mm: float, rng: random.Random) -> str:
    if rain_mm > 0:
        pool = RAIN_HQ_COMMENTS_BY_TYPE.get(requirement_code, FALLBACK_RAIN_HQ_COMMENTS)
    else:
        pool = GENERAL_HQ_COMMENTS_BY_TYPE.get(requirement_code, FALLBACK_HQ_COMMENTS)
    return rng.choice(pool)


def _pick_site_reply(*, requirement_code: str, rain_mm: float, rng: random.Random) -> str:
    if rain_mm > 0 and requirement_code == MANAGER_REQUIREMENT_CODE:
        pool = MANAGER_RAIN_SITE_REPLIES
    elif rain_mm > 0:
        pool = RAIN_SITE_REPLIES
    elif requirement_code == MANAGER_REQUIREMENT_CODE:
        pool = MANAGER_SITE_REPLIES
    else:
        pool = GENERAL_SITE_REPLIES
    return rng.choice(pool)


def _choose_reply_at(*, approval_at: datetime, cutoff: datetime, rng: random.Random) -> datetime:
    if approval_at >= cutoff:
        raise RuntimeError(
            f"approval {approval_at.isoformat()} has no reply window before cutoff {cutoff.isoformat()}"
        )

    for _ in range(100):
        candidate = approval_at + timedelta(
            seconds=rng.randint(5 * 60, 35 * 60),
            microseconds=rng.randrange(0, 1_000_000),
        )
        if _is_lunch_kst(candidate):
            local = candidate.replace(tzinfo=timezone.utc).astimezone(KST)
            local = local.replace(
                hour=13,
                minute=rng.randint(1, 9),
                second=rng.randint(0, 59),
                microsecond=rng.randrange(0, 1_000_000),
            )
            candidate = local.astimezone(timezone.utc).replace(tzinfo=None)
        if approval_at < candidate <= cutoff and not _is_lunch_kst(candidate):
            return candidate

    # Only relevant when an explicit cutoff is very close to the approval.  Walk
    # the small remaining window deterministically instead of silently crossing
    # lunch or creating a future reply.
    candidate = approval_at + timedelta(seconds=1)
    while candidate <= cutoff and candidate <= approval_at + timedelta(hours=6):
        if not _is_lunch_kst(candidate):
            return candidate
        candidate += timedelta(seconds=1)
    raise RuntimeError(f"could not choose a valid reply time after approval {approval_at.isoformat()}")


def _all_fields(row: Any) -> dict[str, Any]:
    return {
        column.name: _json_value(getattr(row, column.name))
        for column in row.__table__.columns
    }


def _rows_payload(rows: Iterable[Any]) -> list[dict[str, Any]]:
    return [_all_fields(row) for row in rows]


def _plan_payload(plan: RepairPlan) -> dict[str, Any]:
    return {
        name: _json_value(getattr(plan, name))
        for name in plan.__dataclass_fields__
    }


def _table_counts(db) -> dict[str, int]:
    return {
        "documents": db.query(Document).count(),
        "document_upload_histories": db.query(DocumentUploadHistory).count(),
        "approval_histories": db.query(ApprovalHistory).count(),
        "document_review_histories": db.query(DocumentReviewHistory).count(),
        "document_comments": db.query(DocumentComment).count(),
        "document_comment_site_acks": db.query(DocumentCommentSiteAck).count(),
    }


def _site_status_counts(db, *, site_id: int) -> dict[str, int]:
    rows = db.query(Document.current_status).filter(Document.site_id == site_id).all()
    return dict(Counter(str(status) for (status,) in rows))


def _site_workflow_counts(db, *, site_id: int) -> dict[str, int]:
    rows = db.query(DocumentInstance.workflow_status).filter(DocumentInstance.site_id == site_id).all()
    return dict(Counter(str(status) for (status,) in rows))


def _find_exact_corrupted_review(
    db,
    *,
    approval: ApprovalHistory,
    document: Document,
) -> DocumentReviewHistory | None:
    if document.instance_id is None:
        raise RuntimeError(f"document {document.id}: instance_id missing")
    candidates = (
        db.query(DocumentReviewHistory)
        .filter(
            DocumentReviewHistory.document_id == document.id,
            DocumentReviewHistory.instance_id == document.instance_id,
            DocumentReviewHistory.action_by_user_id == approval.action_by_user_id,
            DocumentReviewHistory.action_type == ReviewAction.APPROVE,
            DocumentReviewHistory.comment == CORRUPTED_COMMENT,
        )
        .all()
    )
    exact = [
        row
        for row in candidates
        if abs((row.action_at - approval.action_at).total_seconds()) <= REVIEW_MATCH_TOLERANCE_SECONDS
    ]
    if len(exact) > 1:
        raise RuntimeError(
            f"approval {approval.id}: multiple exact corrupted review histories {[row.id for row in exact]}"
        )
    return exact[0] if exact else None


def _validate_target_count(count: int) -> None:
    if count not in {0, EXPECTED_INITIAL_TARGETS}:
        raise RuntimeError(
            f"refusing partial/drifted target set: expected 0 or {EXPECTED_INITIAL_TARGETS}, found {count}"
        )


def _validate_site_user(db, *, site: Site, login_id: str, expected_name: str) -> User:
    user = db.query(User).filter(User.login_id == login_id).one_or_none()
    if user is None:
        raise RuntimeError(f"required site user {login_id!r} not found")
    if (
        user.name != expected_name
        or user.role != Role.SITE
        or int(user.site_id or -1) != int(site.id)
        or not user.is_active
    ):
        raise RuntimeError(
            f"invalid site user {login_id}: name={user.name!r}, role={user.role!r}, "
            f"site_id={user.site_id!r}, active={user.is_active!r}"
        )
    return user


def build_plan(
    db,
    *,
    site: Site,
    manager: User,
    safety_manager: User,
    cutoff: datetime,
    seed: int,
) -> list[RepairPlan]:
    rows = (
        db.query(ApprovalHistory, Document, DocumentInstance, DocumentRequirement)
        .join(Document, Document.id == ApprovalHistory.document_id)
        .join(DocumentInstance, DocumentInstance.id == Document.instance_id)
        .join(DocumentRequirement, DocumentRequirement.id == DocumentInstance.selected_requirement_id)
        .filter(
            Document.site_id == site.id,
            ApprovalHistory.action_type == ApprovalAction.APPROVE,
            ApprovalHistory.comment == CORRUPTED_COMMENT,
        )
        .order_by(ApprovalHistory.id.asc())
        .all()
    )
    _validate_target_count(len(rows))
    if not rows:
        return []

    document_ids = [int(document.id) for _, document, _, _ in rows]
    if len(set(document_ids)) != len(document_ids):
        raise RuntimeError("corrupted target set contains multiple approvals for one document")

    # A previous partial/manual run must not cause a second reply attributed to
    # either requested site user.  Normal script execution is transactional, so
    # any such row means the live state needs a fresh human review first.
    assigned_reply_rows = (
        db.query(DocumentComment.id, DocumentComment.document_id, DocumentComment.user_id)
        .filter(
            DocumentComment.document_id.in_(document_ids),
            DocumentComment.user_id.in_([int(manager.id), int(safety_manager.id)]),
        )
        .all()
    )
    if assigned_reply_rows:
        raise RuntimeError(
            "refusing target documents that already contain replies by site02/site03: "
            f"{[(int(row.id), int(row.document_id), int(row.user_id)) for row in assigned_reply_rows]}"
        )

    plans: list[RepairPlan] = []
    matched_review_ids: set[int] = set()
    for approval, document, instance, requirement in rows:
        if document.current_status != DocumentStatus.APPROVED:
            raise RuntimeError(f"document {document.id}: status changed to {document.current_status!r}")
        if instance.workflow_status != WorkflowStatus.APPROVED:
            raise RuntimeError(f"document {document.id}: workflow changed to {instance.workflow_status!r}")
        if int(instance.site_id) != int(site.id):
            raise RuntimeError(f"document {document.id}: instance site mismatch")
        # One legacy DAILY_TBM instance points at an equivalent requirement row
        # owned by an older duplicate site.  Document + instance site and all
        # three type codes remain the authoritative target guards; repairing
        # that historical requirement FK is intentionally outside this task.
        code = str(requirement.code or "").strip().upper()
        if not code:
            raise RuntimeError(f"document {document.id}: requirement code missing")
        if str(instance.document_type_code or "").strip().upper() != code:
            raise RuntimeError(f"document {document.id}: instance/requirement code mismatch")
        if str(document.document_type or "").strip().upper() != code:
            raise RuntimeError(f"document {document.id}: document/requirement code mismatch")

        matched_review = _find_exact_corrupted_review(db, approval=approval, document=document)
        if matched_review is not None:
            if int(matched_review.id) in matched_review_ids:
                raise RuntimeError(f"review history {matched_review.id}: matched twice")
            matched_review_ids.add(int(matched_review.id))

        work_day = _work_date(document, instance)
        rain_mm = float(CHEONGNA_RAIN_MM_BY_DATE.get(work_day, 0.0))
        rng = random.Random(int(seed) + int(approval.id) * 104_729 + int(document.id) * 7_919)
        corrected = _pick_hq_comment(requirement_code=code, rain_mm=rain_mm, rng=rng)
        reply = _pick_site_reply(requirement_code=code, rain_mm=rain_mm, rng=rng)
        reply_at = _choose_reply_at(approval_at=approval.action_at, cutoff=cutoff, rng=rng)
        reply_user = manager if code == MANAGER_REQUIREMENT_CODE else safety_manager
        plans.append(
            RepairPlan(
                approval_history_id=int(approval.id),
                document_id=int(document.id),
                instance_id=int(instance.id),
                requirement_id=int(requirement.id),
                requirement_code=code,
                work_date=work_day,
                rainfall_mm=rain_mm,
                approval_action_by_user_id=int(approval.action_by_user_id),
                approval_action_type=str(approval.action_type),
                approval_action_at=approval.action_at,
                old_approval_comment=str(approval.comment),
                corrected_hq_comment=corrected,
                matching_review_history_id=(int(matched_review.id) if matched_review is not None else None),
                reply_user_id=int(reply_user.id),
                reply_user_login=str(reply_user.login_id),
                reply_user_name=str(reply_user.name),
                reply_text=reply,
                reply_at=reply_at,
            )
        )

    manager_count = sum(plan.requirement_code == MANAGER_REQUIREMENT_CODE for plan in plans)
    other_count = len(plans) - manager_count
    if manager_count != EXPECTED_MANAGER_TARGETS or other_count != EXPECTED_OTHER_TARGETS:
        raise RuntimeError(
            f"unexpected author split: manager={manager_count}, other={other_count}; "
            f"expected {EXPECTED_MANAGER_TARGETS}/{EXPECTED_OTHER_TARGETS}"
        )
    if len(matched_review_ids) != EXPECTED_MATCHED_CORRUPTED_REVIEWS:
        raise RuntimeError(
            f"unexpected exact corrupted review matches: {len(matched_review_ids)}; "
            f"expected {EXPECTED_MATCHED_CORRUPTED_REVIEWS}"
        )

    site_corrupted_review_ids = {
        int(row_id)
        for (row_id,) in (
            db.query(DocumentReviewHistory.id)
            .join(Document, Document.id == DocumentReviewHistory.document_id)
            .filter(
                Document.site_id == site.id,
                DocumentReviewHistory.action_type == ReviewAction.APPROVE,
                DocumentReviewHistory.comment == CORRUPTED_COMMENT,
            )
            .all()
        )
    }
    if site_corrupted_review_ids != matched_review_ids:
        raise RuntimeError(
            "found corrupted review histories without an exact approval event match: "
            f"all={sorted(site_corrupted_review_ids)}, matched={sorted(matched_review_ids)}"
        )
    return plans


def _capture_target_state(db, *, target_document_ids: list[int]) -> dict[str, Any]:
    if not target_document_ids:
        return {
            "documents": [],
            "instances": [],
            "upload_histories": [],
            "approval_histories": [],
            "review_histories": [],
            "document_comments": [],
        }
    documents = db.query(Document).filter(Document.id.in_(target_document_ids)).order_by(Document.id).all()
    instance_ids = [int(row.instance_id) for row in documents if row.instance_id is not None]
    return {
        "documents": _rows_payload(documents),
        "instances": _rows_payload(
            db.query(DocumentInstance).filter(DocumentInstance.id.in_(instance_ids)).order_by(DocumentInstance.id).all()
        ),
        "upload_histories": _rows_payload(
            db.query(DocumentUploadHistory)
            .filter(DocumentUploadHistory.document_id.in_(target_document_ids))
            .order_by(DocumentUploadHistory.id)
            .all()
        ),
        "approval_histories": _rows_payload(
            db.query(ApprovalHistory)
            .filter(ApprovalHistory.document_id.in_(target_document_ids))
            .order_by(ApprovalHistory.id)
            .all()
        ),
        "review_histories": _rows_payload(
            db.query(DocumentReviewHistory)
            .filter(DocumentReviewHistory.document_id.in_(target_document_ids))
            .order_by(DocumentReviewHistory.id)
            .all()
        ),
        "document_comments": _rows_payload(
            db.query(DocumentComment)
            .filter(DocumentComment.document_id.in_(target_document_ids))
            .order_by(DocumentComment.id)
            .all()
        ),
    }


def _snapshot_payload(
    db,
    *,
    site: Site,
    plans: list[RepairPlan],
    manager: User,
    safety_manager: User,
    cutoff: datetime,
    seed: int,
) -> dict[str, Any]:
    target_ids = [plan.document_id for plan in plans]
    reply_users = [
        {
            "id": int(user.id),
            "login_id": str(user.login_id),
            "name": str(user.name),
            "role": str(user.role),
            "site_id": int(user.site_id),
            "is_active": bool(user.is_active),
        }
        for user in (manager, safety_manager)
    ]
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": str(Path(settings.sqlite_path).resolve()),
        "site": _all_fields(site),
        "rain_source": {
            "source_script": "scripts/backfill_c18_approval_comments.py",
            "location": "Cheongna 37.53,126.64 / Asia/Seoul",
            "dates_with_precipitation": len(CHEONGNA_RAIN_MM_BY_DATE),
        },
        "cutoff_utc": cutoff.isoformat(),
        "seed": int(seed),
        "counts": _table_counts(db),
        "site_status_counts": _site_status_counts(db, site_id=int(site.id)),
        "site_workflow_counts": _site_workflow_counts(db, site_id=int(site.id)),
        # Never copy password hashes or other authentication fields into an
        # operational snapshot manifest.
        "reply_users": reply_users,
        "plans": [_plan_payload(plan) for plan in plans],
        "target_state": _capture_target_state(db, target_document_ids=target_ids),
    }


def _backup_sqlite(destination: Path) -> None:
    source = Path(settings.sqlite_path).resolve()
    if not source.exists():
        raise RuntimeError(f"SQLite database not found: {source}")
    if source == destination.resolve():
        raise RuntimeError("backup destination must differ from source database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_value),
        encoding="utf-8",
    )


def apply_plan(db, *, plans: list[RepairPlan]) -> dict[str, Any]:
    created_comment_ids: list[int] = []
    updated_approval_ids: list[int] = []
    updated_review_ids: list[int] = []

    for plan in plans:
        approval = (
            db.query(ApprovalHistory)
            .filter(ApprovalHistory.id == plan.approval_history_id)
            .one()
        )
        if (
            int(approval.document_id) != plan.document_id
            or int(approval.action_by_user_id) != plan.approval_action_by_user_id
            or str(approval.action_type) != plan.approval_action_type
            or approval.action_at != plan.approval_action_at
            or approval.comment != CORRUPTED_COMMENT
        ):
            raise RuntimeError(f"approval {approval.id}: changed after planning")

        approval.comment = plan.corrected_hq_comment
        db.add(approval)
        updated_approval_ids.append(int(approval.id))

        if plan.matching_review_history_id is not None:
            review = (
                db.query(DocumentReviewHistory)
                .filter(DocumentReviewHistory.id == plan.matching_review_history_id)
                .one()
            )
            if (
                int(review.document_id) != plan.document_id
                or int(review.instance_id) != plan.instance_id
                or int(review.action_by_user_id) != plan.approval_action_by_user_id
                or review.action_type != ReviewAction.APPROVE
                or review.comment != CORRUPTED_COMMENT
                or abs((review.action_at - plan.approval_action_at).total_seconds())
                > REVIEW_MATCH_TOLERANCE_SECONDS
            ):
                raise RuntimeError(f"review history {review.id}: changed after planning")
            review.comment = plan.corrected_hq_comment
            db.add(review)
            updated_review_ids.append(int(review.id))

        reply = DocumentComment(
            document_id=plan.document_id,
            instance_id=plan.instance_id,
            user_id=plan.reply_user_id,
            user_role="SITE",
            comment_text=plan.reply_text,
            created_at=plan.reply_at,
        )
        db.add(reply)
        db.flush()
        created_comment_ids.append(int(reply.id))

    if len(created_comment_ids) != len(plans) or len(set(created_comment_ids)) != len(plans):
        raise RuntimeError("reply insert count/id uniqueness check failed")
    return {
        "updated_approval_ids": updated_approval_ids,
        "updated_review_ids": updated_review_ids,
        "created_comment_ids": created_comment_ids,
    }


def _indexed(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["id"]): row for row in rows}


def verify(
    db,
    *,
    site: Site,
    plans: list[RepairPlan],
    baseline: dict[str, Any],
    result: dict[str, Any],
    cutoff: datetime,
) -> dict[str, Any]:
    db.flush()
    target_ids = [plan.document_id for plan in plans]
    current = _capture_target_state(db, target_document_ids=target_ids)
    before = baseline["target_state"]

    errors: list[str] = []
    for key in ("documents", "instances", "upload_histories"):
        if current[key] != before[key]:
            errors.append(f"{key}_changed")

    plan_by_approval = {plan.approval_history_id: plan for plan in plans}
    before_approvals = _indexed(before["approval_histories"])
    after_approvals = _indexed(current["approval_histories"])
    if before_approvals.keys() != after_approvals.keys():
        errors.append("approval_history_ids_changed")
    else:
        for row_id, original in before_approvals.items():
            expected = dict(original)
            plan = plan_by_approval.get(row_id)
            if plan is not None:
                expected["comment"] = plan.corrected_hq_comment
            if after_approvals[row_id] != expected:
                errors.append(f"approval_history_{row_id}_unexpected_change")

    plan_by_review = {
        int(plan.matching_review_history_id): plan
        for plan in plans
        if plan.matching_review_history_id is not None
    }
    before_reviews = _indexed(before["review_histories"])
    after_reviews = _indexed(current["review_histories"])
    if before_reviews.keys() != after_reviews.keys():
        errors.append("review_history_ids_changed")
    else:
        for row_id, original in before_reviews.items():
            expected = dict(original)
            plan = plan_by_review.get(row_id)
            if plan is not None:
                expected["comment"] = plan.corrected_hq_comment
            if after_reviews[row_id] != expected:
                errors.append(f"review_history_{row_id}_unexpected_change")

    before_comments = _indexed(before["document_comments"])
    after_comments = _indexed(current["document_comments"])
    for row_id, original in before_comments.items():
        if after_comments.get(row_id) != original:
            errors.append(f"existing_document_comment_{row_id}_changed")

    created_ids = [int(value) for value in result["created_comment_ids"]]
    if len(created_ids) != len(plans) or set(after_comments) != set(before_comments) | set(created_ids):
        errors.append("document_comment_id_set_mismatch")

    plan_by_created_id = dict(zip(created_ids, plans, strict=True))
    reply_not_after_approval: list[int] = []
    reply_lunch: list[int] = []
    reply_future: list[int] = []
    reply_payload_errors: list[int] = []
    for comment_id, plan in plan_by_created_id.items():
        actual = after_comments.get(comment_id)
        if actual is None:
            reply_payload_errors.append(comment_id)
            continue
        expected_fields = {
            "document_id": plan.document_id,
            "instance_id": plan.instance_id,
            "user_id": plan.reply_user_id,
            "user_role": "SITE",
            "comment_text": plan.reply_text,
            "created_at": plan.reply_at.isoformat(),
        }
        if any(actual.get(key) != value for key, value in expected_fields.items()):
            reply_payload_errors.append(comment_id)
        if plan.reply_at <= plan.approval_action_at:
            reply_not_after_approval.append(comment_id)
        if _is_lunch_kst(plan.reply_at):
            reply_lunch.append(comment_id)
        if plan.reply_at > cutoff:
            reply_future.append(comment_id)

    after_counts = _table_counts(db)
    expected_counts = dict(baseline["counts"])
    expected_counts["document_comments"] += len(plans)
    if after_counts != expected_counts:
        errors.append("table_counts_changed_unexpectedly")
    after_status = _site_status_counts(db, site_id=int(site.id))
    after_workflow = _site_workflow_counts(db, site_id=int(site.id))
    if after_status != baseline["site_status_counts"]:
        errors.append("site_status_counts_changed")
    if after_workflow != baseline["site_workflow_counts"]:
        errors.append("site_workflow_counts_changed")

    corrupted_approvals = (
        db.query(ApprovalHistory)
        .join(Document, Document.id == ApprovalHistory.document_id)
        .filter(
            Document.site_id == site.id,
            ApprovalHistory.action_type == ApprovalAction.APPROVE,
            ApprovalHistory.comment == CORRUPTED_COMMENT,
        )
        .count()
    )
    corrupted_reviews = (
        db.query(DocumentReviewHistory)
        .join(Document, Document.id == DocumentReviewHistory.document_id)
        .filter(
            Document.site_id == site.id,
            DocumentReviewHistory.action_type == ReviewAction.APPROVE,
            DocumentReviewHistory.comment == CORRUPTED_COMMENT,
        )
        .count()
    )
    if corrupted_approvals:
        errors.append("corrupted_approval_comments_remain")
    if corrupted_reviews:
        errors.append("corrupted_review_comments_remain")
    if reply_not_after_approval:
        errors.append("reply_not_after_approval")
    if reply_lunch:
        errors.append("reply_in_kst_lunch")
    if reply_future:
        errors.append("reply_after_cutoff")
    if reply_payload_errors:
        errors.append("reply_payload_mismatch")

    verification = {
        "target_count": len(plans),
        "updated_approval_count": len(result["updated_approval_ids"]),
        "updated_review_count": len(result["updated_review_ids"]),
        "created_reply_count": len(created_ids),
        "manager_reply_count": sum(plan.reply_user_login == MANAGER_LOGIN for plan in plans),
        "safety_manager_reply_count": sum(plan.reply_user_login == SAFETY_MANAGER_LOGIN for plan in plans),
        "rain_target_count": sum(plan.rainfall_mm > 0 for plan in plans),
        "hq_comment_variant_count": len({plan.corrected_hq_comment for plan in plans}),
        "site_reply_variant_count": len({plan.reply_text for plan in plans}),
        "corrupted_approval_count": corrupted_approvals,
        "corrupted_review_count": corrupted_reviews,
        "reply_not_after_approval_ids": reply_not_after_approval,
        "reply_lunch_ids": reply_lunch,
        "reply_future_ids": reply_future,
        "reply_payload_error_ids": reply_payload_errors,
        "counts": after_counts,
        "site_status_counts": after_status,
        "site_workflow_counts": after_workflow,
        "errors": errors,
    }
    if errors:
        raise RuntimeError(f"post-apply verification failed: {verification}")
    return verification


def _print_plan(plans: list[RepairPlan], *, cutoff: datetime) -> None:
    print(f"cutoff_utc={cutoff.isoformat()}")
    print(f"target_approvals={len(plans)}")
    if not plans:
        return
    print(f"manager_replies={sum(plan.reply_user_login == MANAGER_LOGIN for plan in plans)}")
    print(f"safety_manager_replies={sum(plan.reply_user_login == SAFETY_MANAGER_LOGIN for plan in plans)}")
    print(f"matched_corrupted_reviews={sum(plan.matching_review_history_id is not None for plan in plans)}")
    print(f"rain_targets={sum(plan.rainfall_mm > 0 for plan in plans)}")
    print(f"hq_comment_variants={len({plan.corrected_hq_comment for plan in plans})}")
    print(f"site_reply_variants={len({plan.reply_text for plan in plans})}")
    sample = plans[:5] + plans[-5:] if len(plans) > 10 else plans
    for plan in sample:
        print(
            "plan",
            f"approval={plan.approval_history_id}",
            f"document={plan.document_id}",
            plan.requirement_code,
            plan.approval_action_at.isoformat(),
            "->",
            plan.reply_at.isoformat(),
            plan.reply_user_name,
            f"rain={plan.rainfall_mm}",
            plan.corrected_hq_comment,
            "/",
            plan.reply_text,
        )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="변경 없이 대상과 결정적 계획만 출력")
    mode.add_argument("--apply", action="store_true", help="DB/JSON 스냅샷 후 한 트랜잭션으로 적용")
    parser.add_argument("--confirm", default="", help="apply 확인 토큰")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of-utc", default=None, help="답변시각 상한(ISO-8601 UTC, 재현성용)")
    parser.add_argument(
        "--snapshot-dir",
        default="/home/ubuntu/besma-ops-backups/c18-corrupted-approval-comments",
        help="apply 전 DB/JSON 스냅샷 및 적용 manifest 저장 폴더",
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
        if site is None:
            raise RuntimeError(f"C18 site_code {SITE_CODE!r} not found")
        site_name = str(site.site_name or "")
        if "C18" not in site_name.upper() or "청라" not in site_name:
            raise RuntimeError(f"refusing unexpected site {site.id}/{site.site_code}/{site_name!r}")

        manager = _validate_site_user(db, site=site, login_id=MANAGER_LOGIN, expected_name=MANAGER_NAME)
        safety_manager = _validate_site_user(
            db,
            site=site,
            login_id=SAFETY_MANAGER_LOGIN,
            expected_name=SAFETY_MANAGER_NAME,
        )
        plans = build_plan(
            db,
            site=site,
            manager=manager,
            safety_manager=safety_manager,
            cutoff=cutoff,
            seed=int(args.seed),
        )
        print(f"database={Path(settings.sqlite_path).resolve()}")
        print(f"site={site.id}/{site.site_code}/{site.site_name}")
        print(f"before_counts={_table_counts(db)}")
        print(f"before_site_status={_site_status_counts(db, site_id=int(site.id))}")
        print(f"before_site_workflow={_site_workflow_counts(db, site_id=int(site.id))}")
        _print_plan(plans, cutoff=cutoff)

        if not plans:
            db.rollback()
            print("NOOP_ALREADY_REPAIRED")
            return 0
        if args.dry_run:
            db.rollback()
            print("DRY_RUN_OK")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = Path(args.snapshot_dir).expanduser().resolve()
        snapshot_json = snapshot_dir / f"before_c18_corrupted_approval_comments_{stamp}.json"
        backup_db = snapshot_dir / f"besma_before_c18_corrupted_approval_comments_{stamp}.db"
        manifest_json = snapshot_dir / f"repair_c18_corrupted_approval_comments_{stamp}.json"
        baseline = _snapshot_payload(
            db,
            site=site,
            plans=plans,
            manager=manager,
            safety_manager=safety_manager,
            cutoff=cutoff,
            seed=int(args.seed),
        )
        _write_json(snapshot_json, baseline)
        _backup_sqlite(backup_db)
        prepared_manifest = {
            "state": "prepared",
            "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
            "site_id": int(site.id),
            "site_code": site.site_code,
            "seed": int(args.seed),
            "cutoff_utc": cutoff.isoformat(),
            "snapshot_json": str(snapshot_json),
            "backup_db": str(backup_db),
            "plans": [_plan_payload(plan) for plan in plans],
        }
        _write_json(manifest_json, prepared_manifest)
        print(f"snapshot_json={snapshot_json}")
        print(f"backup_db={backup_db}")
        print(f"prepared_manifest_json={manifest_json}")

        result = apply_plan(db, plans=plans)
        verification_before_commit = verify(
            db,
            site=site,
            plans=plans,
            baseline=baseline,
            result=result,
            cutoff=cutoff,
        )
        db.commit()
        verification_after_commit = verify(
            db,
            site=site,
            plans=plans,
            baseline=baseline,
            result=result,
            cutoff=cutoff,
        )
        manifest = copy.deepcopy(prepared_manifest)
        manifest.update(
            {
                "state": "applied",
                "applied_at_utc": datetime.now(timezone.utc).isoformat(),
                "result": result,
                "verification_before_commit": verification_before_commit,
                "verification_after_commit": verification_after_commit,
            }
        )
        _write_json(manifest_json, manifest)
        print(f"result={result}")
        print(f"verification={verification_after_commit}")
        print(f"manifest_json={manifest_json}")
        print("APPLY_OK")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
