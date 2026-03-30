"""
[CRITICAL POLICY]

- site requirement > master default
- is_enabled=False => HARD DISABLE (no fallback)
- override is field-level fallback
- is_required_default is NOT overridable in MVP
- ADHOC => no auto generation
- get_effective_rule decides policy only
- generation_engine handles period/due

DO NOT CHANGE WITHOUT POLICY UPDATE
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.modules.document_settings.constants import RuleStatusReason
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle


@dataclass(frozen=True)
class EffectiveRuleResult:
    document_type_code: str
    cycle: str | None
    generation_rule: str | None
    generation_value: str | None
    due_offset_days: int | None
    is_required: bool
    status_reason: str
    selected_requirement_id: int | None = None


def valid_override(value: str | None) -> bool:
    """
    override 채택 기준(공통):
    - None, "", 공백 문자열은 모두 무효
    - 문자열이 아닌 값은 이 레이어에서 받지 않는 것을 전제 (스키마에서 통제)
    """
    if value is None:
        return False
    if str(value).strip() == "":
        return False
    return True


def _as_open_start(d: date | None) -> date:
    return d if d is not None else date.min


def _as_open_end(d: date | None) -> date:
    return d if d is not None else date.max


def _is_effective(as_of_date: date, effective_from: date | None, effective_to: date | None) -> bool:
    return _as_open_start(effective_from) <= as_of_date <= _as_open_end(effective_to)


def _specificity_rank(req: DocumentRequirement) -> tuple[int, int, int, int]:
    """
    총순서가 정의되는 specificity 랭킹.
    - 닫힌 구간(start+end) > 반열린 구간(start only / end only) > 상시(NULL,NULL)
    - 닫힌 구간끼리는 기간이 짧을수록 우선
    - 반열린 구간은 길이 비교 없이 구간 타입까지만 반영하고 즉시 tie-break
    - tie-break는 updated_at DESC, id DESC
    """
    has_start = req.effective_from is not None
    has_end = req.effective_to is not None

    if has_start and has_end:
        specificity = 3
        span_days = (req.effective_to - req.effective_from).days
    elif has_start or has_end:
        specificity = 2
        span_days = 10**9  # open은 길이 비교 제외
    else:
        specificity = 1
        span_days = 10**9

    # updated_at DESC, id DESC
    updated_ord = req.updated_at.toordinal() if req.updated_at else date.min.toordinal()
    return (specificity, -span_days, updated_ord, req.id)


def _pick_sort_key(req: DocumentRequirement) -> tuple[int, tuple[int, int, int, int]]:
    """
    충돌 처리 최종 규칙 (MVP 고정):
    - is_enabled=False(금지 규칙) 우선 선택
    - 그 다음은 기존 specificity(기간 지정 > 상시, 기간 짧음 > 김, 최근 > 과거)
    """
    disabled_first = 1 if req.is_enabled is False else 0
    return (disabled_first, _specificity_rank(req))


def _find_active_document_type_master(db: Session, document_type_code: str) -> DocumentTypeMaster | None:
    return (
        db.query(DocumentTypeMaster)
        .filter(
            DocumentTypeMaster.code == document_type_code,
            DocumentTypeMaster.is_active == True,  # noqa: E712
        )
        .first()
    )


def _list_valid_requirements(db: Session, site_id: int, document_type_id: int, as_of_date: date) -> list[DocumentRequirement]:
    reqs = (
        db.query(DocumentRequirement)
        .filter(
            DocumentRequirement.site_id == site_id,
            DocumentRequirement.document_type_id == document_type_id,
        )
        .all()
    )
    return [req for req in reqs if _is_effective(as_of_date, req.effective_from, req.effective_to)]


def _pick_best_requirement(requirements: list[DocumentRequirement]) -> DocumentRequirement | None:
    if not requirements:
        return None
    return sorted(requirements, key=_pick_sort_key, reverse=True)[0]


def _resolve_cycle(
    db: Session,
    default_cycle_id: int,
    override_cycle_id: int | None,
) -> SubmissionCycle | None:
    """
    override_cycle_id가 존재하지만 미존재/비활성인 경우:
    - MVP 정책: master default로 fallback (생성 엔진이 멈추지 않도록)
    """
    if override_cycle_id is not None:
        override = db.query(SubmissionCycle).filter(SubmissionCycle.id == override_cycle_id).first()
        if override and override.is_active:
            return override

    return db.query(SubmissionCycle).filter(SubmissionCycle.id == default_cycle_id).first()


def _build_effective_rule(
    db: Session,
    document_type: DocumentTypeMaster,
    requirement: DocumentRequirement | None,
) -> EffectiveRuleResult:
    # 1) HARD DISABLE: is_enabled=False면 "완전 생성 금지" + generation 필드 None 강제
    if requirement is not None and requirement.is_enabled is False:
        return EffectiveRuleResult(
            document_type_code=document_type.code,
            cycle=None,
            generation_rule=None,
            generation_value=None,
            due_offset_days=None,
            is_required=False,
            status_reason=RuleStatusReason.SITE_DISABLED,
            selected_requirement_id=requirement.id,
        )

    # 2) cycle: requirement.override_cycle_id가 있으면 우선, 없으면 master default
    cycle = _resolve_cycle(
        db,
        document_type.default_cycle_id,
        requirement.override_cycle_id if requirement else None,
    )
    cycle_code = cycle.code if cycle else None

    # 3) generation: 필드별 fallback (site override > master default)
    generation_rule = (
        requirement.override_generation_rule
        if (requirement and valid_override(requirement.override_generation_rule))
        else document_type.generation_rule
    )
    generation_value = (
        requirement.override_generation_value
        if (requirement and valid_override(requirement.override_generation_value))
        else document_type.generation_value
    )
    due_offset_days = (
        requirement.override_due_offset_days
        if (requirement and requirement.override_due_offset_days is not None)
        else document_type.due_offset_days
    )

    is_required = document_type.is_required_default
    status_reason = (
        RuleStatusReason.SITE_OVERRIDE if requirement is not None else RuleStatusReason.MASTER_DEFAULT
    )

    if not cycle or not cycle.is_active:
        return EffectiveRuleResult(
            document_type_code=document_type.code,
            cycle=None,
            generation_rule=None,
            generation_value=None,
            due_offset_days=None,
            is_required=False,
            status_reason=RuleStatusReason.CYCLE_INACTIVE,
            selected_requirement_id=requirement.id if requirement else None,
        )

    if cycle.code == "ADHOC" or not cycle.is_auto_generatable:
        return EffectiveRuleResult(
            document_type_code=document_type.code,
            cycle=cycle.code,
            generation_rule=None,
            generation_value=None,
            due_offset_days=None,
            is_required=False,
            status_reason=RuleStatusReason.CYCLE_MANUAL_ONLY,
            selected_requirement_id=requirement.id if requirement else None,
        )

    return EffectiveRuleResult(
        document_type_code=document_type.code,
        cycle=cycle.code,
        generation_rule=generation_rule,
        generation_value=generation_value,
        due_offset_days=due_offset_days,
        is_required=is_required,
        status_reason=status_reason,
        selected_requirement_id=requirement.id if requirement else None,
    )


def get_effective_rule(
    db: Session,
    site_id: int,
    document_type_code: str,
    as_of_date: date,
) -> EffectiveRuleResult | None:
    document_type = _find_active_document_type_master(db, document_type_code)
    if not document_type:
        return EffectiveRuleResult(
            document_type_code=document_type_code,
            cycle=None,
            generation_rule=None,
            generation_value=None,
            due_offset_days=None,
            is_required=False,
            status_reason=RuleStatusReason.DOC_TYPE_INACTIVE_OR_MISSING,
            selected_requirement_id=None,
        )

    requirements = _list_valid_requirements(db, site_id, document_type.id, as_of_date)
    requirement = _pick_best_requirement(requirements)
    return _build_effective_rule(db, document_type, requirement)


def get_effective_policy(
    db: Session,
    site_id: int,
    document_type_code: str,
    as_of: date,
) -> EffectiveRuleResult | None:
    return get_effective_rule(db=db, site_id=site_id, document_type_code=document_type_code, as_of_date=as_of)
