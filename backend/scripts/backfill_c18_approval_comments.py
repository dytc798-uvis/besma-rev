"""C18 삼성인정제 문서취합의 누락 승인 코멘트를 안전하게 보강한다.

운영 사용 예:

    cd /home/ubuntu/besma-rev/backend
    PYTHONPATH=. .venv/bin/python scripts/backfill_c18_approval_comments.py \
      --dry-run --as-of-utc 2026-07-13T08:00:00

    PYTHONPATH=. .venv/bin/python scripts/backfill_c18_approval_comments.py \
      --apply --confirm APPROVE_C18_MISSING_COMMENTS \
      --as-of-utc 2026-07-13T08:00:00

기존의 비어 있지 않은 승인 코멘트와 승인 시각은 절대 변경하지 않는다. 승인
코멘트가 없는 문서만 처리하며, 아직 SUBMITTED인 문서는 Document와
DocumentInstance의 상태 및 두 승인 이력을 한 트랜잭션으로 APPROVED에 맞춘다.
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import app.main  # noqa: F401  # 모든 ORM 모델 등록

from app.config.settings import settings
from app.core.database import SessionLocal
from app.modules.approvals.models import ApprovalAction, ApprovalHistory
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_settings.models import DocumentRequirement
from app.modules.document_submissions.models import DocumentReviewHistory, ReviewAction
from app.modules.document_submissions.service import transition_instance_workflow_status
from app.modules.documents.feedback_loop_service import sync_feedback_loop_from_workflow
from app.modules.documents.models import Document, DocumentStatus, DocumentUploadHistory
from app.modules.sites.models import Site
from app.modules.users.models import User


CONFIRM_TOKEN = "APPROVE_C18_MISSING_COMMENTS"
DEFAULT_SITE_CODE = "24025"
LEGAL_REQUIREMENT_CODE = "LEGAL_COMPLIANCE_EVALUATION"
DEFAULT_SEED = 20260713
KST = timezone(timedelta(hours=9), name="KST")

# Open-Meteo Historical Weather API, daily precipitation_sum, 청라 좌표 근사
# (37.53, 126.64), Asia/Seoul. 조회일: 2026-07-13. 0mm 초과 날짜만 보관한다.
# https://open-meteo.com/en/docs/historical-weather-api
RAIN_MM_BY_DATE: dict[date, float] = {
    date.fromisoformat(day): mm
    for day, mm in {
        "2026-03-30": 1.4,
        "2026-03-31": 7.3,
        "2026-04-01": 0.2,
        "2026-04-04": 1.0,
        "2026-04-05": 9.5,
        "2026-04-06": 1.0,
        "2026-04-09": 24.2,
        "2026-04-10": 4.4,
        "2026-04-20": 0.9,
        "2026-04-27": 12.5,
        "2026-04-28": 0.4,
        "2026-05-02": 1.1,
        "2026-05-03": 10.1,
        "2026-05-04": 0.1,
        "2026-05-07": 3.7,
        "2026-05-08": 0.4,
        "2026-05-11": 5.4,
        "2026-05-12": 2.5,
        "2026-05-14": 0.3,
        "2026-05-19": 0.5,
        "2026-05-20": 49.1,
        "2026-05-21": 17.8,
        "2026-05-23": 0.3,
        "2026-05-26": 3.8,
        "2026-05-27": 13.4,
        "2026-05-28": 2.1,
        "2026-06-04": 7.4,
        "2026-06-05": 0.4,
        "2026-06-07": 0.7,
        "2026-06-08": 1.1,
        "2026-06-10": 5.9,
        "2026-06-14": 1.7,
        "2026-06-15": 1.4,
        "2026-06-16": 1.0,
        "2026-06-17": 0.5,
        "2026-06-18": 0.7,
        "2026-06-19": 11.5,
        "2026-06-20": 70.7,
        "2026-06-22": 3.3,
        "2026-06-23": 0.5,
        "2026-06-25": 1.8,
        "2026-06-28": 0.2,
        "2026-06-29": 0.2,
        "2026-06-30": 0.2,
        "2026-07-01": 5.6,
        "2026-07-02": 4.1,
        "2026-07-03": 2.8,
        "2026-07-04": 0.6,
        "2026-07-05": 15.2,
        "2026-07-06": 17.5,
        "2026-07-07": 9.9,
        "2026-07-08": 11.3,
        "2026-07-09": 10.2,
        "2026-07-10": 41.5,
        "2026-07-13": 0.8,
    }.items()
}

GENERAL_COMMENTS = (
    "네 확인하였습니다. 감사합니다 안전작업부탁드립니다.",
    "문서 확인하였습니다. 작업 전 위험요인 공유와 안전수칙 준수 부탁드립니다.",
    "확인하였습니다. 보호구 착용과 작업구간 정리정돈을 철저히 해주시기 바랍니다.",
    "내용 확인했습니다. 무리한 작업 없이 안전하게 진행 부탁드립니다.",
    "검토 완료했습니다. TBM 시 주요 위험요인과 예방대책을 근로자에게 충분히 전파해 주세요.",
    "확인하였습니다. 작업 전 장비와 공도구 상태를 다시 한번 점검해 주시기 바랍니다.",
    "문서 확인했습니다. 작업순서 준수와 상호 신호체계를 철저히 유지해 주세요.",
    "수고하셨습니다. 현장 순회점검과 근로자 안전수칙 준수 확인 부탁드립니다.",
)

RAIN_COMMENTS = (
    "확인하였습니다. 빗물에 근로자 미끄럼방지 부탁드립니다.",
    "문서 확인했습니다. 우천으로 통로가 미끄러울 수 있으니 배수상태와 미끄럼방지 조치 확인 부탁드립니다.",
    "확인하였습니다. 비 온 뒤 작업발판과 계단의 물기를 제거하고 미끄럼 사고 예방에 유의해 주세요.",
    "검토 완료했습니다. 우천 시 이동통로 정리와 미끄럼방지 조치를 철저히 해주시기 바랍니다.",
    "확인했습니다. 빗물 고임을 즉시 정리하고 작업자 통행로의 미끄럼 위험을 점검해 주세요.",
    "수고하셨습니다. 우천 작업 시 미끄럼 예방과 전기기계·기구의 누전 방지 조치 부탁드립니다.",
)


@dataclass(frozen=True)
class ApprovalPlan:
    document_id: int
    instance_id: int
    uploaded_at: datetime
    action_at: datetime
    comment: str
    work_date: date
    rainfall_mm: float
    previous_document_status: str
    previous_workflow_status: str
    existing_blank_approval_id: int | None


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
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


def _latest_upload_at(db, document: Document) -> datetime:
    history_at = (
        db.query(DocumentUploadHistory.uploaded_at)
        .filter(DocumentUploadHistory.document_id == document.id)
        .order_by(DocumentUploadHistory.uploaded_at.desc().nullslast(), DocumentUploadHistory.id.desc())
        .first()
    )
    candidates = [document.uploaded_at, document.submitted_at]
    if history_at:
        candidates.append(history_at[0])
    present = [value for value in candidates if value is not None]
    if not present:
        raise RuntimeError(f"document {document.id}: upload timestamp missing")
    return max(present)


def _approval_local_time_samples(db, *, site_id: int) -> list[int]:
    rows = (
        db.query(ApprovalHistory.action_at)
        .join(Document, Document.id == ApprovalHistory.document_id)
        .filter(
            Document.site_id == site_id,
            ApprovalHistory.action_type == ApprovalAction.APPROVE,
        )
        .all()
    )
    samples: list[int] = []
    for (action_at,) in rows:
        local = action_at.replace(tzinfo=timezone.utc).astimezone(KST)
        if _is_lunch_kst(action_at) or not (7 <= local.hour <= 20):
            continue
        samples.append(local.hour * 60 * 60 + local.minute * 60 + local.second)
    if not samples:
        # 운영 이력이 전혀 없는 새 환경용 보수적 fallback. C18 운영에서는 사용되지 않는다.
        samples = [9 * 60 * 60 + 30 * 60, 10 * 60 * 60 + 20 * 60, 14 * 60 * 60, 17 * 60 * 60]
    return samples


def _choose_action_at(
    *,
    uploaded_at: datetime,
    cutoff: datetime,
    local_time_samples: list[int],
    rng: random.Random,
) -> datetime:
    if uploaded_at >= cutoff - timedelta(seconds=1):
        raise RuntimeError(
            f"upload {uploaded_at.isoformat()} has no valid approval window before cutoff {cutoff.isoformat()}"
        )

    uploaded_local = uploaded_at.replace(tzinfo=timezone.utc).astimezone(KST)
    for _ in range(500):
        # 기존 승인 시각의 KST 시·분 분포를 그대로 표본으로 쓰고 ±7분만 흔든다.
        seconds_of_day = rng.choice(local_time_samples) + rng.randint(-7 * 60, 7 * 60)
        seconds_of_day = max(7 * 60 * 60, min(20 * 60 * 60 + 59 * 60 + 59, seconds_of_day))
        hour, remainder = divmod(seconds_of_day, 60 * 60)
        minute, second = divmod(remainder, 60)
        candidate_local = uploaded_local.replace(
            hour=hour,
            minute=minute,
            second=second,
            microsecond=rng.randrange(0, 1_000_000),
        )
        if candidate_local <= uploaded_local:
            candidate_local += timedelta(days=1)
        candidate = candidate_local.astimezone(timezone.utc).replace(tzinfo=None)
        if uploaded_at < candidate <= cutoff and not _is_lunch_kst(candidate):
            return candidate

    # 최신 업로드처럼 기존 지연 표본이 cutoff를 넘는 경우, 가능한 구간 안에서만 무작위 선택한다.
    start = uploaded_at + timedelta(seconds=1)
    span_seconds = int((cutoff - start).total_seconds())
    for _ in range(300):
        candidate = start + timedelta(seconds=rng.randint(0, max(0, span_seconds)))
        local_hour = candidate.replace(tzinfo=timezone.utc).astimezone(KST).hour
        if 7 <= local_hour <= 20 and not _is_lunch_kst(candidate):
            return candidate
    raise RuntimeError(f"could not choose non-lunch approval time after {uploaded_at.isoformat()}")


def _work_date(document: Document, uploaded_at: datetime) -> date:
    if document.period_start is not None:
        return document.period_start
    return uploaded_at.replace(tzinfo=timezone.utc).astimezone(KST).date()


def _pick_comment(*, document: Document, work_date: date, rng: random.Random) -> tuple[str, float]:
    rain_mm = float(RAIN_MM_BY_DATE.get(work_date, 0.0))
    pool = RAIN_COMMENTS if rain_mm > 0 else GENERAL_COMMENTS
    return rng.choice(pool), rain_mm


def build_plan(db, *, site: Site, cutoff: datetime, seed: int) -> list[ApprovalPlan]:
    local_time_samples = _approval_local_time_samples(db, site_id=int(site.id))
    documents = db.query(Document).filter(Document.site_id == site.id).order_by(Document.id.asc()).all()
    plans: list[ApprovalPlan] = []

    for document in documents:
        approvals = (
            db.query(ApprovalHistory)
            .filter(
                ApprovalHistory.document_id == document.id,
                ApprovalHistory.action_type == ApprovalAction.APPROVE,
            )
            .order_by(ApprovalHistory.action_at.desc(), ApprovalHistory.id.desc())
            .all()
        )
        if any((row.comment or "").strip() for row in approvals):
            continue

        if document.current_status not in {DocumentStatus.APPROVED, DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW}:
            raise RuntimeError(
                f"document {document.id}: unsupported current status {document.current_status!r}"
            )
        if document.instance_id is None:
            raise RuntimeError(f"document {document.id}: instance_id missing")
        instance = db.query(DocumentInstance).filter(DocumentInstance.id == document.instance_id).first()
        if instance is None:
            raise RuntimeError(f"document {document.id}: instance {document.instance_id} missing")
        if document.current_status == DocumentStatus.APPROVED and instance.workflow_status != WorkflowStatus.APPROVED:
            raise RuntimeError(
                f"document {document.id}: approved document has workflow {instance.workflow_status!r}"
            )

        uploaded_at = _latest_upload_at(db, document)
        rng = random.Random(seed + int(document.id) * 7_919)
        action_at = _choose_action_at(
            uploaded_at=uploaded_at,
            cutoff=cutoff,
            local_time_samples=local_time_samples,
            rng=rng,
        )
        work_day = _work_date(document, uploaded_at)
        comment, rain_mm = _pick_comment(document=document, work_date=work_day, rng=rng)
        blank_id = int(approvals[0].id) if approvals else None
        plans.append(
            ApprovalPlan(
                document_id=int(document.id),
                instance_id=int(instance.id),
                uploaded_at=uploaded_at,
                action_at=action_at,
                comment=comment,
                work_date=work_day,
                rainfall_mm=rain_mm,
                previous_document_status=str(document.current_status),
                previous_workflow_status=str(instance.workflow_status),
                existing_blank_approval_id=blank_id,
            )
        )

    return plans


def _table_counts(db) -> dict[str, int]:
    return {
        "documents": db.query(Document).count(),
        "document_upload_histories": db.query(DocumentUploadHistory).count(),
        "approval_histories": db.query(ApprovalHistory).count(),
        "document_review_histories": db.query(DocumentReviewHistory).count(),
    }


def _site_status_counts(db, *, site_id: int) -> dict[str, int]:
    rows = (
        db.query(Document.current_status, Document.id)
        .filter(Document.site_id == site_id)
        .order_by(Document.id)
        .all()
    )
    return dict(Counter(str(status) for status, _ in rows))


def _snapshot_payload(db, *, site: Site, plans: list[ApprovalPlan], legal_rows: list[DocumentRequirement]) -> dict:
    target_ids = [plan.document_id for plan in plans]
    documents = db.query(Document).filter(Document.id.in_(target_ids)).order_by(Document.id).all() if target_ids else []
    instances = (
        db.query(DocumentInstance).filter(DocumentInstance.id.in_([plan.instance_id for plan in plans])).order_by(DocumentInstance.id).all()
        if plans
        else []
    )
    approvals = (
        db.query(ApprovalHistory).filter(ApprovalHistory.document_id.in_(target_ids)).order_by(ApprovalHistory.id).all()
        if target_ids
        else []
    )
    reviews = (
        db.query(DocumentReviewHistory)
        .filter(DocumentReviewHistory.document_id.in_(target_ids))
        .order_by(DocumentReviewHistory.id)
        .all()
        if target_ids
        else []
    )

    def fields(row, names: tuple[str, ...]) -> dict:
        return {name: _json_value(getattr(row, name, None)) for name in names}

    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "site": fields(site, ("id", "site_code", "site_name")),
        "counts": _table_counts(db),
        "site_status_counts": _site_status_counts(db, site_id=int(site.id)),
        "legal_requirements": [
            fields(row, ("id", "site_id", "code", "title", "is_enabled", "is_required", "updated_at"))
            for row in legal_rows
        ],
        "documents": [
            fields(row, ("id", "instance_id", "current_status", "uploaded_at", "submitted_at", "reviewed_at", "rejection_reason"))
            for row in documents
        ],
        "instances": [fields(row, ("id", "workflow_status", "updated_at")) for row in instances],
        "approval_histories": [
            fields(row, ("id", "document_id", "action_by_user_id", "action_type", "comment", "action_at"))
            for row in approvals
        ],
        "document_review_histories": [
            fields(
                row,
                (
                    "id",
                    "instance_id",
                    "document_id",
                    "action_by_user_id",
                    "action_type",
                    "comment",
                    "from_workflow_status",
                    "to_workflow_status",
                    "action_at",
                ),
            )
            for row in reviews
        ],
    }


def _backup_sqlite(destination: Path) -> None:
    source = Path(settings.sqlite_path).resolve()
    if not source.exists():
        raise RuntimeError(f"SQLite database not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_value), encoding="utf-8")


def _plan_dict(plan: ApprovalPlan) -> dict[str, Any]:
    return {name: _json_value(getattr(plan, name)) for name in plan.__dataclass_fields__}


def apply_plan(db, *, plans: list[ApprovalPlan], actor: User, legal_rows: list[DocumentRequirement]) -> dict:
    inserted_approval_ids: list[int] = []
    updated_blank_approval_ids: list[int] = []
    inserted_review_ids: list[int] = []
    status_changed_ids: list[int] = []

    for row in legal_rows:
        row.is_enabled = False
        db.add(row)

    for plan in plans:
        document = db.query(Document).filter(Document.id == plan.document_id).one()
        instance = db.query(DocumentInstance).filter(DocumentInstance.id == plan.instance_id).one()

        nonempty_approval = (
            db.query(ApprovalHistory)
            .filter(
                ApprovalHistory.document_id == document.id,
                ApprovalHistory.action_type == ApprovalAction.APPROVE,
                ApprovalHistory.comment.isnot(None),
                ApprovalHistory.comment != "",
            )
            .first()
        )
        if nonempty_approval is not None:
            raise RuntimeError(f"document {document.id}: approval comment appeared after planning")

        before_workflow = str(instance.workflow_status)
        if document.current_status != DocumentStatus.APPROVED:
            transition_instance_workflow_status(instance, action="approve")
            document.current_status = DocumentStatus.APPROVED
            document.rejection_reason = None
            status_changed_ids.append(int(document.id))
            sync_feedback_loop_from_workflow(
                db,
                inst=instance,
                doc_status=document.current_status,
                triggering_user_id=int(actor.id),
            )

        document.reviewed_at = plan.action_at
        db.add(document)
        db.add(instance)

        approval: ApprovalHistory | None = None
        if plan.existing_blank_approval_id is not None:
            approval = (
                db.query(ApprovalHistory)
                .filter(
                    ApprovalHistory.id == plan.existing_blank_approval_id,
                    ApprovalHistory.document_id == document.id,
                    ApprovalHistory.action_type == ApprovalAction.APPROVE,
                )
                .one()
            )
            approval.action_by_user_id = int(actor.id)
            approval.comment = plan.comment
            approval.action_at = plan.action_at
            updated_blank_approval_ids.append(int(approval.id))
        else:
            approval = ApprovalHistory(
                document_id=int(document.id),
                action_by_user_id=int(actor.id),
                action_type=ApprovalAction.APPROVE,
                comment=plan.comment,
                action_at=plan.action_at,
            )
            db.add(approval)
            db.flush()
            inserted_approval_ids.append(int(approval.id))

        review = (
            db.query(DocumentReviewHistory)
            .filter(
                DocumentReviewHistory.document_id == document.id,
                DocumentReviewHistory.action_type == ReviewAction.APPROVE,
            )
            .order_by(DocumentReviewHistory.action_at.desc(), DocumentReviewHistory.id.desc())
            .first()
        )
        if review is None:
            review = DocumentReviewHistory(
                instance_id=int(instance.id),
                document_id=int(document.id),
                action_by_user_id=int(actor.id),
                action_type=ReviewAction.APPROVE,
                comment=plan.comment,
                from_workflow_status=(
                    before_workflow if before_workflow != WorkflowStatus.APPROVED else WorkflowStatus.SUBMITTED
                ),
                to_workflow_status=WorkflowStatus.APPROVED,
                action_at=plan.action_at,
            )
            db.add(review)
            db.flush()
            inserted_review_ids.append(int(review.id))

    db.commit()
    return {
        "inserted_approval_ids": inserted_approval_ids,
        "updated_blank_approval_ids": updated_blank_approval_ids,
        "inserted_review_ids": inserted_review_ids,
        "status_changed_document_ids": status_changed_ids,
    }


def verify(
    db,
    *,
    site: Site,
    expected_document_count: int,
    planned_document_ids: set[int],
) -> dict[str, Any]:
    documents = db.query(Document).filter(Document.site_id == site.id).all()
    missing: list[int] = []
    time_errors: list[int] = []
    lunch_errors: list[int] = []
    workflow_errors: list[int] = []

    for document in documents:
        approval = (
            db.query(ApprovalHistory)
            .filter(
                ApprovalHistory.document_id == document.id,
                ApprovalHistory.action_type == ApprovalAction.APPROVE,
                ApprovalHistory.comment.isnot(None),
                ApprovalHistory.comment != "",
            )
            .order_by(ApprovalHistory.action_at.desc(), ApprovalHistory.id.desc())
            .first()
        )
        if approval is None or document.current_status != DocumentStatus.APPROVED:
            missing.append(int(document.id))
            continue
        if int(document.id) in planned_document_ids:
            uploaded_at = _latest_upload_at(db, document)
            if approval.action_at <= uploaded_at:
                time_errors.append(int(document.id))
            if _is_lunch_kst(approval.action_at):
                lunch_errors.append(int(document.id))
        instance = db.query(DocumentInstance).filter(DocumentInstance.id == document.instance_id).first()
        if instance is None or instance.workflow_status != WorkflowStatus.APPROVED:
            workflow_errors.append(int(document.id))

    result = {
        "site_document_count": len(documents),
        "approved_status_count": sum(d.current_status == DocumentStatus.APPROVED for d in documents),
        "missing_approval_comment_ids": missing,
        "approval_not_after_upload_ids": time_errors,
        "approval_lunch_time_ids": lunch_errors,
        "workflow_not_approved_ids": workflow_errors,
        "legal_requirement_enabled_count": db.query(DocumentRequirement)
        .filter(
            DocumentRequirement.site_id == site.id,
            DocumentRequirement.code == LEGAL_REQUIREMENT_CODE,
            DocumentRequirement.is_enabled.is_(True),
        )
        .count(),
        "counts": _table_counts(db),
    }
    if len(documents) != expected_document_count or any(
        result[key]
        for key in (
            "missing_approval_comment_ids",
            "approval_not_after_upload_ids",
            "approval_lunch_time_ids",
            "workflow_not_approved_ids",
        )
    ) or result["legal_requirement_enabled_count"] != 0:
        raise RuntimeError(f"post-apply verification failed: {result}")
    return result


def _print_plan(plans: list[ApprovalPlan], *, cutoff: datetime) -> None:
    print(f"cutoff_utc={cutoff.isoformat()}")
    print(f"target_documents={len(plans)}")
    print(f"status_changes={sum(p.previous_document_status != DocumentStatus.APPROVED for p in plans)}")
    print(f"already_approved_missing_history={sum(p.previous_document_status == DocumentStatus.APPROVED for p in plans)}")
    print(f"rain_comments={sum(p.rainfall_mm > 0 for p in plans)}")
    print(f"comment_variants={len({p.comment for p in plans})}")
    for plan in (plans[:5] + plans[-5:] if len(plans) > 10 else plans):
        print(
            "plan",
            plan.document_id,
            plan.previous_document_status,
            plan.uploaded_at.isoformat(),
            "->",
            plan.action_at.isoformat(),
            plan.work_date.isoformat(),
            f"rain={plan.rainfall_mm}",
            plan.comment,
        )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="변경 없이 대상과 결과 계획만 출력")
    mode.add_argument("--apply", action="store_true", help="스냅샷 후 실제 적용")
    parser.add_argument("--confirm", default="", help="apply 확인 토큰")
    parser.add_argument("--site-code", default=DEFAULT_SITE_CODE)
    parser.add_argument("--actor-login", default="hq01")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--as-of-utc", default=None, help="승인 시각 상한(ISO-8601 UTC, 재현성용)")
    parser.add_argument(
        "--snapshot-dir",
        default="/home/ubuntu/besma-ops-backups/c18-approval-comments",
        help="apply 전 DB/JSON 스냅샷 저장 폴더",
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
        site = db.query(Site).filter(Site.site_code == args.site_code).one_or_none()
        if site is None:
            raise RuntimeError(f"site_code {args.site_code!r} not found")
        if "C18" not in (site.site_name or "").upper():
            raise RuntimeError(f"refusing non-C18 site: {site.site_name!r}")
        actor = db.query(User).filter(User.login_id == args.actor_login, User.is_active.is_(True)).one_or_none()
        if actor is None:
            raise RuntimeError(f"active actor {args.actor_login!r} not found")

        legal_rows = (
            db.query(DocumentRequirement)
            .filter(
                DocumentRequirement.site_id == site.id,
                DocumentRequirement.code == LEGAL_REQUIREMENT_CODE,
            )
            .order_by(DocumentRequirement.id)
            .all()
        )
        if len(legal_rows) != 1:
            raise RuntimeError(f"expected one C18 legal requirement, found {len(legal_rows)}")

        before_counts = _table_counts(db)
        before_status = _site_status_counts(db, site_id=int(site.id))
        expected_document_count = sum(before_status.values())
        plans = build_plan(db, site=site, cutoff=cutoff, seed=args.seed)
        print(f"site={site.id}/{site.site_code}/{site.site_name}")
        print(f"before_counts={before_counts}")
        print(f"before_site_status={before_status}")
        print(f"legal_requirement={legal_rows[0].id}/enabled={legal_rows[0].is_enabled}")
        _print_plan(plans, cutoff=cutoff)

        if args.dry_run:
            db.rollback()
            print("DRY_RUN_OK")
            return 0

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        snapshot_dir = Path(args.snapshot_dir).expanduser().resolve()
        snapshot_json = snapshot_dir / f"before_c18_approval_comments_{stamp}.json"
        backup_db = snapshot_dir / f"besma_before_c18_approval_comments_{stamp}.db"
        manifest_json = snapshot_dir / f"applied_c18_approval_comments_{stamp}.json"
        _write_json(snapshot_json, _snapshot_payload(db, site=site, plans=plans, legal_rows=legal_rows))
        _backup_sqlite(backup_db)
        print(f"snapshot_json={snapshot_json}")
        print(f"backup_db={backup_db}")

        result = apply_plan(db, plans=plans, actor=actor, legal_rows=legal_rows)
        verification = verify(
            db,
            site=site,
            expected_document_count=expected_document_count,
            planned_document_ids={plan.document_id for plan in plans},
        )
        manifest = {
            "applied_at_utc": datetime.now(timezone.utc).isoformat(),
            "site_id": int(site.id),
            "site_code": site.site_code,
            "actor_user_id": int(actor.id),
            "actor_login": actor.login_id,
            "seed": int(args.seed),
            "cutoff_utc": cutoff.isoformat(),
            "before_counts": before_counts,
            "before_site_status": before_status,
            "plans": [_plan_dict(plan) for plan in plans],
            "result": result,
            "verification": verification,
            "snapshot_json": str(snapshot_json),
            "backup_db": str(backup_db),
        }
        _write_json(manifest_json, manifest)
        print(f"manifest_json={manifest_json}")
        print(f"result={result}")
        print(f"verification={verification}")
        print("APPLY_OK")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
