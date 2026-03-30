from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.document_generation.constants import DocumentSourceType
from app.modules.document_generation.engine import (
    resolve_due_date,
    resolve_generation_slot,
    resolve_period_for_cycle,
)
from app.modules.document_generation.models import DocumentInstance, DocumentInstanceStatus, PeriodBasis
from app.modules.document_settings.constants import RuleStatusReason
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.document_settings.service import get_effective_rule
from app.modules.documents.models import Document


def _get_instance_by_key(
    db: Session,
    site_id: int,
    document_type_code: str,
    period_basis: str,
    period_start: date,
    period_end: date,
) -> DocumentInstance | None:
    return (
        db.query(DocumentInstance)
        .filter(
            DocumentInstance.site_id == site_id,
            DocumentInstance.document_type_code == document_type_code,
            DocumentInstance.period_basis == period_basis,
            DocumentInstance.period_start == period_start,
            DocumentInstance.period_end == period_end,
        )
        .first()
    )


def find_existing_auto_document(
    db: Session,
    site_id: int,
    document_type_code: str,
    period_start: date,
    period_end: date,
) -> Document | None:
    return (
        db.query(Document)
        .filter(
            Document.site_id == site_id,
            Document.document_type == document_type_code,
            Document.period_start == period_start,
            Document.period_end == period_end,
            Document.source_type == DocumentSourceType.AUTO,
        )
        .first()
    )


def create_document_for_period(
    db: Session,
    site_id: int,
    document_type_code: str,
    period_start: date,
    period_end: date,
    due_date: date,
    *,
    instance_id: int,
) -> Document:
    doc = Document(
        document_no=f"AUTO-{site_id}-{document_type_code}-{period_start.isoformat()}",
        title=f"[AUTO] {document_type_code} {period_start.isoformat()}",
        document_type=document_type_code,
        site_id=site_id,
        submitter_user_id=1,
        current_status="DRAFT",
        description="자동 생성 문서(초안)",
        period_start=period_start,
        period_end=period_end,
        due_date=due_date,
        source_type=DocumentSourceType.AUTO,
        version_no=1,
        instance_id=instance_id,
    )
    db.add(doc)
    db.flush()
    return doc


def _resolve_snapshot_context(
    document_type: DocumentTypeMaster | None,
    requirement: DocumentRequirement | None,
    master_cycle: SubmissionCycle | None,
    override_cycle: SubmissionCycle | None,
) -> dict:
    """
    rule snapshot의 재현력을 높이기 위한 부가 컨텍스트를 계산한다.
    - rule layer는 policy만 반환하고, 여기서는 "어디서 왔는지"를 추적용으로 계산해 저장한다.
    """
    resolved_from = None
    if requirement is not None:
        resolved_from = "SITE_OVERRIDE"
    elif document_type is not None:
        resolved_from = "MASTER_DEFAULT"

    resolved_cycle_source = "none"
    if requirement is not None and requirement.override_cycle_id is not None:
        resolved_cycle_source = "override"
    elif document_type is not None:
        resolved_cycle_source = "master"

    return {
        "resolved_from": resolved_from,
        "resolved_cycle_source": resolved_cycle_source,
        "master_cycle_id": master_cycle.id if master_cycle else None,
        "master_cycle_code": master_cycle.code if master_cycle else None,
        "override_cycle_id": override_cycle.id if override_cycle else None,
        "override_cycle_code": override_cycle.code if override_cycle else None,
    }


def _mark_instance_failed_final(
    db: Session,
    site_id: int,
    document_type_code: str,
    period_basis: str,
    period_start: date,
    period_end: date,
    *,
    status_reason: str,
    error_message: str,
    snapshot: dict,
    rule_is_required: bool,
    cycle_code: str | None,
    generation_rule: str | None,
    generation_value: str | None,
    due_offset_days: int | None,
):
    """
    예외 상황에서도 FAILED 기록 유실이 없도록, rollback 이후 별도 저장 트랜잭션으로 FAILED를 확정한다.
    """
    db.rollback()
    inst = _get_instance_by_key(db, site_id, document_type_code, period_basis, period_start, period_end)
    if inst is None:
        inst = DocumentInstance(
            site_id=site_id,
            document_type_code=document_type_code,
            period_start=period_start,
            period_end=period_end,
            generation_anchor_date=None,
            due_date=None,
            status=DocumentInstanceStatus.FAILED,
            status_reason=status_reason,
            selected_requirement_id=None,
            period_basis=period_basis,
            rule_is_required=rule_is_required,
            cycle_code=cycle_code,
            rule_generation_rule=generation_rule,
            rule_generation_value=generation_value,
            rule_due_offset_days=due_offset_days,
            resolved_from=snapshot.get("resolved_from"),
            resolved_cycle_source=snapshot.get("resolved_cycle_source"),
            master_cycle_id=snapshot.get("master_cycle_id"),
            master_cycle_code=snapshot.get("master_cycle_code"),
            override_cycle_id=snapshot.get("override_cycle_id"),
            override_cycle_code=snapshot.get("override_cycle_code"),
            error_message=error_message[:500],
        )
        db.add(inst)
    else:
        inst.status = DocumentInstanceStatus.FAILED
        inst.status_reason = status_reason
        inst.error_message = error_message[:500]
        inst.period_basis = period_basis
        inst.rule_is_required = rule_is_required
        inst.cycle_code = cycle_code
        inst.rule_generation_rule = generation_rule
        inst.rule_generation_value = generation_value
        inst.rule_due_offset_days = due_offset_days
        inst.resolved_from = snapshot.get("resolved_from")
        inst.resolved_cycle_source = snapshot.get("resolved_cycle_source")
        inst.master_cycle_id = snapshot.get("master_cycle_id")
        inst.master_cycle_code = snapshot.get("master_cycle_code")
        inst.override_cycle_id = snapshot.get("override_cycle_id")
        inst.override_cycle_code = snapshot.get("override_cycle_code")
        db.add(inst)
    db.commit()


def orchestrate_document_generation(
    db: Session,
    site_id: int,
    document_type_code: str,
    as_of_date: date,
    dry_run: bool = True,
    retry_failed: bool = False,
    reevaluate_skipped: bool = False,
) -> tuple[str, dict]:
    """
    rule → slot/period → DocumentInstance(PENDING/SKIPPED/FAILED/GENERATED) → Document 생성까지 묶는 오케스트레이션.
    - rule layer와 generation engine은 분리 유지
    - 생성은 항상 idempotent (DocumentInstance 유니크키 기준)
    """
    rule = get_effective_rule(
        db=db,
        site_id=site_id,
        document_type_code=document_type_code,
        as_of_date=as_of_date,
    )
    if not rule:
        # 이 경로는 get_effective_rule 계약상 거의 없지만, 추적 일관성을 위해 SKIPPED 인스턴스 기록을 남긴다.
        try:
            snapshot = _resolve_snapshot_context(None, None, None, None)
            period_start = as_of_date
            period_end = as_of_date
            inst = _get_instance_by_key(
                db, site_id, document_type_code, PeriodBasis.AS_OF_FALLBACK, period_start, period_end
            )
            if inst is None:
                inst = DocumentInstance(
                    site_id=site_id,
                    document_type_code=document_type_code,
                    period_start=period_start,
                    period_end=period_end,
                    generation_anchor_date=None,
                    due_date=None,
                    status=DocumentInstanceStatus.SKIPPED,
                    status_reason=RuleStatusReason.MISSING_RULE,
                    selected_requirement_id=None,
                    period_basis=PeriodBasis.AS_OF_FALLBACK,
                    rule_is_required=False,
                    cycle_code=None,
                    rule_generation_rule=None,
                    rule_generation_value=None,
                    rule_due_offset_days=None,
                    resolved_from=snapshot.get("resolved_from"),
                    resolved_cycle_source=snapshot.get("resolved_cycle_source"),
                    master_cycle_id=snapshot.get("master_cycle_id"),
                    master_cycle_code=snapshot.get("master_cycle_code"),
                    override_cycle_id=snapshot.get("override_cycle_id"),
                    override_cycle_code=snapshot.get("override_cycle_code"),
                    error_message=None,
                )
                db.add(inst)
                db.commit()
            return "skipped", {"code": document_type_code, "reason": "missing_rule", "instance_id": inst.id}
        except Exception:
            db.rollback()
            return "skipped", {"code": document_type_code, "reason": "missing_rule"}

    # 결정 직후(동일 세션) snapshot을 캡처하고, 이후에는 재조회로 값이 바뀌지 않게 그대로 전달한다.
    dt = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.code == document_type_code).first()
    req = None
    if rule.selected_requirement_id is not None:
        req = db.query(DocumentRequirement).filter(DocumentRequirement.id == rule.selected_requirement_id).first()
    master_cycle = None
    if dt is not None:
        master_cycle = db.query(SubmissionCycle).filter(SubmissionCycle.id == dt.default_cycle_id).first()
    override_cycle = None
    if req is not None and req.override_cycle_id is not None:
        override_cycle = db.query(SubmissionCycle).filter(SubmissionCycle.id == req.override_cycle_id).first()

    snapshot = _resolve_snapshot_context(dt, req, master_cycle, override_cycle)
    period_basis = PeriodBasis.CYCLE

    if rule.cycle is None:
        period_basis = PeriodBasis.AS_OF_FALLBACK
        period_start = as_of_date
        period_end = as_of_date
    else:
        period = resolve_period_for_cycle(rule.cycle, as_of_date)
        if not period:
            period_basis = PeriodBasis.AS_OF_FALLBACK
            period_start = as_of_date
            period_end = as_of_date
        else:
            period_start = period.start
            period_end = period.end

    # is_required=false는 Document 생성 없이 SKIPPED 기록(추적용)만 남긴다.
    if not rule.is_required:
        if dry_run:
            return (
                "skipped",
                {
                    "code": document_type_code,
                    "reason": rule.status_reason.lower(),
                    "dry_run": True,
                    "period_start": str(period_start),
                    "period_end": str(period_end),
                },
            )

        try:
            inst = _get_instance_by_key(db, site_id, document_type_code, period_basis, period_start, period_end)
            if inst is None:
                inst = DocumentInstance(
                    site_id=site_id,
                    document_type_code=document_type_code,
                    period_start=period_start,
                    period_end=period_end,
                    generation_anchor_date=None,
                    due_date=None,
                    status=DocumentInstanceStatus.SKIPPED,
                    status_reason=rule.status_reason,
                    selected_requirement_id=rule.selected_requirement_id,
                    period_basis=period_basis,
                    rule_is_required=rule.is_required,
                    cycle_code=rule.cycle,
                    rule_generation_rule=rule.generation_rule,
                    rule_generation_value=rule.generation_value,
                    rule_due_offset_days=rule.due_offset_days,
                    resolved_from=snapshot.get("resolved_from"),
                    resolved_cycle_source=snapshot.get("resolved_cycle_source"),
                    master_cycle_id=snapshot.get("master_cycle_id"),
                    master_cycle_code=snapshot.get("master_cycle_code"),
                    override_cycle_id=snapshot.get("override_cycle_id"),
                    override_cycle_code=snapshot.get("override_cycle_code"),
                    error_message=None,
                )
                db.add(inst)
            else:
                inst.status = DocumentInstanceStatus.SKIPPED
                inst.status_reason = rule.status_reason
                inst.selected_requirement_id = rule.selected_requirement_id
                inst.period_basis = period_basis
                inst.rule_is_required = rule.is_required
                inst.cycle_code = rule.cycle
                inst.rule_generation_rule = rule.generation_rule
                inst.rule_generation_value = rule.generation_value
                inst.rule_due_offset_days = rule.due_offset_days
                inst.resolved_from = snapshot.get("resolved_from")
                inst.resolved_cycle_source = snapshot.get("resolved_cycle_source")
                inst.master_cycle_id = snapshot.get("master_cycle_id")
                inst.master_cycle_code = snapshot.get("master_cycle_code")
                inst.override_cycle_id = snapshot.get("override_cycle_id")
                inst.override_cycle_code = snapshot.get("override_cycle_code")
                inst.generation_anchor_date = None
                inst.due_date = None
                inst.error_message = None
                db.add(inst)

            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                inst = _get_instance_by_key(db, site_id, document_type_code, period_basis, period_start, period_end)
                if inst is None:
                    raise
                inst.status = DocumentInstanceStatus.SKIPPED
                inst.status_reason = rule.status_reason
                inst.selected_requirement_id = rule.selected_requirement_id
                inst.period_basis = period_basis
                inst.rule_is_required = rule.is_required
                inst.cycle_code = rule.cycle
                inst.rule_generation_rule = rule.generation_rule
                inst.rule_generation_value = rule.generation_value
                inst.rule_due_offset_days = rule.due_offset_days
                inst.resolved_from = snapshot.get("resolved_from")
                inst.resolved_cycle_source = snapshot.get("resolved_cycle_source")
                inst.master_cycle_id = snapshot.get("master_cycle_id")
                inst.master_cycle_code = snapshot.get("master_cycle_code")
                inst.override_cycle_id = snapshot.get("override_cycle_id")
                inst.override_cycle_code = snapshot.get("override_cycle_code")
                inst.generation_anchor_date = None
                inst.due_date = None
                inst.error_message = None
                db.add(inst)
                db.flush()

            db.commit()
            return (
                "skipped",
                {
                    "code": document_type_code,
                    "reason": rule.status_reason.lower(),
                    "instance_id": inst.id,
                    "period_start": str(inst.period_start),
                    "period_end": str(inst.period_end),
                },
            )
        except Exception:
            db.rollback()
            raise

    slot = resolve_generation_slot(rule, as_of_date)
    if not slot:
        # is_required=true인데 slot이 없으면 운영상 FAILED로 기록할 가치가 있음
        if dry_run:
            return "skipped", {"code": document_type_code, "reason": "slot_not_resolved", "dry_run": True}

        try:
            inst = _get_instance_by_key(db, site_id, document_type_code, period_basis, period_start, period_end)
            if inst is None:
                inst = DocumentInstance(
                    site_id=site_id,
                    document_type_code=document_type_code,
                    period_start=period_start,
                    period_end=period_end,
                    generation_anchor_date=None,
                    due_date=None,
                    status=DocumentInstanceStatus.FAILED,
                    status_reason=RuleStatusReason.SLOT_NOT_RESOLVED,
                    selected_requirement_id=rule.selected_requirement_id,
                    period_basis=period_basis,
                    rule_is_required=rule.is_required,
                    cycle_code=rule.cycle,
                    rule_generation_rule=rule.generation_rule,
                    rule_generation_value=rule.generation_value,
                    rule_due_offset_days=rule.due_offset_days,
                    resolved_from=snapshot.get("resolved_from"),
                    resolved_cycle_source=snapshot.get("resolved_cycle_source"),
                    master_cycle_id=snapshot.get("master_cycle_id"),
                    master_cycle_code=snapshot.get("master_cycle_code"),
                    override_cycle_id=snapshot.get("override_cycle_id"),
                    override_cycle_code=snapshot.get("override_cycle_code"),
                    error_message="resolve_generation_slot returned None",
                )
                db.add(inst)
            else:
                inst.status = DocumentInstanceStatus.FAILED
                inst.status_reason = RuleStatusReason.SLOT_NOT_RESOLVED
                inst.selected_requirement_id = rule.selected_requirement_id
                inst.period_basis = period_basis
                inst.rule_is_required = rule.is_required
                inst.cycle_code = rule.cycle
                inst.rule_generation_rule = rule.generation_rule
                inst.rule_generation_value = rule.generation_value
                inst.rule_due_offset_days = rule.due_offset_days
                inst.resolved_from = snapshot.get("resolved_from")
                inst.resolved_cycle_source = snapshot.get("resolved_cycle_source")
                inst.master_cycle_id = snapshot.get("master_cycle_id")
                inst.master_cycle_code = snapshot.get("master_cycle_code")
                inst.override_cycle_id = snapshot.get("override_cycle_id")
                inst.override_cycle_code = snapshot.get("override_cycle_code")
                inst.generation_anchor_date = None
                inst.due_date = None
                inst.error_message = "resolve_generation_slot returned None"
                db.add(inst)

            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                inst = _get_instance_by_key(db, site_id, document_type_code, period_basis, period_start, period_end)
                if inst is None:
                    raise
                inst.status = DocumentInstanceStatus.FAILED
                inst.status_reason = RuleStatusReason.SLOT_NOT_RESOLVED
                inst.selected_requirement_id = rule.selected_requirement_id
                inst.period_basis = period_basis
                inst.rule_is_required = rule.is_required
                inst.cycle_code = rule.cycle
                inst.rule_generation_rule = rule.generation_rule
                inst.rule_generation_value = rule.generation_value
                inst.rule_due_offset_days = rule.due_offset_days
                inst.resolved_from = snapshot.get("resolved_from")
                inst.resolved_cycle_source = snapshot.get("resolved_cycle_source")
                inst.master_cycle_id = snapshot.get("master_cycle_id")
                inst.master_cycle_code = snapshot.get("master_cycle_code")
                inst.override_cycle_id = snapshot.get("override_cycle_id")
                inst.override_cycle_code = snapshot.get("override_cycle_code")
                inst.generation_anchor_date = None
                inst.due_date = None
                inst.error_message = "resolve_generation_slot returned None"
                db.add(inst)
                db.flush()

            db.commit()
            return "failed", {"code": document_type_code, "instance_id": inst.id, "reason": "slot_not_resolved"}
        except Exception:
            db.rollback()
            raise

    # idempotency: 인스턴스 row를 먼저 확보
    if dry_run:
        due_date = resolve_due_date(slot, rule.due_offset_days)
        return (
            "created",
            {
                "document_type": document_type_code,
                "period_start": str(slot.period_start),
                "period_end": str(slot.period_end),
                "due_date": str(due_date),
                "dry_run": True,
                "policy_source": rule.status_reason,
                "cycle": rule.cycle,
            },
        )

    try:
        due_date = resolve_due_date(slot, rule.due_offset_days)

        inst: DocumentInstance | None = None

        # 1) idempotency 키 확보 (insert 시도 → 충돌이면 기존 row 사용)
        try:
            inst = DocumentInstance(
                site_id=site_id,
                document_type_code=document_type_code,
                period_start=slot.period_start,
                period_end=slot.period_end,
                generation_anchor_date=slot.generation_anchor_date,
                due_date=due_date,
                status=DocumentInstanceStatus.PENDING,
                status_reason=rule.status_reason,
                selected_requirement_id=rule.selected_requirement_id,
                period_basis=period_basis,
                rule_is_required=rule.is_required,
                cycle_code=rule.cycle,
                rule_generation_rule=rule.generation_rule,
                rule_generation_value=rule.generation_value,
                rule_due_offset_days=rule.due_offset_days,
                resolved_from=snapshot.get("resolved_from"),
                resolved_cycle_source=snapshot.get("resolved_cycle_source"),
                master_cycle_id=snapshot.get("master_cycle_id"),
                master_cycle_code=snapshot.get("master_cycle_code"),
                override_cycle_id=snapshot.get("override_cycle_id"),
                override_cycle_code=snapshot.get("override_cycle_code"),
                error_message=None,
            )
            db.add(inst)
            db.flush()
        except IntegrityError:
            db.rollback()
            inst = _get_instance_by_key(
                db, site_id, document_type_code, period_basis, slot.period_start, slot.period_end
            )
            if inst is None:
                raise

        # 2) 기존 상태별 처리(명시적 전이 규칙)
        if inst.status == DocumentInstanceStatus.PENDING:
            # 중복 실행 차단
            return ("skipped", {"code": document_type_code, "reason": "already_pending", "instance_id": inst.id})
        if inst.status == DocumentInstanceStatus.GENERATED:
            # GENERATED 재사용 시 document 정합성 검증(삭제/연결 끊김 복구)
            doc = db.query(Document).filter(Document.instance_id == inst.id).first()
            if doc is None:
                inst.status = DocumentInstanceStatus.FAILED
                inst.status_reason = RuleStatusReason.DOCUMENT_LINK_BROKEN
                inst.error_message = "linked document not found for GENERATED instance"
                db.add(inst)
                db.commit()
                if retry_failed:
                    inst.status = DocumentInstanceStatus.PENDING
                    inst.error_message = None
                    db.add(inst)
                    db.commit()
                return ("failed", {"code": document_type_code, "reason": "document_link_broken", "instance_id": inst.id})
            return ("skipped", {"code": document_type_code, "reason": "already_generated", "instance_id": inst.id})
        if inst.status == DocumentInstanceStatus.FAILED:
            if not retry_failed:
                return ("skipped", {"code": document_type_code, "reason": "failed_no_retry", "instance_id": inst.id})
            inst.status = DocumentInstanceStatus.PENDING
            inst.error_message = None
        if inst.status == DocumentInstanceStatus.SKIPPED:
            if not reevaluate_skipped:
                return ("skipped", {"code": document_type_code, "reason": "skipped_no_reeval", "instance_id": inst.id})
            inst.status = DocumentInstanceStatus.PENDING
            inst.error_message = None

        # 3) 스냅샷/계산 결과 최신화 (재시도/재평가 포함)
        inst.status_reason = rule.status_reason
        inst.selected_requirement_id = rule.selected_requirement_id
        inst.rule_is_required = rule.is_required
        inst.period_basis = period_basis
        inst.cycle_code = rule.cycle
        inst.rule_generation_rule = rule.generation_rule
        inst.rule_generation_value = rule.generation_value
        inst.rule_due_offset_days = rule.due_offset_days
        inst.resolved_from = snapshot.get("resolved_from")
        inst.resolved_cycle_source = snapshot.get("resolved_cycle_source")
        inst.master_cycle_id = snapshot.get("master_cycle_id")
        inst.master_cycle_code = snapshot.get("master_cycle_code")
        inst.override_cycle_id = snapshot.get("override_cycle_id")
        inst.override_cycle_code = snapshot.get("override_cycle_code")
        inst.generation_anchor_date = slot.generation_anchor_date
        inst.due_date = due_date
        db.add(inst)
        db.flush()

        # 4) 문서 중복 2차 방어
        existing = find_existing_auto_document(
            db=db,
            site_id=site_id,
            document_type_code=document_type_code,
            period_start=slot.period_start,
            period_end=slot.period_end,
        )
        if existing:
            inst.status = DocumentInstanceStatus.GENERATED
            if existing.instance_id is None:
                existing.instance_id = inst.id
                db.add(existing)
            inst.error_message = None
            db.add(inst)
            db.flush()
            db.commit()
            return (
                "skipped",
                {
                    "code": document_type_code,
                    "reason": "duplicate_auto_document",
                    "instance_id": inst.id,
                    "document_no": existing.document_no,
                },
            )

        # 5) Document 생성 + instance 연결 (동일 커밋 단위)
        doc = create_document_for_period(
            db=db,
            site_id=site_id,
            document_type_code=document_type_code,
            period_start=slot.period_start,
            period_end=slot.period_end,
            due_date=due_date,
            instance_id=inst.id,
        )
        inst.status = DocumentInstanceStatus.GENERATED
        inst.error_message = None
        db.add(inst)
        db.flush()
        db.commit()
        return (
            "created",
            {
                "document_type": document_type_code,
                "instance_id": inst.id,
                "document_no": doc.document_no,
                "period_start": str(doc.period_start),
                "period_end": str(doc.period_end),
                "due_date": str(doc.due_date),
                "dry_run": False,
                "policy_source": rule.status_reason,
                "cycle": rule.cycle,
            },
        )
    except Exception as e:  # noqa: BLE001
        _mark_instance_failed_final(
            db,
            site_id,
            document_type_code,
            period_basis,
            slot.period_start,
            slot.period_end,
            status_reason=RuleStatusReason.EXCEPTION,
            error_message=str(e),
            snapshot=snapshot,
            rule_is_required=rule.is_required,
            cycle_code=rule.cycle,
            generation_rule=rule.generation_rule,
            generation_value=rule.generation_value,
            due_offset_days=rule.due_offset_days,
        )
        inst = _get_instance_by_key(db, site_id, document_type_code, period_basis, slot.period_start, slot.period_end)
        return ("failed", {"code": document_type_code, "instance_id": inst.id if inst else None, "reason": "exception"})


def generate_document_submission(
    db: Session,
    site_id: int,
    document_type_code: str,
    as_of_date: date,
    dry_run: bool = True,
) -> tuple[str, dict]:
    # Backward-compatible wrapper: 기존 엔드포인트 동작을 유지하되, 내부는 오케스트레이터로 일원화.
    return orchestrate_document_generation(
        db=db,
        site_id=site_id,
        document_type_code=document_type_code,
        as_of_date=as_of_date,
        dry_run=dry_run,
        retry_failed=False,
        reevaluate_skipped=False,
    )
