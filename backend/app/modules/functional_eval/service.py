from __future__ import annotations

import hashlib
import csv
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.enums import Role, UIType
from app.core.datetime_utils import utc_now
from app.core.permissions import HQ_SAFE_WORKSPACE_ROLES
from app.modules.functional_eval.eval_catalog import (
    EvalType,
    apply_score_point_adjustments,
    assessment_has_bottom,
    build_lowest_grade_scores,
    build_safety_scores_with_bottom_for_violation,
    catalog_for_api,
    compute_assessment,
    get_criteria,
    normalize_grade_code,
    violation_safety_criterion_ids,
    violation_safety_targets_already_bottom,
)
from app.modules.functional_eval.attendance import ParsedAttendanceRow, parse_attendance_report_xlsx
from app.modules.functional_eval.models import (
    FunctionalEvalAssessment,
    FunctionalEvalAssessmentRevision,
    FunctionalEvalAttendanceEntry,
    FunctionalEvalAttendanceImportBatch,
    FunctionalEvalCustomerReward,
    FunctionalEvalPeriod,
    FunctionalEvalRosterImportBatch,
    FunctionalEvalSanction,
    FunctionalEvalSiteApproval,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import (
    ParsedRosterRow,
    RosterDiffItem,
    RosterDiffResult,
    hash_rrn,
    parse_daily_roster_xlsx,
)
from app.modules.functional_eval.sanctions import (
    SANCTION_RESULT_LABELS,
    VIOLATION_BY_CODE,
    VIOLATION_CATALOG,
    build_sanction_display_label,
    institutional_sanction_label,
    is_permanent_sanction,
    resolve_sanction,
    sanction_outcome_label,
    worker_status_from_sanctions,
)
from app.modules.functional_eval.customer_rewards import CUSTOMER_REWARD_NOTE, REWARD_STATUS_APPROVED, REWARD_STATUS_PENDING
from app.modules.functional_eval.sanction_reviews import SANCTION_STATUS_APPROVED, SANCTION_STATUS_PENDING
from app.modules.functional_eval.sanction_evidence import (
    DEFAULT_SANCTION_PENALTY_POINTS,
    EVIDENCE_COMMENT,
    EVIDENCE_PHOTO,
)
from app.config.settings import settings
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.utils.file_ingestion import parse_excel_with_fallback

from app.modules.functional_eval.eval_schedule import (
    EVAL_CAMPAIGN_DEADLINE,
    assert_evaluation_open,
    evaluation_is_open,
    evaluation_opens_at_kst_iso,
    evaluation_opens_at_kst_label,
)
from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD
from app.modules.functional_eval.signature_service import batch_label
from app.modules.functional_eval.site_alias import build_eval_login_id
from app.modules.functional_eval import approval_workflow
from app.modules.functional_eval.legacy_site_grade import apply_legacy_assessments

DEFAULT_PERIOD_TITLE = "기능인제 인사고과"
DEFAULT_DEADLINE = EVAL_CAMPAIGN_DEADLINE


def _rrn_front_password(rrn_raw: str) -> str | None:
    digits = re.sub(r"\D", "", rrn_raw)
    if len(digits) >= 6:
        return digits[:6]
    return None


def _birth_sort_key(rrn_raw: str) -> tuple[int, int, int]:
    digits = re.sub(r"\D", "", rrn_raw)
    if len(digits) < 7:
        return (9999, 12, 31)
    yy = int(digits[0:2])
    mm = int(digits[2:4])
    dd = int(digits[4:6])
    century = 1900 if digits[6] in "1256" else 2000
    if digits[6] in "34":
        century = 2000
    return (century + yy, mm, dd)


def _site_code_from_login_id(login_id: str | None) -> str:
    raw = (login_id or "").strip()
    if not raw:
        return ""
    return raw.split("-", 1)[0].strip()


@dataclass
class ParsedTeamAssignmentRow:
    site_code: str
    team_leader_name: str
    team_leader_rrn_raw: str
    worker_name: str
    worker_rrn_raw: str | None = None


def get_or_create_active_period(db: Session) -> FunctionalEvalPeriod:
    period = (
        db.query(FunctionalEvalPeriod)
        .filter(FunctionalEvalPeriod.is_active.is_(True))
        .order_by(FunctionalEvalPeriod.id.desc())
        .first()
    )
    if period is not None:
        return period
    period = FunctionalEvalPeriod(
        title=DEFAULT_PERIOD_TITLE,
        deadline_date=DEFAULT_DEADLINE,
        is_active=True,
    )
    from app.modules.functional_eval.constants import DEFAULT_GRADE_STATS_LIVE_FROM

    period.grade_stats_live_from = DEFAULT_GRADE_STATS_LIVE_FROM
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def period_is_closed(period: FunctionalEvalPeriod, *, today: date | None = None) -> bool:
    ref = today or utc_now().date()
    return ref > period.deadline_date


def assert_period_editable(period: FunctionalEvalPeriod) -> None:
    """평가·ERP 반영 등 — 마감 후 불가."""
    if period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")


def assert_period_eval_editable(period: FunctionalEvalPeriod) -> None:
    assert_evaluation_open()
    assert_period_editable(period)


def get_latest_attendance_date(db: Session, period_id: int) -> date | None:
    row = (
        db.query(FunctionalEvalAttendanceEntry.work_date)
        .filter(FunctionalEvalAttendanceEntry.period_id == period_id)
        .order_by(FunctionalEvalAttendanceEntry.work_date.desc())
        .first()
    )
    return row[0] if row else None


def _attendance_rrn_hashes_for_date(
    db: Session, period_id: int, work_date: date, *, site_code: str | None = None
) -> set[str]:
    q = db.query(FunctionalEvalAttendanceEntry.rrn_hash).filter(
        FunctionalEvalAttendanceEntry.period_id == period_id,
        FunctionalEvalAttendanceEntry.work_date == work_date,
    )
    if site_code:
        q = q.filter(FunctionalEvalAttendanceEntry.site_code == site_code)
    return {r[0] for r in q.all()}


def _period_attendance_rrn_hashes(
    db: Session, period_id: int, *, site_code: str | None = None
) -> set[str]:
    q = db.query(FunctionalEvalAttendanceEntry.rrn_hash).filter(
        FunctionalEvalAttendanceEntry.period_id == period_id,
    )
    if site_code:
        q = q.filter(FunctionalEvalAttendanceEntry.site_code == site_code)
    return {r[0] for r in q.distinct().all()}


def _clean_erp_site_label(label: str | None) -> str:
    if not label:
        return ""
    text = str(label).strip()
    if text.startswith("현장명:"):
        text = text.split(":", 1)[1].strip()
    return text


def _attendance_site_meta(
    db: Session, period_id: int
) -> tuple[set[str], dict[str, str], dict[str, str]]:
    """출역일보에 실제 등장한 현장코드·ERP 현장명·대표(소장) 열."""
    rows = (
        db.query(FunctionalEvalAttendanceEntry)
        .filter(FunctionalEvalAttendanceEntry.period_id == period_id)
        .all()
    )
    codes: set[str] = set()
    labels: dict[str, str] = {}
    rep_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        code = (row.site_code or "").strip()
        if not code:
            continue
        codes.add(code)
        cleaned = _clean_erp_site_label(row.erp_site_label)
        if cleaned and (code not in labels or len(cleaned) > len(labels[code])):
            labels[code] = cleaned
        if row.rep_name:
            rep_counts[code][str(row.rep_name).strip()] += 1
    rep_best: dict[str, str] = {}
    for code, counter in rep_counts.items():
        if counter:
            rep_best[code] = counter.most_common(1)[0][0]
    return codes, labels, rep_best


def _resolve_site_display_name(
    site_code: str,
    site_names: dict[str, str],
    erp_labels: dict[str, str],
) -> str:
    erp = erp_labels.get(site_code) or ""
    registered = (site_names.get(site_code) or "").strip()
    if erp:
        return erp
    if registered and not registered.startswith(f"현장 {site_code}"):
        return registered
    return registered or f"현장 {site_code}"


def _reference_worker_map(db: Session, period_id: int) -> dict[str, FunctionalEvalWorker]:
    rows = (
        db.query(FunctionalEvalWorker)
        .filter(FunctionalEvalWorker.period_id == period_id)
        .all()
    )
    return {w.rrn_hash: w for w in rows if w.rrn_hash}


def _worker_has_assessments(db: Session, worker_id: int) -> bool:
    return (
        db.query(FunctionalEvalAssessment.id)
        .filter(FunctionalEvalAssessment.worker_id == worker_id)
        .first()
        is not None
    )


def _assert_worker_attendance_eligible(
    db: Session, period: FunctionalEvalPeriod, worker: FunctionalEvalWorker
) -> None:
    """당일 출역 목록 또는 기간 내 출역·기존 평가가 있으면 입력 허용."""
    if _worker_has_assessments(db, worker.id):
        return
    if worker.rrn_hash in _period_attendance_rrn_hashes(db, period.id, site_code=worker.site_code):
        return
    latest = get_latest_attendance_date(db, period.id)
    if latest is None:
        raise ValueError("NO_ATTENDANCE_UPLOAD")
    if worker.rrn_hash in _attendance_rrn_hashes_for_date(
        db, period.id, latest, site_code=worker.site_code
    ):
        return
    raise ValueError("WORKER_NOT_ON_ATTENDANCE")


def serialize_period(period: FunctionalEvalPeriod, db: Session | None = None) -> dict[str, Any]:
    attendance_date = period.last_attendance_date
    attendance_count = 0
    if db is not None:
        if attendance_date is None:
            attendance_date = get_latest_attendance_date(db, period.id)
        if attendance_date is not None:
            attendance_count = (
                db.query(FunctionalEvalAttendanceEntry.id)
                .filter(
                    FunctionalEvalAttendanceEntry.period_id == period.id,
                    FunctionalEvalAttendanceEntry.work_date == attendance_date,
                )
                .count()
            )
    return {
        "id": period.id,
        "title": period.title,
        "deadline_date": period.deadline_date,
        "is_active": period.is_active,
        "is_closed": period_is_closed(period),
        "evaluation_open": evaluation_is_open(),
        "evaluation_opens_at": evaluation_opens_at_kst_iso(),
        "evaluation_opens_at_label": evaluation_opens_at_kst_label(),
        "last_attendance_date": attendance_date,
        "attendance_row_count": attendance_count,
        "created_at": period.created_at,
        "updated_at": period.updated_at,
    }


def violation_catalog_public() -> list[dict[str, Any]]:
    return [
        {
            "code": v.code,
            "category": v.category,
            "category_label": v.category_label,
            "label": v.label,
            "sanction_rule": v.sanction_rule,
            "sort_order": v.sort_order,
        }
        for v in VIOLATION_CATALOG
    ]


def _is_hq_safety_user(user: User) -> bool:
    role = user.role if isinstance(user.role, Role) else Role(str(user.role))
    return role in HQ_SAFE_WORKSPACE_ROLES


def _user_brief(db: Session, user_id: int | None) -> tuple[str | None, str | None]:
    if not user_id:
        return None, None
    row = db.query(User).filter(User.id == user_id).first()
    if row is None:
        return None, None
    return (row.name or "").strip() or None, (row.login_id or "").strip() or None


def _worker_ids_same_person(db: Session, worker: FunctionalEvalWorker) -> list[int]:
    return [
        row.id
        for row in db.query(FunctionalEvalWorker.id).filter(FunctionalEvalWorker.rrn_hash == worker.rrn_hash).all()
    ]


def _strike_sequence_for_person(db: Session, rrn_hash: str) -> dict[int, int]:
    """동일인·동일 위반코드 기준 누적 차수(기간 무관). 승인된 제재만 집계."""
    worker_ids = [
        row.id for row in db.query(FunctionalEvalWorker.id).filter(FunctionalEvalWorker.rrn_hash == rrn_hash).all()
    ]
    if not worker_ids:
        return {}
    rows = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.worker_id.in_(worker_ids),
            FunctionalEvalSanction.status == SANCTION_STATUS_APPROVED,
        )
        .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
        .all()
    )
    per_code: dict[str, int] = {}
    out: dict[int, int] = {}
    for row in rows:
        per_code[row.violation_code] = per_code.get(row.violation_code, 0) + 1
        out[row.id] = per_code[row.violation_code]
    return out


def _effective_strike_number(row: FunctionalEvalSanction, strike_sequence: dict[int, int] | None) -> int:
    if strike_sequence and row.id in strike_sequence:
        return strike_sequence[row.id]
    return row.strike_number


def _serialize_sanction(
    row: FunctionalEvalSanction,
    worker_name: str,
    db: Session | None = None,
    *,
    strike_sequence: dict[int, int] | None = None,
) -> dict[str, Any]:
    item = VIOLATION_BY_CODE.get(row.violation_code)
    reporter_name: str | None = None
    reporter_login: str | None = None
    if db is not None:
        reporter_name, reporter_login = _user_brief(db, row.reported_by_user_id)
    strike = _effective_strike_number(row, strike_sequence)
    display_label = build_sanction_display_label(row.violation_code, strike, row.sanction_result)
    return {
        "id": row.id,
        "period_id": row.period_id,
        "worker_id": row.worker_id,
        "site_code": row.site_code,
        "worker_name": worker_name,
        "violation_code": row.violation_code,
        "violation_label": item.label if item else row.violation_code,
        "violation_category": row.violation_category,
        "violation_category_label": item.category_label if item else row.violation_category,
        "strike_number": strike,
        "sanction_result": row.sanction_result,
        "sanction_result_label": SANCTION_RESULT_LABELS.get(row.sanction_result, row.sanction_result),
        "institutional_sanction_label": institutional_sanction_label(row.sanction_result),
        "outcome_label": sanction_outcome_label(row.sanction_result),
        "sanction_display_label": display_label,
        "is_hiring_ban": is_permanent_sanction(row.sanction_result),
        "note": row.note,
        "evidence_type": row.evidence_type or EVIDENCE_COMMENT,
        "evidence_type_label": "사진" if (row.evidence_type or EVIDENCE_COMMENT) == EVIDENCE_PHOTO else "코멘트",
        "evidence_photo_url": (
            f"/functional-eval/sanctions/{row.id}/evidence-photo"
            if row.evidence_photo_path
            else None
        ),
        "penalty_points": int(row.penalty_points if row.penalty_points is not None else DEFAULT_SANCTION_PENALTY_POINTS),
        "has_signature": bool((row.signature_data or "").strip()),
        "signature_url": (
            f"/functional-eval/sanctions/{row.id}/signature"
            if (row.signature_data or "").strip()
            else None
        ),
        "reported_by_user_id": row.reported_by_user_id,
        "reported_by_name": reporter_name,
        "reported_by_login_id": reporter_login,
        "status": getattr(row, "status", None) or SANCTION_STATUS_APPROVED,
        "status_label": {
            SANCTION_STATUS_PENDING: "승인 대기",
            SANCTION_STATUS_APPROVED: "승인",
            "REJECTED": "반려",
        }.get(getattr(row, "status", None) or SANCTION_STATUS_APPROVED, getattr(row, "status", None) or SANCTION_STATUS_APPROVED),
        "created_at": row.created_at,
    }


def _serialize_assessment_revision(row: FunctionalEvalAssessmentRevision, db: Session) -> dict[str, Any]:
    editor_name, editor_login = _user_brief(db, row.edited_by_user_id)
    return {
        "id": row.id,
        "worker_id": row.worker_id,
        "eval_type": row.eval_type,
        "before_grade_code": normalize_grade_code(row.before_grade_code) or row.before_grade_code,
        "after_grade_code": normalize_grade_code(row.after_grade_code) or row.after_grade_code,
        "reason": row.reason,
        "source": row.source,
        "sanction_id": row.sanction_id,
        "edited_by_user_id": row.edited_by_user_id,
        "edited_by_name": editor_name,
        "edited_by_login_id": editor_login,
        "created_at": row.created_at,
    }


def _worker_sanction_rows(db: Session, worker_id: int) -> list[FunctionalEvalSanction]:
    return (
        db.query(FunctionalEvalSanction)
        .filter(FunctionalEvalSanction.worker_id == worker_id)
        .order_by(FunctionalEvalSanction.created_at.desc(), FunctionalEvalSanction.id.desc())
        .all()
    )


def _worker_is_permanently_expelled(db: Session, worker_id: int) -> bool:
    rows = [
        r
        for r in _worker_sanction_rows(db, worker_id)
        if (getattr(r, "status", None) or SANCTION_STATUS_APPROVED) == SANCTION_STATUS_APPROVED
    ]
    return any(is_permanent_sanction(r.sanction_result) for r in rows)


def _count_approved_sanctions_for_violation(
    db: Session, worker: FunctionalEvalWorker, violation_code: str
) -> int:
    return (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.worker_id.in_(_worker_ids_same_person(db, worker)),
            FunctionalEvalSanction.violation_code == violation_code,
            FunctionalEvalSanction.status == SANCTION_STATUS_APPROVED,
        )
        .count()
    )


def _worker_sanction_status(db: Session, worker_id: int) -> tuple[str, str, int, FunctionalEvalSanction | None]:
    rows = [
        r
        for r in _worker_sanction_rows(db, worker_id)
        if (getattr(r, "status", None) or SANCTION_STATUS_APPROVED) != "REJECTED"
    ]
    if not rows:
        return "NONE", "해당 없음", 0, None
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    strike_sequence = _strike_sequence_for_person(db, worker.rrn_hash) if worker else None
    approved_rows = [
        r for r in rows if (getattr(r, "status", None) or SANCTION_STATUS_APPROVED) == SANCTION_STATUS_APPROVED
    ]
    results = [r.sanction_result for r in approved_rows]
    if results:
        status = worker_status_from_sanctions(results)
        display_row = next((r for r in approved_rows if r.sanction_result == status), approved_rows[0])
    else:
        pending = next(r for r in rows if getattr(r, "status", None) == SANCTION_STATUS_PENDING)
        status = "PENDING"
        display_row = pending
    strike = _effective_strike_number(display_row, strike_sequence)
    label = build_sanction_display_label(display_row.violation_code, strike, display_row.sanction_result)
    if status == "PENDING":
        label = f"제재 승인 대기 ({display_row.violation_code})"
    return status, label, len(rows), rows[0]


def _serialize_assessment(
    row: FunctionalEvalAssessment | None,
    eval_type: EvalType,
    *,
    bonus_points: int = 0,
    penalty_points: int = 0,
) -> dict[str, Any] | None:
    if row is None:
        return None
    required = len(get_criteria(eval_type))
    scores = row.scores_json or {}
    grade_code = normalize_grade_code(row.grade_code) or row.grade_code
    grade_label = row.grade_label or ""
    if grade_code and grade_label.endswith("등급"):
        grade_label = f"{grade_code}등급"
    total_score = int(row.total_score or 0)
    max_score = int(row.max_score or 0)
    payload: dict[str, Any] = {
        "eval_type": row.eval_type,
        "scores": scores,
        "total_score": total_score,
        "max_score": max_score,
        "grade_code": grade_code,
        "grade_label": grade_label,
        "is_complete": len(scores) >= required and required > 0,
        "updated_at": row.updated_at,
    }
    if (
        eval_type == "SAFETY"
        and payload["is_complete"]
        and max_score > 0
        and (bonus_points > 0 or penalty_points > 0)
    ):
        adjusted_total, adj_code, adj_label = apply_score_point_adjustments(
            total_score,
            max_score,
            bonus=bonus_points,
            penalty=penalty_points,
        )
        adj_code = normalize_grade_code(adj_code) or adj_code
        payload["base_total_score"] = total_score
        payload["base_grade_code"] = grade_code
        payload["total_score"] = adjusted_total
        payload["grade_code"] = adj_code
        payload["grade_label"] = f"{adj_code}등급" if adj_code else adj_label
        payload["adjustment_bonus"] = bonus_points
        payload["adjustment_penalty"] = penalty_points
    return payload


def _normalize_person_name(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", (text or "").strip()).lower()


def _normalize_login_to_name(login_id: str) -> str:
    login_id = (login_id or "").strip()
    if not login_id:
        return ""
    if "-" in login_id:
        login_id = login_id.split("-", 1)[1]
    return _normalize_person_name(login_id)


def _normalize_role_identifier(text: str) -> str:
    s = _normalize_person_name(text)
    for suffix in ("소장", "팀장", "현장소장", "현장 팀장"):
        s = s.replace(suffix, "")
    return s


def _manager_candidates_for_user(db: Session, user: User) -> set[str]:
    login_id = (user.login_id or "").strip()
    login_norm = _normalize_login_to_name(login_id)
    user_name = _normalize_role_identifier(str(getattr(user, "name", "") or ""))
    if not login_norm and not user_name:
        return set()

    candidates: set[str] = set()
    regs = db.query(FunctionalEvalSiteRegistry).all()
    for reg in regs:
        site_code = (reg.site_code or "").strip()
        if not site_code:
            continue
        manager_login = (reg.manager_login_id or "").strip()
        if login_id and manager_login and login_id == manager_login:
            candidates.add(site_code)
            continue
        manager_login_norm = _normalize_login_to_name(manager_login)
        if login_norm and manager_login_norm and manager_login_norm == login_norm:
            candidates.add(site_code)
            continue
        generated = build_eval_login_id((reg.site_alias or "").strip(), reg.manager_name or "")
        if login_norm and _normalize_login_to_name(generated) == login_norm:
            candidates.add(site_code)
            continue
        manager_name_norm = _normalize_role_identifier(reg.manager_name or "")
        if user_name and manager_name_norm and user_name == manager_name_norm:
            candidates.add(site_code)

    if user_name:
        manager_workers = (
            db.query(FunctionalEvalWorker)
            .filter(
                FunctionalEvalWorker.is_site_manager.is_(True),
                FunctionalEvalWorker.is_active.is_(True),
                FunctionalEvalWorker.assigned_evaluator_login_id.isnot(None),
            )
            .all()
        )
        for worker in manager_workers:
            worker_name = _normalize_role_identifier(str(worker.name or ""))
            if worker_name and user_name == worker_name:
                candidates.add((worker.site_code or "").strip())
            mw_login = _normalize_login_to_name(worker.assigned_evaluator_login_id or "")
            if login_norm and mw_login and mw_login == login_norm:
                candidates.add((worker.site_code or "").strip())

    candidates.discard("")
    return candidates


def _is_team_leader_self_target(
    db: Session, user: User, worker: FunctionalEvalWorker, site_alias: str | None = None
) -> bool:
    """팀장 로그인의 경우 팀장 본인 대상 평가는 막는다."""
    login_id = (user.login_id or "").strip()
    if not login_id:
        return False
    user_name = _normalize_person_name(str(getattr(user, "name", "") or ""))
    if not user_name:
        user_name = _normalize_login_to_name(user.login_id or "")
    if not user_name:
        return False
    worker_name = _normalize_person_name(str(worker.name or ""))
    if not worker_name or user_name != worker_name:
        return False
    assigned = (worker.assigned_evaluator_login_id or "").strip()
    login_norm = _normalize_login_to_name(login_id)
    if assigned and assigned != login_id:
        return False
    if assigned == login_id:
        return True
    if not assigned:
        return login_norm == worker_name
    if site_alias is None:
        reg = (
            db.query(FunctionalEvalSiteRegistry)
            .filter(FunctionalEvalSiteRegistry.site_code == worker.site_code)
            .first()
        )
        site_alias = (reg.site_alias or "").strip() if reg else ""
    site_alias = (site_alias or worker.site_code or "").strip()
    expected = build_eval_login_id(site_alias, worker.name)
    return bool(expected and _normalize_person_name(expected) == _normalize_person_name(login_id))


def _assessments_map(db: Session, worker_ids: list[int]) -> dict[int, dict[str, FunctionalEvalAssessment]]:
    if not worker_ids:
        return {}
    rows = (
        db.query(FunctionalEvalAssessment)
        .filter(FunctionalEvalAssessment.worker_id.in_(worker_ids))
        .all()
    )
    out: dict[int, dict[str, FunctionalEvalAssessment]] = {}
    for row in rows:
        out.setdefault(row.worker_id, {})[row.eval_type] = row
    return out


EVAL_ASSIGNMENT_DIRECT = "DIRECT"
EVAL_ASSIGNMENT_TEAM = "TEAM"
EVAL_ASSIGNMENT_TEAM_LEADER = "TEAM_LEADER"

EVAL_ASSIGNMENT_LABELS = {
    EVAL_ASSIGNMENT_DIRECT: "직영",
    EVAL_ASSIGNMENT_TEAM: "팀원",
    EVAL_ASSIGNMENT_TEAM_LEADER: "팀장",
}


def _collect_team_leader_evaluator_logins(
    rows: list[FunctionalEvalWorker],
    manager_login: str,
    *,
    db: Session | None = None,
    site_code: str | None = None,
    period_id: int | None = None,
) -> set[str]:
    """팀원에게 배정된 팀장 로그인 ID 집합(이름 기준 dedupe)."""
    if db is not None and site_code and period_id is not None:
        from app.modules.functional_eval.team_leader_login import collect_team_leader_evaluator_logins_deduped

        return collect_team_leader_evaluator_logins_deduped(
            db,
            rows,
            manager_login,
            site_code=site_code,
            period_id=period_id,
        )
    manager_login = (manager_login or "").strip()
    logins: set[str] = set()
    for row in rows:
        assigned = (row.assigned_evaluator_login_id or "").strip()
        if assigned and assigned != manager_login:
            logins.add(assigned)
    return logins


def serialize_worker(
    db: Session,
    worker: FunctionalEvalWorker,
    *,
    assessments: dict[str, FunctionalEvalAssessment] | None = None,
    team_leader_logins: set[str] | None = None,
) -> dict[str, Any]:
    status, status_label, count, latest = _worker_sanction_status(db, worker.id)
    permanent = _worker_is_permanently_expelled(db, worker.id)
    strike_sequence = _strike_sequence_for_person(db, worker.rrn_hash)
    if assessments is None:
        assessments = _assessments_map(db, [worker.id]).get(worker.id, {})
    penalty_total = _worker_penalty_points_total(db, worker.id)
    bonus_total = _worker_bonus_points_total(db, worker.id)
    functional = _serialize_assessment(assessments.get("FUNCTIONAL"), "FUNCTIONAL")
    safety = _serialize_assessment(
        assessments.get("SAFETY"),
        "SAFETY",
        bonus_points=bonus_total,
        penalty_points=penalty_total,
    )
    eval_assignment = _worker_eval_assignment(db, worker, team_leader_logins=team_leader_logins)
    payload: dict[str, Any] = {
        "id": worker.id,
        "period_id": worker.period_id,
        "site_code": worker.site_code,
        "site_name": worker.site_name,
        "row_no": worker.row_no,
        "name": worker.name,
        "age_label": worker.age_label,
        "position_name": worker.position_name,
        "job_name": worker.job_name,
        "rrn_masked": worker.rrn_masked,
        "phone_mobile": worker.phone_mobile,
        "assigned_evaluator_login_id": worker.assigned_evaluator_login_id,
        "eval_assignment": eval_assignment,
        "eval_assignment_label": EVAL_ASSIGNMENT_LABELS.get(eval_assignment, ""),
        "is_site_manager": worker.is_site_manager,
        "is_active": worker.is_active,
        "sanction_status": status,
        "sanction_status_label": status_label if status != "NONE" else "해당 없음",
        "sanction_count": count,
        "is_permanently_expelled": permanent,
        "history_visible": not permanent,
        "latest_sanction": (
            _serialize_sanction(latest, worker.name, db, strike_sequence=strike_sequence)
            if latest and not permanent
            else None
        ),
        "mileage": serialize_worker_adjustments(db, worker),
        "adjustments": serialize_worker_adjustments(db, worker),
        "penalty_points_total": penalty_total,
        "bonus_points_total": bonus_total,
        "functional_assessment": functional,
        "safety_assessment": safety,
        "mileage_note": worker.mileage_note,
        "evaluation_batch": worker.evaluation_batch or 0,
        "evaluation_batch_label": batch_label(worker.evaluation_batch or 0),
    }
    payload["remark"] = build_worker_remark(db, worker, payload, include_eval_status=True)
    payload["note"] = payload["remark"]
    approved = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.worker_id == worker.id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_APPROVED,
        )
        .order_by(FunctionalEvalCustomerReward.reviewed_at.desc())
        .first()
    )
    pending = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.worker_id == worker.id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_PENDING,
        )
        .order_by(FunctionalEvalCustomerReward.created_at.desc())
        .first()
    )
    reward = approved or pending
    if reward is not None:
        payload["customer_reward"] = {
            "id": reward.id,
            "status": reward.status,
            "bonus_points": reward.bonus_points,
            "photo_url": f"/functional-eval/customer-rewards/{reward.id}/photo",
        }
        if approved is not None:
            full = settings.storage_root / approved.photo_path
            if full.is_file():
                payload["reward_photo_path"] = str(full)
    return payload


GRADE_SORT_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3}


def _grade_sort_key(assessment: dict[str, Any] | None) -> tuple[int, int, str]:
    if not assessment or not assessment.get("is_complete"):
        return (1, 99, "")
    code = normalize_grade_code(str(assessment.get("grade_code") or "")) or ""
    return (0, GRADE_SORT_ORDER.get(code, 50), code)


def _eval_grade_label(assessment: dict[str, Any] | None) -> str:
    if not assessment or not assessment.get("is_complete"):
        return "미평가"
    return str(assessment.get("grade_label") or assessment.get("grade_code") or "—")


def _is_fully_evaluated(worker_payload: dict[str, Any]) -> bool:
    f = worker_payload.get("functional_assessment") or {}
    s = worker_payload.get("safety_assessment") or {}
    return bool(f.get("is_complete")) and bool(s.get("is_complete"))


def _worker_needs_highlight(worker_payload: dict[str, Any]) -> bool:
    sanction = str(worker_payload.get("sanction_status") or "").strip().upper()
    if sanction and sanction != "NONE":
        return True
    for key in ("functional_assessment", "safety_assessment"):
        assessment = worker_payload.get(key) or {}
        if not assessment.get("is_complete"):
            continue
        if normalize_grade_code(str(assessment.get("grade_code") or "")) == "C":
            return True
    return False


def _worker_sanction_remark_lines(db: Session, worker_id: int, *, permanent: bool) -> list[str]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    strike_sequence = _strike_sequence_for_person(db, worker.rrn_hash) if worker else None
    rows = (
        db.query(FunctionalEvalSanction)
        .filter(FunctionalEvalSanction.worker_id == worker_id)
        .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
        .all()
    )
    if permanent and rows:
        rows = rows[-1:]
    lines: list[str] = []
    for row in rows:
        strike = _effective_strike_number(row, strike_sequence)
        inst = build_sanction_display_label(row.violation_code, strike, row.sanction_result)
        penalty = int(row.penalty_points if row.penalty_points is not None else DEFAULT_SANCTION_PENALTY_POINTS)
        reason = (row.note or "").strip()
        if penalty > 0:
            if reason:
                lines.append(f"제재:{inst}(-{penalty}):{reason}")
            else:
                lines.append(f"제재:{inst}(-{penalty})")
        elif reason:
            lines.append(f"제재:{inst}:{reason}")
        else:
            lines.append(f"제재:{inst}")
    return lines


def build_worker_remark(
    db: Session,
    worker: FunctionalEvalWorker,
    worker_payload: dict[str, Any],
    *,
    include_eval_status: bool = True,
) -> str:
    parts: list[str] = []
    if include_eval_status:
        f = worker_payload.get("functional_assessment") or {}
        s = worker_payload.get("safety_assessment") or {}
        if not f.get("is_complete"):
            parts.append("기능미완")
        if not s.get("is_complete"):
            parts.append("안전미완")

    mileage_note = (worker.mileage_note or "").strip()
    bonus = _worker_bonus_points_total(db, worker.id)
    if bonus > 0:
        parts.append(f"고객사포상(+{bonus})")
    elif mileage_note == CUSTOMER_REWARD_NOTE:
        parts.append("고객사포상")

    penalty_total = _worker_penalty_points_total(db, worker.id)
    if penalty_total > 0:
        parts.append(f"감점(-{penalty_total})")

    parts.extend(
        _worker_sanction_remark_lines(
            db,
            worker.id,
            permanent=bool(worker_payload.get("is_permanently_expelled")),
        )
    )
    return " · ".join(parts) if parts else "—"


def _worker_eval_remark(db: Session, worker: FunctionalEvalWorker, worker_payload: dict[str, Any]) -> str:
    return build_worker_remark(db, worker, worker_payload, include_eval_status=True)


def _remark_for_completed_worker(db: Session, worker: FunctionalEvalWorker, worker_payload: dict[str, Any]) -> str:
    return build_worker_remark(db, worker, worker_payload, include_eval_status=False)


def _site_name_map(db: Session, site_codes: set[str]) -> dict[str, str]:
    if not site_codes:
        return {}
    rows = db.query(Site).filter(Site.site_code.in_(site_codes)).all()
    return {s.site_code: s.site_name for s in rows if s.site_code}


def _registry_erp_label_map(db: Session, site_codes: set[str]) -> dict[str, str]:
    if not site_codes:
        return {}
    from app.modules.functional_eval.eval_provisioning import normalize_erp_site_label
    from app.modules.functional_eval.models import FunctionalEvalSiteRegistry

    rows = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code.in_(site_codes))
        .all()
    )
    return {
        row.site_code: normalize_erp_site_label(row.erp_site_label)
        for row in rows
        if row.site_code and (row.erp_site_label or "").strip()
    }


def _resolve_worker_site_display_name(
    site_code: str,
    *,
    worker_site_name: str | None,
    site_names: dict[str, str],
    erp_labels: dict[str, str],
) -> str:
    erp = erp_labels.get(site_code) or ""
    registered = (site_names.get(site_code) or "").strip()
    if erp:
        return erp
    worker_label = (worker_site_name or "").strip()
    if worker_label and not worker_label.startswith(f"현장 {site_code}"):
        return worker_label
    if registered and not registered.startswith(f"현장 {site_code}"):
        return registered
    return registered or worker_label or f"현장 {site_code}"


def _site_evaluator_map(db: Session, site_codes: set[str]) -> dict[str, str]:
    if not site_codes:
        return {}
    out: dict[str, str] = {}
    regs = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code.in_(site_codes))
        .all()
    )
    login_ids = set(site_codes)
    login_ids.update(r.manager_login_id for r in regs if r.manager_login_id)
    users = (
        db.query(User)
        .filter(User.role == Role.SITE_FUNCTIONAL_EVAL, User.login_id.in_(login_ids))
        .all()
    )
    by_login = {u.login_id: u.name for u in users if u.login_id}
    for reg in regs:
        out[reg.site_code] = by_login.get(reg.manager_login_id) or reg.manager_name
    for code in site_codes:
        if code not in out and code in by_login:
            out[code] = by_login[code]
    return out


HQ_SITE_BUCKET_IN_PROGRESS = "in_progress"
HQ_SITE_BUCKET_NOT_STARTED = "not_started"
HQ_SITE_BUCKET_COMPLETED = "completed"


def classify_hq_site_bucket(*, fully_complete: int, total: int) -> str:
    """본사 대시보드 — 현장 진행 구분."""
    total = int(total or 0)
    fully_complete = int(fully_complete or 0)
    if total <= 0:
        return HQ_SITE_BUCKET_NOT_STARTED
    if fully_complete >= total:
        return HQ_SITE_BUCKET_COMPLETED
    if fully_complete <= 0:
        return HQ_SITE_BUCKET_NOT_STARTED
    return HQ_SITE_BUCKET_IN_PROGRESS


def _hq_site_bucket_label(bucket: str) -> str:
    return {
        HQ_SITE_BUCKET_IN_PROGRESS: "진행 중",
        HQ_SITE_BUCKET_NOT_STARTED: "미평가",
        HQ_SITE_BUCKET_COMPLETED: "평가 완료",
    }.get(bucket, bucket)


def _summarize_hq_site_buckets(sites: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        HQ_SITE_BUCKET_IN_PROGRESS: 0,
        HQ_SITE_BUCKET_NOT_STARTED: 0,
        HQ_SITE_BUCKET_COMPLETED: 0,
    }
    for row in sites:
        bucket = row.get("bucket") or HQ_SITE_BUCKET_NOT_STARTED
        if bucket in counts:
            counts[bucket] += 1
    return {
        "in_progress": counts[HQ_SITE_BUCKET_IN_PROGRESS],
        "not_started": counts[HQ_SITE_BUCKET_NOT_STARTED],
        "completed": counts[HQ_SITE_BUCKET_COMPLETED],
        "labels": {
            HQ_SITE_BUCKET_IN_PROGRESS: _hq_site_bucket_label(HQ_SITE_BUCKET_IN_PROGRESS),
            HQ_SITE_BUCKET_NOT_STARTED: _hq_site_bucket_label(HQ_SITE_BUCKET_NOT_STARTED),
            HQ_SITE_BUCKET_COMPLETED: _hq_site_bucket_label(HQ_SITE_BUCKET_COMPLETED),
        },
    }


def _hq_evaluator_site_codes(db: Session) -> set[str]:
    """본사 현장 목록 — 소장 계정(별칭-이름)이 있는 현장코드."""
    codes = {r.site_code for r in db.query(FunctionalEvalSiteRegistry.site_code).all() if r[0]}
    for user in db.query(User).filter(User.role == Role.SITE_FUNCTIONAL_EVAL).all():
        if user.site_id:
            site = db.query(Site).filter(Site.id == user.site_id).first()
            if site and site.site_code:
                codes.add(site.site_code)
        elif (user.login_id or "").strip().isdigit():
            codes.add(str(user.login_id).strip())
    return codes


def build_site_progress(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_site: dict[str, dict[str, Any]] = {}
    for item in items:
        w = item["worker"]
        code = w.get("site_code") or ""
        if code not in by_site:
            by_site[code] = {
                "site_code": code,
                "site_name": w.get("site_name") or f"현장 {code}",
                "total": 0,
                "fully_complete": 0,
                "functional_complete": 0,
                "safety_complete": 0,
                "incomplete": 0,
            }
        row = by_site[code]
        row["total"] += 1
        f = w.get("functional_assessment") or {}
        s = w.get("safety_assessment") or {}
        if f.get("is_complete"):
            row["functional_complete"] += 1
        if s.get("is_complete"):
            row["safety_complete"] += 1
        if _is_fully_evaluated(w):
            row["fully_complete"] += 1
        else:
            row["incomplete"] += 1
    return sorted(by_site.values(), key=lambda x: str(x["site_code"]))


def _aggregate_site_eval_stats(
    workers: list[FunctionalEvalWorker],
    assess_map: dict[int, dict[str, Any]],
    site_names: dict[str, str],
    evaluators: dict[str, str],
    *,
    erp_labels: dict[str, str] | None = None,
    rep_evaluators: dict[str, str] | None = None,
    evaluator_site_codes: set[str] | None = None,
) -> list[dict[str, Any]]:
    erp_labels = erp_labels or {}
    rep_evaluators = rep_evaluators or {}
    evaluator_site_codes = evaluator_site_codes if evaluator_site_codes is not None else set(evaluators)
    by_site: dict[str, dict[str, Any]] = {}
    for worker in workers:
        code = worker.site_code or ""
        if code not in by_site:
            missing_ev = code not in evaluator_site_codes and code not in evaluators
            ev_name = evaluators.get(code) or ""
            if not ev_name and rep_evaluators.get(code):
                ev_name = f"{rep_evaluators[code]} (출역 대표)"
            if not ev_name:
                ev_name = "—"
            by_site[code] = {
                "site_code": code,
                "site_name": _resolve_site_display_name(code, site_names, erp_labels),
                "evaluator_name": ev_name,
                "evaluator_missing": missing_ev,
                "total": 0,
                "fully_complete": 0,
            }
        row = by_site[code]
        row["total"] += 1
        payload = _worker_assess_payload(assess_map, worker.id)
        if _is_fully_evaluated(payload):
            row["fully_complete"] += 1
    sites: list[dict[str, Any]] = []
    for row in by_site.values():
        fc = int(row["fully_complete"])
        total = int(row["total"])
        row["progress"] = f"{fc}/{total}"
        row["progress_pct"] = round((fc / total) * 100) if total > 0 else 0
        row["has_completed"] = fc > 0
        row["bucket"] = classify_hq_site_bucket(fully_complete=fc, total=total)
        row["bucket_label"] = _hq_site_bucket_label(row["bucket"])
        sites.append(row)
    return sites


def _attendance_target_workers(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_code: str | None = None,
) -> list[FunctionalEvalWorker]:
    """기간 내 출역 이력이 있는 근로자(평가·HQ 진행률 대상)."""
    rrn_hashes = _period_attendance_rrn_hashes(db, period.id, site_code=site_code)
    if not rrn_hashes:
        return []
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_site_manager.is_(False),
        FunctionalEvalWorker.rrn_hash.in_(rrn_hashes),
    )
    if site_code:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    return q.all()


def _workers_with_any_assessment(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_code: str | None = None,
) -> list[FunctionalEvalWorker]:
    assessed_worker_ids = {
        worker_id
        for (worker_id,) in db.query(FunctionalEvalAssessment.worker_id)
        .distinct()
        .all()
    }
    if not assessed_worker_ids:
        return []
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.id.in_(assessed_worker_ids),
        FunctionalEvalWorker.is_site_manager.is_(False),
    )
    if site_code:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    return q.all()


def _summarize_worker_eval_status(
    workers: list[FunctionalEvalWorker],
    assess_map: dict[int, dict[str, Any]],
) -> dict[str, int]:
    counts = {"not_started": 0, "in_progress": 0, "completed": 0}
    for worker in workers:
        payload = _worker_assess_payload(assess_map, worker.id)
        if _is_fully_evaluated(payload):
            counts["completed"] += 1
        elif (payload.get("functional_assessment") or {}).get("is_complete") or (
            payload.get("safety_assessment") or {}
        ).get("is_complete"):
            counts["in_progress"] += 1
        else:
            counts["not_started"] += 1
    return counts


def _list_eval_complete_site_submit_blockers(
    db: Session,
    period: FunctionalEvalPeriod,
) -> list[dict[str, Any]]:
    """전원 평가 완료였으나 본사 검토·서명 전인 현장 — 차단 사유."""
    from app.modules.functional_eval import approval_workflow, signature_ops
    from app.modules.functional_eval.constants import (
        APPROVAL_STATUS_CEO_APPROVED,
        APPROVAL_STATUS_HQ_APPROVED,
        APPROVAL_STATUS_HQ_OFFICER_APPROVED,
        APPROVAL_STATUS_SITE_APPROVED,
    )

    workers = _attendance_target_workers(db, period)
    site_codes = sorted({w.site_code for w in workers if w.site_code})
    site_names = _site_name_map(db, set(site_codes))
    blockers: list[dict[str, Any]] = []

    for site_code in site_codes:
        summary = serialize_site_approval_summary(db, period, site_code)
        total = int(summary.get("site_total_workers") or 0)
        complete = int(summary.get("site_complete_workers") or 0)
        if total <= 0 or complete < total:
            continue

        approval = approval_workflow.get_or_create_site_approval(db, period.id, site_code)
        if approval.status in {
            APPROVAL_STATUS_SITE_APPROVED,
            APPROVAL_STATUS_HQ_OFFICER_APPROVED,
            APPROVAL_STATUS_HQ_APPROVED,
            APPROVAL_STATUS_CEO_APPROVED,
        }:
            continue

        batches = signature_ops.active_site_batches(db, period, site_code)
        batch = max(batches) if batches else 0
        team_signed = signature_ops.all_team_leaders_signed(db, period, site_code, batch)
        if not team_signed:
            blocker_label = "팀장 평가완료보고서 미서명"
            blocker_stage = "team_leader_signoff"
        elif approval_workflow.is_site_evaluation_editable(approval.status):
            blocker_label = "소장 최종 제출 대기"
            blocker_stage = "site_manager_submit"
        else:
            continue

        blockers.append(
            {
                "site_code": site_code,
                "site_name": site_names.get(site_code) or f"현장 {site_code}",
                "blocker_label": blocker_label,
                "blocker_stage": blocker_stage,
                "team_leaders_all_signed": team_signed,
                "site_complete_workers": complete,
                "site_total_workers": total,
            }
        )
    return blockers


def _list_eval_complete_site_submit_blockers_from_progress(
    db: Session,
    period: FunctionalEvalPeriod,
    site_progress: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from app.modules.functional_eval.constants import (
        APPROVAL_STATUS_CEO_APPROVED,
        APPROVAL_STATUS_HQ_APPROVED,
        APPROVAL_STATUS_HQ_OFFICER_APPROVED,
        APPROVAL_STATUS_SITE_APPROVED,
    )

    submitted_statuses = {
        APPROVAL_STATUS_SITE_APPROVED,
        APPROVAL_STATUS_HQ_OFFICER_APPROVED,
        APPROVAL_STATUS_HQ_APPROVED,
        APPROVAL_STATUS_CEO_APPROVED,
    }
    approval_rows = (
        db.query(FunctionalEvalSiteApproval)
        .filter(FunctionalEvalSiteApproval.period_id == period.id)
        .all()
    )
    status_by_site = {row.site_code: row.status for row in approval_rows}
    blockers: list[dict[str, Any]] = []
    for row in site_progress:
        site_code = str(row.get("site_code") or "")
        total = int(row.get("total") or row.get("site_total_workers") or 0)
        complete = int(row.get("fully_complete") or row.get("site_complete_workers") or 0)
        if not site_code or total <= 0 or complete < total:
            continue
        if status_by_site.get(site_code) in submitted_statuses:
            continue
        blockers.append(
            {
                "site_code": site_code,
                "site_name": row.get("site_name") or f"현장 {site_code}",
                "blocker_label": "소장 최종 제출 대기",
                "blocker_stage": "site_manager_submit",
                "team_leaders_all_signed": True,
                "site_complete_workers": complete,
                "site_total_workers": total,
            }
        )
    return blockers


def build_hq_review_queue(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_progress: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval.constants import (
        APPROVAL_STATUS_HQ_APPROVED,
        APPROVAL_STATUS_HQ_OFFICER_APPROVED,
        APPROVAL_STATUS_SITE_APPROVED,
    )

    pending_reward_count = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.period_id == period.id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_PENDING,
        )
        .count()
    )
    pending_sanction_count = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.period_id == period.id,
            FunctionalEvalSanction.status == SANCTION_STATUS_PENDING,
        )
        .count()
    )
    pending_officer_count = (
        db.query(FunctionalEvalSiteApproval)
        .filter(
            FunctionalEvalSiteApproval.period_id == period.id,
            FunctionalEvalSiteApproval.status == APPROVAL_STATUS_SITE_APPROVED,
        )
        .count()
    )
    pending_director_count = (
        db.query(FunctionalEvalSiteApproval)
        .filter(
            FunctionalEvalSiteApproval.period_id == period.id,
            FunctionalEvalSiteApproval.status == APPROVAL_STATUS_HQ_OFFICER_APPROVED,
        )
        .count()
    )
    pending_ceo_count = (
        db.query(FunctionalEvalSiteApproval)
        .filter(
            FunctionalEvalSiteApproval.period_id == period.id,
            FunctionalEvalSiteApproval.status == APPROVAL_STATUS_HQ_APPROVED,
        )
        .count()
    )
    site_submit_blockers = (
        _list_eval_complete_site_submit_blockers_from_progress(db, period, site_progress)
        if site_progress is not None
        else _list_eval_complete_site_submit_blockers(db, period)
    )
    evidence_sites = {
        code
        for (code,) in db.query(FunctionalEvalSanction.site_code)
        .filter(FunctionalEvalSanction.period_id == period.id)
        .distinct()
        .all()
        if code
    } | {
        code
        for (code,) in db.query(FunctionalEvalWorker.site_code)
        .join(FunctionalEvalCustomerReward, FunctionalEvalCustomerReward.worker_id == FunctionalEvalWorker.id)
        .filter(FunctionalEvalCustomerReward.period_id == period.id)
        .distinct()
        .all()
        if code
    }

    return {
        "pending_reward_count": pending_reward_count,
        "pending_sanction_count": pending_sanction_count,
        "pending_hq_officer_site_count": pending_officer_count,
        "pending_hq_director_site_count": pending_director_count,
        "pending_hq_site_count": pending_officer_count + pending_director_count,
        "pending_ceo_site_count": pending_ceo_count,
        "total_hq_action_count": pending_reward_count + pending_sanction_count + pending_officer_count + pending_director_count,
        "sites_with_evidence_count": len(evidence_sites),
        "eval_complete_not_submitted_count": len(site_submit_blockers),
        "site_submit_blockers": site_submit_blockers,
    }

def build_hq_sites_overview(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
    include_inactive: bool = False,
) -> dict[str, Any]:
    """본사 현장 목록. 기본은 출역 근로자 기준, include_inactive면 평가 이력 근로자도 포함."""
    workers = _attendance_target_workers(db, period, site_code=site_code)
    assessed_workers: list[FunctionalEvalWorker] = []
    if include_inactive:
        assessed_workers = _workers_with_any_assessment(db, period, site_code=site_code)
    seen_worker_ids = {w.id for w in workers}
    for assessed_worker in assessed_workers:
        if assessed_worker.id not in seen_worker_ids:
            workers.append(assessed_worker)
            seen_worker_ids.add(assessed_worker.id)
    all_worker_ids = [w.id for w in workers]
    assess_map = _assessments_map(db, all_worker_ids)
    attendance_site_codes, erp_labels, rep_evaluators = _attendance_site_meta(db, period.id)
    if site_code:
        attendance_site_codes = {site_code} & attendance_site_codes

    all_codes = attendance_site_codes | {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, all_codes)
    evaluator_site_codes = _hq_evaluator_site_codes(db)
    evaluators = _site_evaluator_map(db, all_codes)
    sites = _aggregate_site_eval_stats(
        workers,
        assess_map,
        site_names,
        evaluators,
        erp_labels=erp_labels,
        rep_evaluators=rep_evaluators,
        evaluator_site_codes=evaluator_site_codes,
    )
    for row in sites:
        row["attendance_pending"] = False

    has_attendance = bool(attendance_site_codes)
    worker_status_counts = _summarize_worker_eval_status(workers, assess_map)
    gaps = {
        "sites_missing_evaluator_account": sorted(
            code for code in attendance_site_codes if code not in evaluator_site_codes
        ),
        "evaluator_sites_without_attendance": sorted(
            code for code in evaluator_site_codes if code not in attendance_site_codes
        ),
    }

    reverse = sort_dir.lower() == "desc"

    def _key(row: dict[str, Any]) -> Any:
        if sort_by == "site_name":
            return (row.get("site_name") or "", row.get("site_code") or "")
        if sort_by == "evaluator_name":
            return row.get("evaluator_name") or ""
        if sort_by == "progress":
            return (row.get("fully_complete") or 0, row.get("total") or 0)
        return row.get("site_code") or ""

    sites.sort(key=_key, reverse=reverse)
    total_workers = len(workers)
    fully = sum(1 for w in workers if _is_fully_evaluated(_worker_assess_payload(assess_map, w.id)))
    attendance_message = None
    if not has_attendance:
        attendance_message = (
            "출역일보가 아직 반영되지 않았습니다. 「명부·제재 관리」에서 출역일보를 업로드하면 "
            "현장별 진행률(완료/출역대상)이 표시됩니다."
        )
    return {
        "period": serialize_period(period, db),
        "attendance_message": attendance_message,
        "gaps": gaps,
        "totals": {
            "sites": len(sites),
            "workers": total_workers,
            "fully_complete": fully,
            "incomplete": total_workers - fully,
        },
        "worker_status_counts": worker_status_counts,
        "site_buckets": _summarize_hq_site_buckets(sites),
        "review_queue": build_hq_review_queue(db, period, site_progress=sites),
        "sites": sites,
        # 구버전 프론트( site_progress 키 ) 호환
        "site_progress": sites,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


def _worker_assess_payload(
    assess_map: dict[int, dict[str, FunctionalEvalAssessment]],
    worker_id: int,
) -> dict[str, Any]:
    assessments = assess_map.get(worker_id, {})
    return {
        "functional_assessment": _serialize_assessment(assessments.get("FUNCTIONAL"), "FUNCTIONAL"),
        "safety_assessment": _serialize_assessment(assessments.get("SAFETY"), "SAFETY"),
    }


def build_hq_eval_rows(items: list[dict[str, Any]], *, completed_only: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        w = item["worker"]
        if completed_only and not _is_fully_evaluated(w):
            continue
        f = w.get("functional_assessment") or {}
        s = w.get("safety_assessment") or {}
        fully = _is_fully_evaluated(w)
        if fully:
            eval_status = "completed"
            eval_status_label = "완료"
        elif f.get("is_complete") or s.get("is_complete"):
            eval_status = "in_progress"
            eval_status_label = "진행 중"
        else:
            eval_status = "not_started"
            eval_status_label = "미평가"
        rows.append(
            {
                "worker_id": w["id"],
                "site_code": w.get("site_code"),
                "site_name": w.get("site_name"),
                "name": w.get("name"),
                "is_active": w.get("is_active"),
                "is_permanently_expelled": w.get("is_permanently_expelled"),
                "sanction_count": w.get("sanction_count") or 0,
                "functional_grade": _eval_grade_label(f),
                "safety_grade": _eval_grade_label(s),
                "functional_score": f.get("total_score"),
                "safety_score": s.get("total_score"),
                "remark": w.get("remark") or "—",
                "is_fully_complete": fully,
                "eval_status": eval_status,
                "eval_status_label": eval_status_label,
                "needs_highlight": _worker_needs_highlight(w),
            }
        )
    return rows


def list_hq_site_completed_evaluations(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
    *,
    sort_by: str = "name",
    sort_dir: str = "asc",
) -> dict[str, Any]:
    items = list_hq_summary(
        db,
        period,
        sort_by=sort_by,
        sort_dir=sort_dir,
        site_code=site_code,
        include_inactive=True,
    )
    site_names = _site_name_map(db, {site_code})
    evaluators = _site_evaluator_map(db, {site_code})
    total = len(items)
    fully = sum(1 for i in items if _is_fully_evaluated(i["worker"]))
    first = items[0]["worker"] if items else {}
    site_row = {
        "site_code": site_code,
        "site_name": first.get("site_name") or site_names.get(site_code) or f"현장 {site_code}",
        "evaluator_name": evaluators.get(site_code) or "—",
        "total": total,
        "fully_complete": fully,
        "progress": f"{fully}/{total}",
        "progress_pct": round((fully / total) * 100) if total > 0 else 0,
        "has_completed": fully > 0,
        "bucket": classify_hq_site_bucket(fully_complete=fully, total=total),
        "bucket_label": _hq_site_bucket_label(classify_hq_site_bucket(fully_complete=fully, total=total)),
    }
    approval = build_site_approval_payload(db, period, site_code)
    return {
        "site": site_row,
        "eval_rows": build_hq_eval_rows(items, completed_only=False),
        "approval": approval,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


def list_hq_eval_export_rows(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_code: str | None = None,
) -> list[dict[str, Any]]:
    items = list_hq_summary(
        db,
        period,
        sort_by="site_code",
        sort_dir="asc",
        include_inactive=True,
        site_code=site_code,
    )
    rows: list[dict[str, Any]] = []
    site_codes = {item["worker"].get("site_code") for item in items if item["worker"].get("site_code")}
    evaluators = _site_evaluator_map(db, site_codes)
    for item in items:
        w = item["worker"]
        code = w.get("site_code") or ""
        fully = _is_fully_evaluated(w)
        rows.append(
            {
                "site_code": code,
                "site_name": w.get("site_name") or f"현장 {code}",
                "evaluator_name": evaluators.get(code) or "—",
                "name": w.get("name"),
                "functional_grade": _eval_grade_label(w.get("functional_assessment")),
                "safety_grade": _eval_grade_label(w.get("safety_assessment")),
                "eval_status": w.get("eval_status_label") or ("완료" if fully else "미완료"),
                "fully_complete": "Y" if fully else "N",
                "remark": w.get("remark") or "—",
            }
        )
    return rows


def list_grade_workbook_workers(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_code: str | None = None,
) -> list[dict[str, Any]]:
    """출역 대상 근로자 + 평가 데이터 (현장별 기능인등급 엑셀용)."""
    workers = _attendance_target_workers(db, period, site_code=site_code)
    workers.sort(key=lambda w: (w.site_code or "", w.row_no or 0, w.id or 0))
    site_codes = {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, site_codes)
    assess_map = _assessments_map(db, [w.id for w in workers])
    out: list[dict[str, Any]] = []
    for worker in workers:
        payload = serialize_worker(db, worker, assessments=assess_map.get(worker.id, {}))
        if not payload.get("site_name"):
            payload["site_name"] = site_names.get(worker.site_code) or f"현장 {worker.site_code}"
        apply_legacy_assessments(payload)
        out.append(payload)
    return out


def build_site_grade_workbook_bytes(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_code: str | None = None,
) -> bytes:
    from app.modules.functional_eval.site_grade_workbook import generate_site_grade_workbook_bytes

    workers = list_grade_workbook_workers(db, period, site_code=site_code)
    if not workers:
        raise ValueError("NO_ATTENDANCE_WORKERS")
    return generate_site_grade_workbook_bytes(workers)


def build_hq_summary_totals(items: list[dict[str, Any]]) -> dict[str, int]:
    workers = [item["worker"] for item in items]
    fully = sum(1 for w in workers if _is_fully_evaluated(w))
    return {
        "workers": len(workers),
        "fully_complete": fully,
        "incomplete": len(workers) - fully,
    }


def _worker_penalty_points_total(db: Session, worker_id: int) -> int:
    from sqlalchemy import func

    total = (
        db.query(func.coalesce(func.sum(FunctionalEvalSanction.penalty_points), 0))
        .filter(
            FunctionalEvalSanction.worker_id == worker_id,
            FunctionalEvalSanction.status == SANCTION_STATUS_APPROVED,
        )
        .scalar()
    )
    return int(total or 0)


def _worker_bonus_points_total(db: Session, worker_id: int) -> int:
    from sqlalchemy import func

    from app.modules.functional_eval.customer_rewards import REWARD_STATUS_APPROVED

    total = (
        db.query(func.coalesce(func.sum(FunctionalEvalCustomerReward.bonus_points), 0))
        .filter(
            FunctionalEvalCustomerReward.worker_id == worker_id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_APPROVED,
        )
        .scalar()
    )
    return int(total or 0)


def serialize_worker_adjustments(db: Session, worker: FunctionalEvalWorker) -> dict[str, Any]:
    """제재 감점·포상 가점 — 마일리지 제도와 별도, 건별 기록 합산."""
    penalty = _worker_penalty_points_total(db, worker.id)
    bonus = _worker_bonus_points_total(db, worker.id)
    payload: dict[str, Any] = {
        "penalty_points": penalty,
        "bonus_points": bonus,
    }
    if penalty > 0:
        payload["penalty_label"] = f"감점 -{penalty}점"
    if bonus > 0:
        payload["bonus_label"] = f"가점 +{bonus}점"
    if penalty > 0:
        payload["status"] = "PENALTY"
        payload["points"] = -penalty
        payload["label"] = payload["penalty_label"]
    elif bonus > 0:
        payload["status"] = "BONUS"
        payload["points"] = bonus
        payload["label"] = payload["bonus_label"]
    else:
        payload["status"] = "NONE"
        payload["points"] = 0
    return payload


def serialize_mileage_placeholder(db: Session, worker: FunctionalEvalWorker) -> dict[str, Any]:
    """하위 호환 — `/mileage` 엔드포인트. 실제로는 제재·포상 가감점 합산."""
    return serialize_worker_adjustments(db, worker)


def _site_code_for_user(user: User, db: Session) -> str:
    if user.site_id:
        site = db.query(Site).filter(Site.id == user.site_id).first()
        if site and site.site_code:
            return site.site_code
    manager_candidates = _manager_candidates_for_user(db, user)
    if len(manager_candidates) == 1:
        return next(iter(manager_candidates))
    login = (user.login_id or "").strip()
    if login.isdigit():
        return login
    login_norm = _normalize_login_to_name(login)
    if "-" in login:
        alias = login.split("-", 1)[0].strip()
        alias_norm = _normalize_person_name(alias)
        if alias_norm:
            reg = (
                db.query(FunctionalEvalSiteRegistry)
                .filter(FunctionalEvalSiteRegistry.site_alias.is_not(None))
                .all()
            )
            for row in reg:
                if _normalize_person_name(str(row.site_alias or "")) == alias_norm:
                    return row.site_code or ""
    if login_norm:
        regs = (
            db.query(FunctionalEvalSiteRegistry)
            .all()
        )
        direct_matches: set[str] = set()
        manager_name_matches: set[str] = set()
        user_name = _normalize_role_identifier(str(getattr(user, "name", "") or ""))
        for row in regs:
            site_code = row.site_code or ""
            if not site_code:
                continue
            manager_login = (row.manager_login_id or "").strip()
            if manager_login and _normalize_login_to_name(manager_login) == login_norm:
                direct_matches.add(site_code)
                continue
            if row.site_alias and row.manager_name:
                generated = build_eval_login_id(row.site_alias, row.manager_name)
                if _normalize_login_to_name(generated) == login_norm:
                    direct_matches.add(site_code)
            site_alias = _normalize_person_name(row.site_alias or "")
            manager_name = _normalize_role_identifier(row.manager_name or "")
            if manager_name and (manager_name == user_name or manager_name == login_norm):
                manager_name_matches.add(site_code)
        if len(direct_matches) == 1:
            return next(iter(direct_matches))
        if len(direct_matches) > 1:
            narrowed = set()
            manager_workers = (
                db.query(FunctionalEvalWorker)
                .filter(
                    FunctionalEvalWorker.is_site_manager.is_(True),
                    FunctionalEvalWorker.is_active.is_(True),
                )
                .all()
            )
            for mw in manager_workers:
                mw_name = _normalize_role_identifier((mw.name or ""))
                if mw_name == user_name:
                    narrowed.add(mw.site_code)
                mw_login = _normalize_login_to_name((mw.assigned_evaluator_login_id or ""))
                if login_norm and mw_login == login_norm:
                    narrowed.add(mw.site_code)
            if len(narrowed) == 1:
                return next(iter(narrowed))
            if not narrowed:
                narrowed = set()
            direct_matches = direct_matches.intersection(narrowed) if narrowed else direct_matches
            if len(direct_matches) == 1:
                return next(iter(direct_matches))
            return ""
        if len(manager_name_matches) == 1:
            return next(iter(manager_name_matches))
        if len(manager_candidates) == 1:
            return next(iter(manager_candidates))
    return ""


def _manager_login_for_site(db: Session, site_code: str) -> str:
    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    if reg and (reg.manager_login_id or "").strip():
        return reg.manager_login_id.strip()
    return site_code


def _is_manager_user_for_site(db: Session, user: User, site_code: str) -> bool:
    login_id = (user.login_id or "").strip()
    login_norm = _normalize_login_to_name(login_id)
    if not login_id and not login_norm:
        return False
    user_name = _normalize_role_identifier(str(getattr(user, "name", "") or ""))
    if not user_name:
        user_name = _normalize_login_to_name(login_id)

    if login_id == site_code:
        return True
    if login_id == _manager_login_for_site(db, site_code):
        return True

    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    if reg:
        manager_name = _normalize_role_identifier((reg.manager_name or "").strip())
        manager_login = _normalize_login_to_name(str(reg.manager_login_id or ""))
        if login_norm and manager_login and manager_login == login_norm:
            return True
        if manager_name and user_name and user_name == manager_name:
            return True
        if login_norm:
            site_alias = (reg.site_alias or "").strip()
            generated = build_eval_login_id(site_alias, reg.manager_name or "")
            if _normalize_login_to_name(generated) == login_norm:
                return True
        manager_candidates = _manager_candidates_for_user(db, user)
        if manager_candidates and site_code in manager_candidates:
            return True

    manager_workers = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.is_site_manager.is_(True),
            FunctionalEvalWorker.is_active.is_(True),
        )
        .all()
    )
    for worker in manager_workers:
        worker_name = _normalize_person_name(str(worker.name or ""))
        worker_login = _normalize_login_to_name((worker.assigned_evaluator_login_id or "").strip())
        if login_norm and worker_login and worker_login == login_norm:
            return True
        if worker_name and user_name and worker_name == user_name:
            return True
    return False


def _worker_eval_assignment(
    db: Session,
    worker: FunctionalEvalWorker,
    *,
    team_leader_logins: set[str] | None = None,
) -> str:
    """DIRECT=직영, TEAM_LEADER=팀장(소장 평가), TEAM=팀원(팀장 평가)."""
    manager_login = _manager_login_for_site(db, worker.site_code)
    assigned = (worker.assigned_evaluator_login_id or "").strip()
    if worker.is_site_manager:
        return EVAL_ASSIGNMENT_DIRECT
    if not assigned:
        return EVAL_ASSIGNMENT_DIRECT
    if assigned != manager_login:
        return EVAL_ASSIGNMENT_TEAM
    if team_leader_logins is not None:
        reg = (
            db.query(FunctionalEvalSiteRegistry)
            .filter(FunctionalEvalSiteRegistry.site_code == worker.site_code)
            .first()
        )
        site_alias = (reg.site_alias or "").strip() if reg else ""
        leader_login = build_eval_login_id(site_alias, worker.name or "")
        if leader_login and leader_login in team_leader_logins:
            return EVAL_ASSIGNMENT_TEAM_LEADER
    return EVAL_ASSIGNMENT_DIRECT


def _site_attendance_workers(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
) -> list[FunctionalEvalWorker]:
    """기간 내 출역 이력이 있는 현장 근로자(퇴사·재출역 포함, 평가·승인·서명 대상)."""
    workers = _attendance_target_workers(db, period, site_code=site_code)
    workers.sort(key=lambda w: (w.row_no or 0, w.id or 0))
    return workers


def site_worker_payloads_for_batch(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
    batch: int,
) -> list[dict[str, Any]]:
    rows = _site_attendance_workers(db, period, site_code)
    manager_login = _manager_login_for_site(db, site_code)
    team_leader_logins = _collect_team_leader_evaluator_logins(
        rows, manager_login, db=db, site_code=site_code, period_id=period.id
    )
    assess_map = _assessments_map(db, [r.id for r in rows])
    payloads: list[dict[str, Any]] = []
    for row in rows:
        if (row.evaluation_batch or 0) != batch:
            continue
        payloads.append(
            serialize_worker(
                db,
                row,
                assessments=assess_map.get(row.id, {}),
                team_leader_logins=team_leader_logins,
            )
        )
    return payloads


def serialize_site_approval_summary(db: Session, period: FunctionalEvalPeriod, site_code: str) -> dict[str, Any]:
    rows = _site_attendance_workers(db, period, site_code)
    manager_login = _manager_login_for_site(db, site_code)
    team_leader_logins = _collect_team_leader_evaluator_logins(
        rows, manager_login, db=db, site_code=site_code, period_id=period.id
    )
    assess_map = _assessments_map(db, [r.id for r in rows])
    complete = 0
    direct_total = 0
    team_total = 0
    direct_complete = 0
    team_complete = 0
    for row in rows:
        payload = serialize_worker(
            db,
            row,
            assessments=assess_map.get(row.id, {}),
            team_leader_logins=team_leader_logins,
        )
        if _is_fully_evaluated(payload):
            complete += 1
        assignment = payload.get("eval_assignment")
        if assignment in (EVAL_ASSIGNMENT_DIRECT, EVAL_ASSIGNMENT_TEAM_LEADER):
            direct_total += 1
            if _is_fully_evaluated(payload):
                direct_complete += 1
        else:
            team_total += 1
            if _is_fully_evaluated(payload):
                team_complete += 1
    approval_row = approval_workflow.get_or_create_site_approval(db, period.id, site_code)
    status = approval_row.status
    batches = sorted({r.evaluation_batch or 0 for r in rows})
    batch = batches[-1] if batches else 0
    from app.modules.functional_eval.grade_inflation_guard import compute_grade_inflation_review

    site_workers = site_worker_payloads_for_batch(db, period, site_code, batch)
    grade_review = compute_grade_inflation_review(site_workers)
    return {
        "site_total_workers": len(rows),
        "site_complete_workers": complete,
        "direct_total": direct_total,
        "direct_complete": direct_complete,
        "team_total": team_total,
        "team_complete": team_complete,
        "incomplete_count": len(rows) - complete,
        "can_submit_site_approval": complete == len(rows) and len(rows) > 0
        and approval_workflow.is_site_evaluation_editable(status),
        "can_self_reject_site_approval": status == "SITE_APPROVED",
        "evaluation_editable": approval_workflow.is_site_evaluation_editable(status),
        **grade_review,
    }


def build_site_approval_payload(db: Session, period: FunctionalEvalPeriod, site_code: str) -> dict[str, Any]:
    row = approval_workflow.get_or_create_site_approval(db, period.id, site_code)
    return {
        **approval_workflow.serialize_site_approval(row),
        **serialize_site_approval_summary(db, period, site_code),
    }


def _is_primary_site_evaluator(db: Session, user: User, site_code: str) -> bool:
    return _is_manager_user_for_site(db, user, site_code)


def _attendance_worker_count_for_site(
    db: Session,
    period_id: int,
    site_code: str,
    *,
    work_date: date | None = None,
) -> int:
    work_date = work_date or get_latest_attendance_date(db, period_id)
    if work_date is None:
        return 0
    rrn_hashes = _attendance_rrn_hashes_for_date(db, period_id, work_date, site_code=site_code)
    if not rrn_hashes:
        return 0
    rows = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.period_id == period_id,
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.is_site_manager.is_(False),
            FunctionalEvalWorker.rrn_hash.in_(rrn_hashes),
        )
        .all()
    )
    return len(rows)


def serialize_evaluator_session(db: Session, user: User, period: FunctionalEvalPeriod) -> dict[str, Any]:
    site_code = _site_code_for_user(user, db)
    login_id = (user.login_id or "").strip()
    is_manager = _is_primary_site_evaluator(db, user, site_code)
    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    site_alias = (reg.site_alias or "").strip() if reg else ""
    manager_name = (reg.manager_name or "").strip() if reg else ""
    manager_login_id = _manager_login_for_site(db, site_code)
    site_worker_count = _attendance_worker_count_for_site(db, period.id, site_code)
    workers = list_workers_for_user(db, user, period)
    approval = build_site_approval_payload(db, period, site_code) if is_manager else None
    return {
        "role": "MANAGER" if is_manager else "TEAM_LEADER",
        "role_label": "소장" if is_manager else "팀장",
        "eval_scope_label": (
            "직영 평가"
            if is_manager and site_worker_count > TEAM_LEADER_SPLIT_THRESHOLD
            else ("전원 평가" if is_manager else "팀원 평가")
        ),
        "login_id": login_id,
        "display_name": (getattr(user, "name", None) or "").strip() or login_id,
        "site_code": site_code,
        "site_alias": site_alias,
        "manager_name": manager_name,
        "manager_login_id": manager_login_id,
        "assigned_worker_count": len(workers),
        "site_worker_count": site_worker_count,
        "team_split_active": site_worker_count > TEAM_LEADER_SPLIT_THRESHOLD,
        "split_threshold": TEAM_LEADER_SPLIT_THRESHOLD,
        "approval": approval,
    }


def list_hq_evaluator_accounts(db: Session, period: FunctionalEvalPeriod) -> dict[str, Any]:
    work_date = get_latest_attendance_date(db, period.id)
    regs = {r.site_code: r for r in db.query(FunctionalEvalSiteRegistry).all()}

    assigned_workers_by_login: dict[str, list[FunctionalEvalWorker]] = defaultdict(list)
    if work_date:
        for site_code in regs:
            rrn_hashes = _attendance_rrn_hashes_for_date(db, period.id, work_date, site_code=site_code)
            if not rrn_hashes:
                continue
            workers = (
                db.query(FunctionalEvalWorker)
                .filter(
                    FunctionalEvalWorker.period_id == period.id,
                    FunctionalEvalWorker.site_code == site_code,
                    FunctionalEvalWorker.is_site_manager.is_(False),
                    FunctionalEvalWorker.rrn_hash.in_(rrn_hashes),
                )
                .all()
            )
            for worker in workers:
                assigned = (worker.assigned_evaluator_login_id or "").strip()
                if assigned:
                    assigned_workers_by_login[assigned].append(worker)
    assess_map = _assessments_map(
        db, [w.id for workers in assigned_workers_by_login.values() for w in workers]
    )
    completed_counts: Counter[str] = Counter()
    incomplete_counts: Counter[str] = Counter()
    for login_id, workers in assigned_workers_by_login.items():
        for worker in workers:
            if _is_fully_evaluated(_worker_assess_payload(assess_map, worker.id)):
                completed_counts[login_id] += 1
            else:
                incomplete_counts[login_id] += 1

    site_names: dict[str, str] = {}
    for site in db.query(Site).all():
        if site.site_code:
            site_names[site.site_code] = site.site_name or site.site_code

    items: list[dict[str, Any]] = []
    users = (
        db.query(User)
        .filter(User.role == Role.SITE_FUNCTIONAL_EVAL, User.is_active.is_(True))
        .order_by(User.login_id.asc())
        .all()
    )
    for user in users:
        site_code = _site_code_for_user(user, db)
        if not site_code:
            continue
        reg = regs.get(site_code)
        login_id = (user.login_id or "").strip()
        is_manager = _is_manager_user_for_site(db, user, site_code)
        items.append(
            {
                "site_code": site_code,
                "site_alias": (reg.site_alias or "").strip() if reg else "",
                "site_name": site_names.get(site_code) or (reg.erp_site_label if reg else site_code),
                "name": (user.name or "").strip(),
                "login_id": login_id,
                "role": "소장" if is_manager else "팀장",
                "assigned_worker_count": len(assigned_workers_by_login.get(login_id, [])),
                "completed_worker_count": completed_counts[login_id],
                "incomplete_worker_count": incomplete_counts[login_id],
                "team_split_active": _attendance_worker_count_for_site(db, period.id, site_code, work_date=work_date)
                > TEAM_LEADER_SPLIT_THRESHOLD,
            }
        )

    items.sort(key=lambda x: (x["site_code"], 0 if x["role"] == "소장" else 1, x["login_id"]))
    team_leader_count = sum(1 for x in items if x["role"] == "팀장")
    split_sites = sorted(
        {
            x["site_code"]
            for x in items
            if x["team_split_active"] and x["role"] == "팀장"
        }
    )
    return {
        "split_threshold": TEAM_LEADER_SPLIT_THRESHOLD,
        "last_attendance_date": work_date.isoformat() if work_date else None,
        "manager_count": sum(1 for x in items if x["role"] == "소장"),
        "team_leader_count": team_leader_count,
        "split_site_count": len(split_sites),
        "items": items,
    }


def _worker_assignment_for_site(
    db: Session,
    worker: FunctionalEvalWorker,
    *,
    period: FunctionalEvalPeriod | None = None,
) -> str:
    period_row = period or db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == worker.period_id).first()
    if period_row is None:
        return EVAL_ASSIGNMENT_DIRECT
    rows = _site_attendance_workers(db, period_row, worker.site_code)
    manager_login = _manager_login_for_site(db, worker.site_code)
    team_leader_logins = _collect_team_leader_evaluator_logins(
        rows, manager_login, db=db, site_code=worker.site_code, period_id=period_row.id
    )


def _assert_worker_access(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    if user.role != Role.SITE_FUNCTIONAL_EVAL:
        return
    login_id = (user.login_id or "").strip()
    site_code = _site_code_for_user(user, db)
    if site_code != worker.site_code:
        raise ValueError("SITE_MISMATCH")
    if _is_primary_site_evaluator(db, user, site_code):
        return
    if _is_team_leader_self_target(db, user, worker):
        raise ValueError("CANNOT_EVALUATE_SELF")
    assigned = (worker.assigned_evaluator_login_id or "").strip()
    if assigned and assigned != login_id:
        raise ValueError("SITE_MISMATCH")
    if not assigned:
        raise ValueError("SITE_MISMATCH")


def _assert_worker_score_save_access(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    """기능·안전 점수 저장 — 소장은 팀원(팀장 담당) 점수 수정 불가."""
    if user.role != Role.SITE_FUNCTIONAL_EVAL:
        return
    site_code = _site_code_for_user(user, db)
    if site_code != worker.site_code:
        raise ValueError("SITE_MISMATCH")
    if _is_primary_site_evaluator(db, user, site_code):
        if _worker_assignment_for_site(db, worker) == EVAL_ASSIGNMENT_TEAM:
            raise ValueError("MANAGER_CANNOT_EDIT_TEAM_SCORES")
        return
    _assert_worker_access(db, user, worker)


def _assert_worker_evidence_access(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    """포상·제재 등록 — 소장은 현장 전체, 팀장은 담당 팀원만."""
    if _is_hq_safety_user(user):
        return
    if user.role != Role.SITE_FUNCTIONAL_EVAL:
        raise ValueError("SITE_MISMATCH")
    site_code = _site_code_for_user(user, db)
    if site_code != worker.site_code:
        raise ValueError("SITE_MISMATCH")
    if _is_primary_site_evaluator(db, user, site_code):
        if _is_team_leader_self_target(db, user, worker):
            raise ValueError("CANNOT_EVALUATE_SELF")
        return
    if _is_team_leader_self_target(db, user, worker):
        raise ValueError("CANNOT_EVALUATE_SELF")
    login_id = (user.login_id or "").strip()
    assigned = (worker.assigned_evaluator_login_id or "").strip()
    if assigned and assigned != login_id:
        raise ValueError("SITE_MISMATCH")
    if not assigned:
        raise ValueError("SITE_MISMATCH")


def _assert_worker_view_access(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    """이력·조회 — 소장은 현장 전체, 팀장은 담당만, 본사는 전체."""
    if _is_hq_safety_user(user):
        return
    if user.role != Role.SITE_FUNCTIONAL_EVAL:
        raise ValueError("SITE_MISMATCH")
    site_code = _site_code_for_user(user, db)
    if site_code != worker.site_code:
        raise ValueError("SITE_MISMATCH")
    if _is_primary_site_evaluator(db, user, site_code):
        return
    _assert_worker_access(db, user, worker)


def _worker_has_safety_bottom(db: Session, worker_id: int) -> bool:
    row = (
        db.query(FunctionalEvalAssessment)
        .filter(
            FunctionalEvalAssessment.worker_id == worker_id,
            FunctionalEvalAssessment.eval_type == "SAFETY",
        )
        .first()
    )
    if row is None:
        return False
    required = len(get_criteria("SAFETY"))
    scores = dict(row.scores_json or {})
    if len(scores) < required or required <= 0:
        return False
    return assessment_has_bottom("SAFETY", scores)


def _worker_sanction_count(db: Session, worker_id: int) -> int:
    return (
        db.query(FunctionalEvalSanction)
        .filter(FunctionalEvalSanction.worker_id == worker_id)
        .count()
    )


def _assert_sanction_access(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    """제재 등록 — 소장은 현장 전체, 팀장은 담당 팀원만."""
    if _is_hq_safety_user(user):
        return
    _assert_worker_evidence_access(db, user, worker)


def _assert_sanction_register(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    _assert_sanction_access(db, user, worker)


def list_workers_for_user(db: Session, user: User, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    site_code = _site_code_for_user(user, db)
    login_id = (user.login_id or "").strip()
    rows = _site_attendance_workers(db, period, site_code)
    if not rows:
        return []
    is_manager = _is_primary_site_evaluator(db, user, site_code)
    manager_login = _manager_login_for_site(db, site_code)
    team_leader_logins = _collect_team_leader_evaluator_logins(
        rows, manager_login, db=db, site_code=site_code, period_id=period.id
    )
    site_alias = ""
    if not is_manager:
        reg = (
            db.query(FunctionalEvalSiteRegistry)
            .filter(FunctionalEvalSiteRegistry.site_code == site_code)
            .first()
        )
        site_alias = (reg.site_alias or "").strip() if reg else ""
    if is_manager and len(rows) > TEAM_LEADER_SPLIT_THRESHOLD:
        rows = [r for r in rows if (r.assigned_evaluator_login_id or "").strip() == manager_login]
    elif not is_manager:
        rows = [
            r
            for r in rows
            if (r.assigned_evaluator_login_id or "").strip() == login_id
            and not _is_team_leader_self_target(db, user, r, site_alias=site_alias)
        ]
    assess_map = _assessments_map(db, [r.id for r in rows])
    return [
        serialize_worker(db, row, assessments=assess_map.get(row.id, {}), team_leader_logins=team_leader_logins)
        for row in rows
    ]


def list_site_overview_for_manager(db: Session, user: User, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    site_code = _site_code_for_user(user, db)
    if not _is_primary_site_evaluator(db, user, site_code):
        return []
    rows = _site_attendance_workers(db, period, site_code)
    manager_login = _manager_login_for_site(db, site_code)
    team_leader_logins = _collect_team_leader_evaluator_logins(
        rows, manager_login, db=db, site_code=site_code, period_id=period.id
    )
    assess_map = _assessments_map(db, [r.id for r in rows])
    return [
        serialize_worker(db, row, assessments=assess_map.get(row.id, {}), team_leader_logins=team_leader_logins)
        for row in rows
    ]


def get_worker_history(db: Session, user: User, worker_id: int) -> dict[str, Any]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    _assert_worker_view_access(db, user, worker)

    permanent = _worker_is_permanently_expelled(db, worker.id)
    worker_payload = serialize_worker(db, worker)
    revisions = (
        db.query(FunctionalEvalAssessmentRevision)
        .filter(FunctionalEvalAssessmentRevision.worker_id == worker.id)
        .order_by(FunctionalEvalAssessmentRevision.created_at.desc(), FunctionalEvalAssessmentRevision.id.desc())
        .all()
    )
    revision_payload = [_serialize_assessment_revision(r, db) for r in revisions]

    strike_sequence = _strike_sequence_for_person(db, worker.rrn_hash)

    if permanent:
        latest = _worker_sanction_rows(db, worker.id)
        summary = (
            _serialize_sanction(latest[0], worker.name, db, strike_sequence=strike_sequence) if latest else None
        )
        return {
            "worker": worker_payload,
            "history_visible": False,
            "sanctions": [],
            "assessment_revisions": revision_payload,
            "summary": summary,
            "message": "영구 퇴출 대상은 상세 이력을 표시하지 않습니다.",
        }

    current = (
        db.query(FunctionalEvalSanction)
        .filter(FunctionalEvalSanction.worker_id == worker.id)
        .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
        .all()
    )
    prior_workers = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.rrn_hash == worker.rrn_hash,
            FunctionalEvalWorker.id != worker.id,
        )
        .order_by(FunctionalEvalWorker.period_id.desc())
        .all()
    )
    prior_sanctions: list[dict[str, Any]] = []
    prior_assessments: list[dict[str, Any]] = []
    for pw in prior_workers:
        pw_assess = _assessments_map(db, [pw.id]).get(pw.id, {})
        functional = _serialize_assessment(pw_assess.get("FUNCTIONAL"), "FUNCTIONAL")
        safety = _serialize_assessment(pw_assess.get("SAFETY"), "SAFETY")
        if (functional and functional.get("is_complete")) or (safety and safety.get("is_complete")):
            period_row = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == pw.period_id).first()
            prior_assessments.append(
                {
                    "period_id": pw.period_id,
                    "period_title": period_row.title if period_row else f"기간 {pw.period_id}",
                    "site_code": pw.site_code,
                    "functional_assessment": functional,
                    "safety_assessment": safety,
                    "from_prior_period": True,
                }
            )
        rows = (
            db.query(FunctionalEvalSanction)
            .filter(FunctionalEvalSanction.worker_id == pw.id)
            .order_by(FunctionalEvalSanction.created_at.asc())
            .all()
        )
        for row in rows:
            item = _serialize_sanction(row, pw.name, db, strike_sequence=strike_sequence)
            item["period_id"] = pw.period_id
            item["from_prior_period"] = True
            prior_sanctions.append(item)

    return {
        "worker": worker_payload,
        "history_visible": True,
        "sanctions": [_serialize_sanction(s, worker.name, db, strike_sequence=strike_sequence) for s in current],
        "prior_sanctions": prior_sanctions,
        "prior_assessments": prior_assessments,
        "assessment_revisions": revision_payload,
        "mileage": serialize_worker_adjustments(db, worker),
        "adjustments": serialize_worker_adjustments(db, worker),
    }


def _upsert_assessment_with_revision(
    db: Session,
    *,
    worker: FunctionalEvalWorker,
    eval_type: EvalType,
    scores: dict[str, str],
    user: User,
    reason: str,
    source: str,
    sanction_id: int | None = None,
) -> dict[str, Any]:
    computed = compute_assessment(eval_type, scores)
    existing = (
        db.query(FunctionalEvalAssessment)
        .filter(
            FunctionalEvalAssessment.worker_id == worker.id,
            FunctionalEvalAssessment.eval_type == eval_type,
        )
        .first()
    )
    before_scores = dict(existing.scores_json) if existing else None
    before_grade = normalize_grade_code(existing.grade_code) if existing else None

    if existing is None:
        existing = FunctionalEvalAssessment(
            worker_id=worker.id,
            eval_type=eval_type,
            scores_json=computed["scores"],
            total_score=computed["total_score"],
            max_score=computed["max_score"],
            grade_code=computed["grade_code"],
            grade_label=computed["grade_label"],
            updated_by_user_id=user.id,
        )
        db.add(existing)
    else:
        existing.scores_json = computed["scores"]
        existing.total_score = computed["total_score"]
        existing.max_score = computed["max_score"]
        existing.grade_code = computed["grade_code"]
        existing.grade_label = computed["grade_label"]
        existing.updated_by_user_id = user.id
        db.add(existing)

    revision = FunctionalEvalAssessmentRevision(
        worker_id=worker.id,
        eval_type=eval_type,
        before_scores_json=before_scores,
        after_scores_json=computed["scores"],
        before_grade_code=before_grade,
        after_grade_code=computed["grade_code"],
        reason=reason.strip(),
        source=source,
        sanction_id=sanction_id,
        edited_by_user_id=user.id,
    )
    db.add(revision)
    db.flush()
    return _serialize_assessment(existing, eval_type)


def _apply_safety_bottom_from_violation(
    db: Session,
    *,
    worker: FunctionalEvalWorker,
    user: User,
    sanction_row: FunctionalEvalSanction,
    violation_code: str,
    violation_label: str,
    note: str,
) -> None:
    """추가 제재 — 해당 위반에 대응하는 안전(2-2) 항목만 「문제」로 자동 반영."""
    existing = (
        db.query(FunctionalEvalAssessment)
        .filter(
            FunctionalEvalAssessment.worker_id == worker.id,
            FunctionalEvalAssessment.eval_type == "SAFETY",
        )
        .first()
    )
    before = dict(existing.scores_json) if existing and existing.scores_json else None
    if violation_safety_targets_already_bottom(violation_code, before):
        return
    scores = build_safety_scores_with_bottom_for_violation(violation_code, before)
    criterion_ids = violation_safety_criterion_ids(violation_code)
    if not criterion_ids:
        return
    titles = []
    for crit in get_criteria("SAFETY"):
        if str(crit["id"]) in criterion_ids:
            titles.append(str(crit.get("title") or crit["id"]))
    target_label = ", ".join(titles) if titles else violation_label
    reason = (
        f"제재 등록 — {violation_label} · {target_label} 「문제」 자동 반영"
        f" ({note.strip()})"
    )
    _upsert_assessment_with_revision(
        db,
        worker=worker,
        eval_type="SAFETY",
        scores=scores,
        user=user,
        reason=reason,
        source="SANCTION_AUTO",
        sanction_id=sanction_row.id,
    )


def record_sanction(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    user: User,
    worker_id: int,
    violation_code: str,
    evidence_type: str,
    note: str | None,
    evidence_photo_path: str | None = None,
    evidence_photo_original_filename: str | None = None,
    signature_data: str,
    penalty_points: int = DEFAULT_SANCTION_PENALTY_POINTS,
) -> dict[str, Any]:
    from app.modules.functional_eval.signature_service import validate_signature_data

    period_closed = period_is_closed(period)
    if not period_closed:
        assert_period_editable(period)
    elif _is_hq_safety_user(user):
        pass
    elif user.role != Role.SITE_FUNCTIONAL_EVAL:
        raise ValueError("SITE_MISMATCH")

    if violation_code not in VIOLATION_BY_CODE:
        raise ValueError("UNKNOWN_VIOLATION")

    ev_type = (evidence_type or "").strip().upper()
    if ev_type not in {EVIDENCE_COMMENT, EVIDENCE_PHOTO}:
        raise ValueError("INVALID_EVIDENCE_TYPE")

    note_text = (note or "").strip()
    if ev_type == EVIDENCE_COMMENT and not note_text:
        raise ValueError("SANCTION_EVIDENCE_COMMENT_REQUIRED")
    if ev_type == EVIDENCE_PHOTO and not evidence_photo_path:
        raise ValueError("SANCTION_EVIDENCE_PHOTO_REQUIRED")

    try:
        _, sig_raw = validate_signature_data(signature_data)
    except ValueError as exc:
        raise ValueError("SANCTION_SIGNATURE_REQUIRED") from exc
    signature_hash = hashlib.sha256(sig_raw).hexdigest()

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None or worker.period_id != period.id:
        raise ValueError("WORKER_NOT_FOUND")
    if worker.is_site_manager:
        raise ValueError("CANNOT_SANCTION_SITE_MANAGER")
    _assert_sanction_register(db, user, worker)
    if not _is_hq_safety_user(user) and not period_closed:
        _assert_worker_attendance_eligible(db, period, worker)

    site_pending = period_closed and not _is_hq_safety_user(user)

    prior_count = _count_approved_sanctions_for_violation(db, worker, violation_code)
    sanction_result, strike = resolve_sanction(violation_code, prior_count)
    item = VIOLATION_BY_CODE[violation_code]
    if prior_count > 0:
        points = max(1, min(int(penalty_points or DEFAULT_SANCTION_PENALTY_POINTS), 100))
    else:
        points = 0

    row = FunctionalEvalSanction(
        period_id=period.id,
        worker_id=worker.id,
        site_code=worker.site_code,
        violation_code=violation_code,
        violation_category=item.category,
        strike_number=strike,
        sanction_result=sanction_result,
        note=note_text or None,
        evidence_type=ev_type,
        evidence_photo_path=evidence_photo_path,
        evidence_photo_original_filename=evidence_photo_original_filename,
        signature_data=signature_data.strip(),
        signature_hash=signature_hash,
        penalty_points=points,
        status=SANCTION_STATUS_PENDING if site_pending else SANCTION_STATUS_APPROVED,
        reported_by_user_id=user.id,
    )
    db.add(row)
    db.flush()

    if not site_pending:
        display_note = note_text or ("사진 근거" if ev_type == EVIDENCE_PHOTO else "")
        _apply_safety_bottom_from_violation(
            db,
            worker=worker,
            user=user,
            sanction_row=row,
            violation_code=violation_code,
            violation_label=item.label,
            note=display_note,
        )
    db.commit()
    db.refresh(row)
    strike_sequence = _strike_sequence_for_person(db, worker.rrn_hash)
    return _serialize_sanction(row, worker.name, db, strike_sequence=strike_sequence)


def list_hq_summary(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
    sanction_status: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    workers = _attendance_target_workers(db, period, site_code=site_code)
    assessed_workers: list[FunctionalEvalWorker] = []
    if include_inactive:
        assessed_workers = _workers_with_any_assessment(db, period, site_code=site_code)

    all_worker_ids = [w.id for w in workers]
    seen_worker_ids = {w.id for w in workers}
    if include_inactive:
        for assessed_worker in assessed_workers:
            if assessed_worker.id not in seen_worker_ids:
                workers.append(assessed_worker)
                seen_worker_ids.add(assessed_worker.id)
                all_worker_ids.append(assessed_worker.id)

    site_codes = {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, site_codes)
    assess_map = _assessments_map(db, all_worker_ids)

    items: list[dict[str, Any]] = []
    for worker in workers:
        worker_payload = serialize_worker(db, worker, assessments=assess_map.get(worker.id, {}))
        if not worker_payload.get("site_name"):
            worker_payload["site_name"] = site_names.get(worker.site_code) or f"현장 {worker.site_code}"
        if sanction_status and worker_payload["sanction_status"] != sanction_status:
            continue
        sanctions = (
            db.query(FunctionalEvalSanction)
            .filter(FunctionalEvalSanction.worker_id == worker.id)
            .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
            .all()
        )
        visible_sanctions = sanctions
        if worker_payload["is_permanently_expelled"]:
            visible_sanctions = sanctions[-1:] if sanctions else []
        strike_sequence = _strike_sequence_for_person(db, worker.rrn_hash)
        items.append(
            {
                "worker": worker_payload,
                "sanctions": [
                    _serialize_sanction(s, worker.name, db, strike_sequence=strike_sequence) for s in visible_sanctions
                ],
                "sanction_count_total": len(sanctions),
            }
        )

    reverse = sort_dir.lower() == "desc"

    def _key(item: dict[str, Any]) -> Any:
        w = item["worker"]
        if sort_by == "sanction_status":
            return w.get("sanction_status") or ""
        if sort_by == "name":
            return w.get("name") or ""
        if sort_by == "sanction_count":
            return w.get("sanction_count") or 0
        if sort_by == "site_name":
            return (w.get("site_name") or "", w.get("site_code") or "")
        if sort_by == "functional_grade":
            return _grade_sort_key(w.get("functional_assessment"))
        if sort_by == "safety_grade":
            return _grade_sort_key(w.get("safety_assessment"))
        return w.get("site_code") or ""

    items.sort(key=_key, reverse=reverse)
    return items


GRADE_STAT_CODES: tuple[str, ...] = ("S", "A", "B", "C")


def _grade_distribution(workers: list[dict[str, Any]], *, assessment_field: str) -> dict[str, Any]:
    counts = {code: 0 for code in GRADE_STAT_CODES}
    ungraded = 0
    for worker in workers:
        assessment = worker.get(assessment_field)
        if not assessment or not assessment.get("is_complete"):
            ungraded += 1
            continue
        code = normalize_grade_code(str(assessment.get("grade_code") or "")) or ""
        if code in counts:
            counts[code] += 1
        else:
            ungraded += 1
    graded_total = sum(counts.values())
    grades: dict[str, dict[str, float | int]] = {}
    for code in GRADE_STAT_CODES:
        count = counts[code]
        grades[code] = {
            "count": count,
            "pct": round(100.0 * count / graded_total, 1) if graded_total else 0.0,
        }
    return {
        "workers_total": len(workers),
        "graded_total": graded_total,
        "ungraded_count": ungraded,
        "grades": grades,
    }


def _grade_stats_block(workers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "functional": _grade_distribution(workers, assessment_field="functional_assessment"),
        "safety": _grade_distribution(workers, assessment_field="safety_assessment"),
    }


def _attendance_worker_payloads(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    site_code: str | None = None,
) -> list[dict[str, Any]]:
    workers = _attendance_target_workers(db, period, site_code=site_code)
    site_codes = {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, site_codes)
    _, attendance_labels, _ = _attendance_site_meta(db, period.id)
    registry_labels = _registry_erp_label_map(db, site_codes)
    erp_labels = {**registry_labels, **attendance_labels}
    assess_map = _assessments_map(db, [w.id for w in workers])
    payloads: list[dict[str, Any]] = []
    for worker in workers:
        payload = serialize_worker(db, worker, assessments=assess_map.get(worker.id, {}))
        code = str(worker.site_code or "")
        payload["site_name"] = _resolve_worker_site_display_name(
            code,
            worker_site_name=payload.get("site_name"),
            site_names=site_names,
            erp_labels=erp_labels,
        )
        payloads.append(payload)
    return payloads


def build_hq_grade_stats(db: Session, period: FunctionalEvalPeriod) -> dict[str, Any]:
    from app.modules.functional_eval import grade_stats_cache

    return grade_stats_cache.get_hq_grade_stats(db, period)


def build_site_grade_stats(db: Session, period: FunctionalEvalPeriod, site_code: str) -> dict[str, Any]:
    from app.modules.functional_eval import grade_stats_cache

    return grade_stats_cache.get_site_grade_stats(db, period, site_code)


def build_hq_summary_response(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
    include_inactive: bool = False,
) -> dict[str, Any]:
    """본사 평가 현황 — 현장 목록·진행률만 반환 (근로자 상세는 현장별 API)."""
    return build_hq_sites_overview(
        db,
        period,
        sort_by=sort_by,
        sort_dir=sort_dir,
        site_code=site_code,
        include_inactive=include_inactive,
    )


def build_hq_monitoring_summary(db: Session, period: FunctionalEvalPeriod) -> dict[str, Any]:
    summary = build_hq_sites_overview(
        db,
        period,
        sort_by="progress",
        sort_dir="desc",
        include_inactive=True,
    )
    return {
        "period": summary["period"],
        "attendance_message": summary.get("attendance_message"),
        "totals": summary["totals"],
        "worker_status_counts": summary["worker_status_counts"],
        "site_buckets": summary["site_buckets"],
    }


def _diff_row(existing: FunctionalEvalWorker | None, row: ParsedRosterRow) -> RosterDiffItem:
    if existing is None:
        return RosterDiffItem(
            type="NEW",
            rrn_hash=row.rrn_hash,
            name=row.name,
            site_code=row.site_code,
        )
    changes: dict[str, tuple[Any, Any]] = {}
    if existing.name != row.name:
        changes["name"] = (existing.name, row.name)
    if existing.site_code != row.site_code:
        changes["site_code"] = (existing.site_code, row.site_code)
    if existing.job_code != row.job_code:
        changes["job_code"] = (existing.job_code, row.job_code)
    if not existing.is_active:
        changes["is_active"] = (False, True)
    diff_type = "UPDATED" if changes else "UNCHANGED"
    return RosterDiffItem(
        type=diff_type,
        rrn_hash=row.rrn_hash,
        name=row.name,
        site_code=row.site_code,
        worker_id=existing.id,
        changes=changes or None,
    )


def diff_daily_roster(
    db: Session,
    period: FunctionalEvalPeriod,
    parsed_rows: list[ParsedRosterRow],
) -> RosterDiffResult:
    existing_all = (
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all()
    )
    by_hash = {w.rrn_hash: w for w in existing_all if w.rrn_hash}
    incoming_hashes = {r.rrn_hash for r in parsed_rows}

    items: list[RosterDiffItem] = []
    for row in parsed_rows:
        items.append(_diff_row(by_hash.get(row.rrn_hash), row))

    for rrn_hash, worker in by_hash.items():
        if rrn_hash in incoming_hashes:
            continue
        if not worker.is_active:
            continue
        items.append(
            RosterDiffItem(
                type="REMOVED",
                rrn_hash=rrn_hash,
                name=worker.name,
                site_code=worker.site_code,
                worker_id=worker.id,
            )
        )
    return RosterDiffResult(items=items)


def _next_row_no(db: Session, period_id: int, site_code: str) -> int:
    last = (
        db.query(FunctionalEvalWorker)
        .filter(FunctionalEvalWorker.period_id == period_id, FunctionalEvalWorker.site_code == site_code)
        .order_by(FunctionalEvalWorker.row_no.desc())
        .first()
    )
    return (last.row_no + 1) if last else 1


def _provision_site_managers(db: Session, parsed_rows: list[ParsedRosterRow]) -> dict[str, int]:
    # (birth sort key, manager name, rrn raw) — 직종 1이 여러 명이면 연장자 1명
    managers_by_site: dict[str, list[tuple[tuple[int, int, int], str, str]]] = {}
    for row in parsed_rows:
        if row.is_site_manager:
            managers_by_site.setdefault(row.site_code, []).append(
                (_birth_sort_key(row.rrn_raw), row.name, row.rrn_raw)
            )

    sites_created = 0
    managers_created = 0
    for site_code, managers in managers_by_site.items():
        if not managers:
            continue
        managers.sort(key=lambda x: x[0])
        manager_name = managers[0][1]
        rrn_raw = managers[0][2]
        pw = _rrn_front_password(rrn_raw)
        if not pw:
            continue

        site = db.query(Site).filter(Site.site_code == site_code).first()
        if site is None:
            site = Site(site_code=site_code, site_name=f"현장 {site_code}")
            db.add(site)
            db.flush()
            sites_created += 1

        user = db.query(User).filter(User.login_id == site_code).first()
        if user is None:
            user = User(
                name=manager_name,
                login_id=site_code,
                password_hash=get_password_hash(pw),
                role=Role.SITE_FUNCTIONAL_EVAL,
                ui_type=UIType.SITE,
                site_id=site.id,
                must_change_password=False,
            )
            db.add(user)
            managers_created += 1
        else:
            user.name = manager_name
            user.role = Role.SITE_FUNCTIONAL_EVAL
            user.ui_type = UIType.SITE
            user.site_id = site.id
            user.password_hash = get_password_hash(pw)
            user.must_change_password = False
            db.add(user)

    db.commit()
    return {"sites_created": sites_created, "managers_created": managers_created}


def apply_daily_roster_diff(
    db: Session,
    period: FunctionalEvalPeriod,
    parsed_rows: list[ParsedRosterRow],
    *,
    original_filename: str,
    stored_path: str,
) -> dict[str, Any]:
    diff = diff_daily_roster(db, period, parsed_rows)
    existing_all = (
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all()
    )
    by_hash = {w.rrn_hash: w for w in existing_all}
    incoming_hashes = {r.rrn_hash for r in parsed_rows}
    now = utc_now()
    row_counters: dict[str, int] = {}

    def _alloc_row_no(site_code: str) -> int:
        if site_code not in row_counters:
            row_counters[site_code] = _next_row_no(db, period.id, site_code) - 1
        row_counters[site_code] += 1
        return row_counters[site_code]

    for row in parsed_rows:
        worker = by_hash.get(row.rrn_hash)
        if worker is None:
            worker = FunctionalEvalWorker(
                period_id=period.id,
                site_code=row.site_code,
                row_no=_alloc_row_no(row.site_code),
                name=row.name,
                rrn_hash=row.rrn_hash,
                rrn_masked=row.rrn_masked,
                job_code=row.job_code,
                phone_mobile=row.phone,
                assigned_evaluator_login_id=row.site_code,
                is_site_manager=row.is_site_manager,
                is_active=True,
                is_on_reference_roster=True,
            )
            db.add(worker)
        else:
            if worker.site_code != row.site_code:
                worker.row_no = _alloc_row_no(row.site_code)
            worker.site_code = row.site_code
            worker.name = row.name
            worker.job_code = row.job_code
            worker.phone_mobile = row.phone
            worker.rrn_masked = row.rrn_masked
            worker.assigned_evaluator_login_id = worker.assigned_evaluator_login_id or row.site_code
            worker.is_site_manager = row.is_site_manager
            worker.is_active = True
            worker.is_on_reference_roster = True
            worker.removed_at = None
            worker.updated_at = now
            db.add(worker)

    for rrn_hash, worker in by_hash.items():
        if rrn_hash in incoming_hashes:
            continue
        if not worker.is_on_reference_roster:
            continue
        worker.is_on_reference_roster = False
        worker.is_active = False
        worker.removed_at = now
        db.add(worker)

    db.flush()
    for site_code in {r.site_code for r in parsed_rows}:
        resequence_site_row_numbers(db, period.id, site_code)
    manager_stats = _provision_site_managers(db, parsed_rows)

    batch = FunctionalEvalRosterImportBatch(
        period_id=period.id,
        original_filename=original_filename,
        stored_path=stored_path,
        total_rows=len(parsed_rows),
        new_count=diff.new_count,
        updated_count=diff.updated_count,
        unchanged_count=diff.unchanged_count,
        removed_count=diff.removed_count,
    )
    db.add(batch)
    db.commit()

    from app.modules.functional_eval import grade_stats_cache

    grade_stats_cache.mark_dirty(db, period)

    return {
        "batch_id": batch.id,
        "total_rows": len(parsed_rows),
        "new_count": diff.new_count,
        "updated_count": diff.updated_count,
        "unchanged_count": diff.unchanged_count,
        "removed_count": diff.removed_count,
        "site_count": len({r.site_code for r in parsed_rows}),
        **manager_stats,
    }


def serialize_roster_diff(diff: RosterDiffResult) -> dict[str, Any]:
    return {
        "total": len(diff.items),
        "new_count": diff.new_count,
        "updated_count": diff.updated_count,
        "unchanged_count": diff.unchanged_count,
        "removed_count": diff.removed_count,
        "items": [
            {
                "type": item.type,
                "rrn_hash": item.rrn_hash,
                "name": item.name,
                "site_code": item.site_code,
                "worker_id": item.worker_id,
                "changes": item.changes,
            }
            for item in diff.items
        ],
    }


def diff_daily_roster_file(db: Session, period: FunctionalEvalPeriod, file_path: Path) -> dict[str, Any]:
    parsed = parse_daily_roster_xlsx(file_path)
    diff = diff_daily_roster(db, period, parsed)
    return {**serialize_roster_diff(diff), "parsed_rows": len(parsed)}


def resequence_site_row_numbers(db: Session, period_id: int, site_code: str) -> None:
    workers = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.period_id == period_id,
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.is_active.is_(True),
        )
        .order_by(FunctionalEvalWorker.name.asc(), FunctionalEvalWorker.id.asc())
        .all()
    )
    for idx, worker in enumerate(workers, start=1):
        worker.row_no = idx
        db.add(worker)
    db.flush()


def eval_catalog_public() -> dict[str, Any]:
    return catalog_for_api()


def get_worker_assessment(db: Session, user: User, worker_id: int, eval_type: EvalType) -> dict[str, Any]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    if _is_hq_safety_user(user):
        _assert_worker_view_access(db, user, worker)
    else:
        _assert_worker_access(db, user, worker)
    if worker.is_site_manager:
        raise ValueError("CANNOT_EVALUATE_SITE_MANAGER")
    row = (
        db.query(FunctionalEvalAssessment)
        .filter(
            FunctionalEvalAssessment.worker_id == worker_id,
            FunctionalEvalAssessment.eval_type == eval_type,
        )
        .first()
    )
    bonus = _worker_bonus_points_total(db, worker_id) if eval_type == "SAFETY" else 0
    penalty = _worker_penalty_points_total(db, worker_id) if eval_type == "SAFETY" else 0
    return {
        "worker_id": worker_id,
        "eval_type": eval_type,
        "catalog": catalog_for_api()[eval_type],
        "assessment": _serialize_assessment(
            row,
            eval_type,
            bonus_points=bonus,
            penalty_points=penalty,
        ),
    }


def save_worker_assessment(
    db: Session,
    user: User,
    worker_id: int,
    eval_type: EvalType,
    scores: dict[str, str],
) -> dict[str, Any]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    _assert_worker_score_save_access(db, user, worker)
    if worker.is_site_manager:
        raise ValueError("CANNOT_EVALUATE_SITE_MANAGER")
    period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == worker.period_id).first()
    if period is None:
        raise ValueError("WORKER_NOT_FOUND")
    if period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")
    approval_workflow.assert_site_editable(db, period.id, worker.site_code)
    from app.modules.functional_eval import signature_ops

    signature_ops.assert_worker_not_signature_locked(db, user, worker)
    _assert_worker_attendance_eligible(db, period, worker)

    computed = compute_assessment(eval_type, scores)
    row = (
        db.query(FunctionalEvalAssessment)
        .filter(
            FunctionalEvalAssessment.worker_id == worker_id,
            FunctionalEvalAssessment.eval_type == eval_type,
        )
        .first()
    )
    if row is None:
        row = FunctionalEvalAssessment(
            worker_id=worker_id,
            eval_type=eval_type,
            scores_json=computed["scores"],
            total_score=computed["total_score"],
            max_score=computed["max_score"],
            grade_code=computed["grade_code"],
            grade_label=computed["grade_label"],
            updated_by_user_id=user.id,
        )
        db.add(row)
    else:
        row.scores_json = computed["scores"]
        row.total_score = computed["total_score"]
        row.max_score = computed["max_score"]
        row.grade_code = computed["grade_code"]
        row.grade_label = computed["grade_label"]
        row.updated_by_user_id = user.id
        db.add(row)
    db.commit()
    db.refresh(row)
    from app.modules.functional_eval import grade_stats_cache

    grade_stats_cache.mark_dirty(db, period)
    bonus = _worker_bonus_points_total(db, worker_id) if eval_type == "SAFETY" else 0
    penalty = _worker_penalty_points_total(db, worker_id) if eval_type == "SAFETY" else 0
    return _serialize_assessment(row, eval_type, bonus_points=bonus, penalty_points=penalty)


def save_hq_assessment_override(
    db: Session,
    user: User,
    worker_id: int,
    eval_type: EvalType,
    scores: dict[str, str],
    reason: str,
) -> dict[str, Any]:
    if not _is_hq_safety_user(user):
        raise ValueError("HQ_ONLY")
    reason_text = (reason or "").strip()
    if not reason_text:
        raise ValueError("REVISION_REASON_REQUIRED")

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    if worker.is_site_manager:
        raise ValueError("CANNOT_EVALUATE_SITE_MANAGER")
    period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == worker.period_id).first()
    if period is None:
        raise ValueError("WORKER_NOT_FOUND")
    if period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")

    assessment = _upsert_assessment_with_revision(
        db,
        worker=worker,
        eval_type=eval_type,
        scores=scores,
        user=user,
        reason=reason_text,
        source="HQ_OVERRIDE",
    )
    db.commit()
    from app.modules.functional_eval import grade_stats_cache

    grade_stats_cache.mark_dirty(db, period)
    return {"assessment": assessment}


def list_worker_assessment_revisions(db: Session, user: User, worker_id: int) -> list[dict[str, Any]]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    _assert_worker_view_access(db, user, worker)
    rows = (
        db.query(FunctionalEvalAssessmentRevision)
        .filter(FunctionalEvalAssessmentRevision.worker_id == worker.id)
        .order_by(FunctionalEvalAssessmentRevision.created_at.desc(), FunctionalEvalAssessmentRevision.id.desc())
        .all()
    )
    return [_serialize_assessment_revision(r, db) for r in rows]


def apply_daily_roster_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    original_filename: str,
) -> dict[str, Any]:
    parsed = parse_daily_roster_xlsx(file_path)
    return apply_daily_roster_diff(
        db,
        period,
        parsed,
        original_filename=original_filename,
        stored_path=str(file_path),
    )


def _pick_column(headers: list[str], aliases: tuple[str, ...]) -> int | None:
    normalized = [str(h or "").strip().lower() for h in headers]
    for idx, name in enumerate(normalized):
        for alias in aliases:
            if alias in name:
                return idx
    return None


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _parse_team_assignments_xlsx(path: Path) -> list[ParsedTeamAssignmentRow]:
    parsed = parse_excel_with_fallback(path)
    headers = parsed.headers or []
    rows = parsed.rows or []
    i_site = _pick_column(headers, ("현장코드", "site_code"))
    i_leader = _pick_column(headers, ("팀장", "leader"))
    i_leader_rrn = _pick_column(headers, ("팀장주민", "팀장 주민", "leader_rrn", "leader rrn"))
    i_worker = _pick_column(headers, ("팀원", "근로자", "성명", "worker"))
    i_worker_rrn = _pick_column(headers, ("팀원주민", "팀원 주민", "worker_rrn", "worker rrn", "주민번호"))
    required = [i_site, i_leader, i_leader_rrn, i_worker]
    if any(v is None for v in required):
        raise ValueError("TEAM_ASSIGNMENT_HEADER_INVALID")
    out: list[ParsedTeamAssignmentRow] = []
    for raw in rows:
        site_code = _to_text(raw[i_site]) if i_site is not None and i_site < len(raw) else ""
        leader = _to_text(raw[i_leader]) if i_leader is not None and i_leader < len(raw) else ""
        leader_rrn = _to_text(raw[i_leader_rrn]) if i_leader_rrn is not None and i_leader_rrn < len(raw) else ""
        worker_name = _to_text(raw[i_worker]) if i_worker is not None and i_worker < len(raw) else ""
        worker_rrn = _to_text(raw[i_worker_rrn]) if i_worker_rrn is not None and i_worker_rrn < len(raw) else ""
        if not (site_code and leader and leader_rrn and worker_name):
            continue
        out.append(
            ParsedTeamAssignmentRow(
                site_code=site_code,
                team_leader_name=leader,
                team_leader_rrn_raw=leader_rrn,
                worker_name=worker_name,
                worker_rrn_raw=worker_rrn or None,
            )
        )
    return out


def _parse_team_assignments_txt(path: Path) -> list[ParsedTeamAssignmentRow]:
    raw = path.read_bytes()
    text = ""
    for enc in ("utf-8-sig", "cp949", "euc-kr", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if not text.strip():
        raise ValueError("EMPTY_FILE")
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    if not reader.fieldnames:
        reader = csv.DictReader(io.StringIO(text))
    out: list[ParsedTeamAssignmentRow] = []
    for row in reader:
        site_code = (row.get("site_code") or row.get("현장코드") or "").strip()
        leader = (row.get("team_leader_name") or row.get("팀장명") or "").strip()
        leader_rrn = (row.get("team_leader_rrn") or row.get("팀장주민번호") or "").strip()
        worker_name = (row.get("worker_name") or row.get("팀원명") or row.get("근로자명") or "").strip()
        worker_rrn = (row.get("worker_rrn") or row.get("팀원주민번호") or row.get("주민번호") or "").strip()
        if not (site_code and leader and leader_rrn and worker_name):
            continue
        out.append(
            ParsedTeamAssignmentRow(
                site_code=site_code,
                team_leader_name=leader,
                team_leader_rrn_raw=leader_rrn,
                worker_name=worker_name,
                worker_rrn_raw=worker_rrn or None,
            )
        )
    return out


def parse_team_assignment_file(file_path: Path) -> list[ParsedTeamAssignmentRow]:
    ext = file_path.suffix.lower()
    if ext in {".xlsx", ".xls"}:
        return _parse_team_assignments_xlsx(file_path)
    if ext == ".txt":
        return _parse_team_assignments_txt(file_path)
    raise ValueError("TEAM_ASSIGNMENT_UNSUPPORTED_FILE")


def apply_team_leader_assignments_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    threshold: int = TEAM_LEADER_SPLIT_THRESHOLD,
) -> dict[str, Any]:
    rows = parse_team_assignment_file(file_path)
    if not rows:
        raise ValueError("NO_TEAM_ASSIGNMENT_ROWS")

    site_worker_counts: dict[str, int] = defaultdict(int)
    for worker in db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all():
        if worker.is_site_manager:
            continue
        site_worker_counts[worker.site_code] += 1

    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (row.team_leader_name.strip(), re.sub(r"\D", "", row.team_leader_rrn_raw))
        if not key[0] or not key[1]:
            continue
        bucket = grouped[row.site_code].setdefault(
            key[0],
            {
                "rrn": key[1],
                "workers": [],
            },
        )
        bucket["workers"].append(row)

    assignment_rows: list[dict[str, Any]] = []
    created_accounts = 0
    assigned_workers = 0

    for site_code, leaders in grouped.items():
        if site_worker_counts.get(site_code, 0) <= threshold:
            continue
        site = db.query(Site).filter(Site.site_code == site_code).first()
        if site is None:
            site = Site(site_code=site_code, site_name=f"현장 {site_code}")
            db.add(site)
            db.flush()

        ordered_leaders = sorted(leaders.items(), key=lambda x: _birth_sort_key(x[1]["rrn"]))
        reg = (
            db.query(FunctionalEvalSiteRegistry)
            .filter(FunctionalEvalSiteRegistry.site_code == site_code)
            .first()
        )
        site_alias = (reg.site_alias or site_code).strip() if reg else site_code
        for leader_name, meta in ordered_leaders.items():
            login_id = build_eval_login_id(site_alias, leader_name)
            if not login_id:
                continue
            initial_pw = _rrn_front_password(meta["rrn"])
            if not initial_pw:
                continue
            user = db.query(User).filter(User.login_id == login_id).first()
            if user is None:
                user = User(
                    name=leader_name,
                    login_id=login_id,
                    password_hash=get_password_hash(initial_pw),
                    role=Role.SITE_FUNCTIONAL_EVAL,
                    ui_type=UIType.SITE,
                    site_id=site.id,
                    must_change_password=False,
                )
                db.add(user)
                created_accounts += 1
            else:
                user.name = leader_name
                user.password_hash = get_password_hash(initial_pw)
                user.role = Role.SITE_FUNCTIONAL_EVAL
                user.ui_type = UIType.SITE
                user.site_id = site.id
                user.must_change_password = False
                db.add(user)

            team_workers = meta["workers"]
            leader_name_norm = leader_name.replace(" ", "")
            names = {
                r.worker_name.strip()
                for r in team_workers
                if r.worker_name.strip() and r.worker_name.strip().replace(" ", "") != leader_name_norm
            }
            rrn_hashes: set[str] = set()
            leader_rrn_hash = hash_rrn(meta["rrn"])
            for r in team_workers:
                if r.worker_rrn_raw:
                    candidate_hash = hash_rrn(r.worker_rrn_raw)
                    if candidate_hash == leader_rrn_hash:
                        continue
                    rrn_hashes.add(candidate_hash)
            q = db.query(FunctionalEvalWorker).filter(
                FunctionalEvalWorker.period_id == period.id,
                FunctionalEvalWorker.site_code == site_code,
                FunctionalEvalWorker.is_site_manager.is_(False),
            )
            candidates = q.all()
            for worker in candidates:
                if worker.name in names or (worker.rrn_hash and worker.rrn_hash in rrn_hashes):
                    worker.assigned_evaluator_login_id = login_id
                    db.add(worker)
                    assigned_workers += 1

            assignment_rows.append(
                {
                    "site_code": site_code,
                    "team_leader_name": leader_name,
                    "login_id": login_id,
                    "initial_password": initial_pw,
                    "team_worker_count": len(team_workers),
                }
            )

    db.commit()
    assignment_rows.sort(key=lambda x: (x["site_code"], x["login_id"]))
    return {
        "threshold": threshold,
        "parsed_rows": len(rows),
        "created_accounts": created_accounts,
        "assigned_workers": assigned_workers,
        "account_rows": assignment_rows,
    }


def apply_monthly_site_aggregate_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    original_filename: str,
) -> dict[str, Any]:
    from app.modules.functional_eval import eval_provisioning

    result = eval_provisioning.apply_monthly_site_aggregate_file(
        db, period, file_path, original_filename=original_filename
    )
    db.refresh(period)
    return {**result, "period": serialize_period(period, db)}


def apply_attendance_report_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    original_filename: str,
) -> dict[str, Any]:
    from app.modules.functional_eval import eval_provisioning

    result = eval_provisioning.apply_attendance_report_file(
        db, period, file_path, original_filename=original_filename
    )
    db.refresh(period)
    return {**result, "period": serialize_period(period, db)}

