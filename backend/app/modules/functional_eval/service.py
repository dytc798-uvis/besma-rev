from __future__ import annotations

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
from app.modules.functional_eval.eval_catalog import EvalType, catalog_for_api, compute_assessment, get_criteria
from app.modules.functional_eval.attendance import ParsedAttendanceRow, parse_attendance_report_xlsx
from app.modules.functional_eval.models import (
    FunctionalEvalAssessment,
    FunctionalEvalAttendanceEntry,
    FunctionalEvalAttendanceImportBatch,
    FunctionalEvalPeriod,
    FunctionalEvalRosterImportBatch,
    FunctionalEvalSanction,
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
    is_permanent_sanction,
    resolve_sanction,
    worker_status_from_sanctions,
)
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.utils.file_ingestion import parse_excel_with_fallback

from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD

DEFAULT_PERIOD_TITLE = "기능인제 인사고과"
DEFAULT_DEADLINE = date(2026, 6, 26)


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
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def period_is_closed(period: FunctionalEvalPeriod, *, today: date | None = None) -> bool:
    ref = today or utc_now().date()
    return ref > period.deadline_date


def assert_period_editable(period: FunctionalEvalPeriod) -> None:
    if period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")


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


def _serialize_sanction(row: FunctionalEvalSanction, worker_name: str) -> dict[str, Any]:
    item = VIOLATION_BY_CODE.get(row.violation_code)
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
        "strike_number": row.strike_number,
        "sanction_result": row.sanction_result,
        "sanction_result_label": SANCTION_RESULT_LABELS.get(row.sanction_result, row.sanction_result),
        "note": row.note,
        "reported_by_user_id": row.reported_by_user_id,
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
    rows = _worker_sanction_rows(db, worker_id)
    return any(is_permanent_sanction(r.sanction_result) for r in rows)


def _worker_sanction_status(db: Session, worker_id: int) -> tuple[str, str, int, FunctionalEvalSanction | None]:
    rows = _worker_sanction_rows(db, worker_id)
    if not rows:
        return "NONE", "해당 없음", 0, None
    results = [r.sanction_result for r in rows]
    status = worker_status_from_sanctions(results)
    label = SANCTION_RESULT_LABELS.get(status, status if status != "NONE" else "해당 없음")
    return status, label, len(rows), rows[0]


def _serialize_assessment(row: FunctionalEvalAssessment | None, eval_type: EvalType) -> dict[str, Any] | None:
    if row is None:
        return None
    required = len(get_criteria(eval_type))
    scores = row.scores_json or {}
    return {
        "eval_type": row.eval_type,
        "scores": scores,
        "total_score": row.total_score,
        "max_score": row.max_score,
        "grade_code": row.grade_code,
        "grade_label": row.grade_label,
        "is_complete": len(scores) >= required and required > 0,
        "updated_at": row.updated_at,
    }


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


def serialize_worker(
    db: Session,
    worker: FunctionalEvalWorker,
    *,
    assessments: dict[str, FunctionalEvalAssessment] | None = None,
) -> dict[str, Any]:
    status, status_label, count, latest = _worker_sanction_status(db, worker.id)
    permanent = _worker_is_permanently_expelled(db, worker.id)
    if assessments is None:
        assessments = _assessments_map(db, [worker.id]).get(worker.id, {})
    functional = _serialize_assessment(assessments.get("FUNCTIONAL"), "FUNCTIONAL")
    safety = _serialize_assessment(assessments.get("SAFETY"), "SAFETY")
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
        "assigned_evaluator_login_id": worker.assigned_evaluator_login_id,
        "is_site_manager": worker.is_site_manager,
        "is_active": worker.is_active,
        "sanction_status": status,
        "sanction_status_label": status_label if status != "NONE" else "해당 없음",
        "sanction_count": count,
        "is_permanently_expelled": permanent,
        "history_visible": not permanent,
        "latest_sanction": _serialize_sanction(latest, worker.name) if latest and not permanent else None,
        "mileage": serialize_mileage_placeholder(worker),
        "functional_assessment": functional,
        "safety_assessment": safety,
        "mileage_note": worker.mileage_note,
    }
    return payload


GRADE_SORT_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def _grade_sort_key(assessment: dict[str, Any] | None) -> tuple[int, int, str]:
    if not assessment or not assessment.get("is_complete"):
        return (1, 99, "")
    code = str(assessment.get("grade_code") or "")
    return (0, GRADE_SORT_ORDER.get(code, 50), code)


def _eval_grade_label(assessment: dict[str, Any] | None) -> str:
    if not assessment or not assessment.get("is_complete"):
        return "미평가"
    return str(assessment.get("grade_label") or assessment.get("grade_code") or "—")


def _is_fully_evaluated(worker_payload: dict[str, Any]) -> bool:
    f = worker_payload.get("functional_assessment") or {}
    s = worker_payload.get("safety_assessment") or {}
    return bool(f.get("is_complete")) and bool(s.get("is_complete"))


def _worker_eval_remark(worker_payload: dict[str, Any]) -> str:
    parts: list[str] = []
    f = worker_payload.get("functional_assessment") or {}
    s = worker_payload.get("safety_assessment") or {}
    if not f.get("is_complete"):
        parts.append("기능미완")
    if not s.get("is_complete"):
        parts.append("안전미완")
    if (worker_payload.get("sanction_count") or 0) > 0:
        label = worker_payload.get("sanction_status_label") or ""
        if label and label != "해당 없음":
            parts.append(f"제재:{label}")
    note = (worker_payload.get("mileage_note") or "").strip()
    if note:
        parts.append(note)
    return " · ".join(parts) if parts else "—"


def _site_name_map(db: Session, site_codes: set[str]) -> dict[str, str]:
    if not site_codes:
        return {}
    rows = db.query(Site).filter(Site.site_code.in_(site_codes)).all()
    return {s.site_code: s.site_name for s in rows if s.site_code}


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
        row["has_completed"] = fc > 0
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


def build_hq_sites_overview(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
) -> dict[str, Any]:
    """본사 현장 목록 = 기간 내 출역일보에 등장한 현장만 (출역 없는 소장 현장 제외)."""
    workers = _attendance_target_workers(db, period, site_code=site_code)
    attendance_site_codes, erp_labels, rep_evaluators = _attendance_site_meta(db, period.id)
    if site_code:
        attendance_site_codes = {site_code} & attendance_site_codes

    all_codes = attendance_site_codes | {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, all_codes)
    evaluator_site_codes = _hq_evaluator_site_codes(db)
    evaluators = _site_evaluator_map(db, all_codes)
    assess_map = _assessments_map(db, [w.id for w in workers])
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


def _remark_for_completed_worker(worker_payload: dict[str, Any]) -> str:
    parts: list[str] = []
    if (worker_payload.get("sanction_count") or 0) > 0:
        label = worker_payload.get("sanction_status_label") or ""
        if label and label != "해당 없음":
            parts.append(f"제재:{label}")
    note = (worker_payload.get("mileage_note") or "").strip()
    if note:
        parts.append(note)
    return " · ".join(parts) if parts else "—"


def build_hq_eval_rows(items: list[dict[str, Any]], *, completed_only: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        w = item["worker"]
        if completed_only and not _is_fully_evaluated(w):
            continue
        rows.append(
            {
                "worker_id": w["id"],
                "site_code": w.get("site_code"),
                "site_name": w.get("site_name"),
                "name": w.get("name"),
                "is_active": w.get("is_active"),
                "functional_grade": _eval_grade_label(w.get("functional_assessment")),
                "safety_grade": _eval_grade_label(w.get("safety_assessment")),
                "functional_score": (w.get("functional_assessment") or {}).get("total_score"),
                "safety_score": (w.get("safety_assessment") or {}).get("total_score"),
                "remark": _remark_for_completed_worker(w) if _is_fully_evaluated(w) else _worker_eval_remark(w),
                "is_fully_complete": _is_fully_evaluated(w),
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
        include_inactive=False,
    )
    completed_items = [i for i in items if _is_fully_evaluated(i["worker"])]
    site_names = _site_name_map(db, {site_code})
    evaluators = _site_evaluator_map(db, {site_code})
    total = len(items)
    fully = len(completed_items)
    first = items[0]["worker"] if items else {}
    site_row = {
        "site_code": site_code,
        "site_name": first.get("site_name") or site_names.get(site_code) or f"현장 {site_code}",
        "evaluator_name": evaluators.get(site_code) or "—",
        "total": total,
        "fully_complete": fully,
        "progress": f"{fully}/{total}",
        "has_completed": fully > 0,
    }
    return {
        "site": site_row,
        "eval_rows": build_hq_eval_rows(completed_items, completed_only=True),
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


def list_hq_eval_export_rows(db: Session, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    items = list_hq_summary(db, period, sort_by="site_code", sort_dir="asc", include_inactive=False)
    rows: list[dict[str, Any]] = []
    site_codes = {item["worker"].get("site_code") for item in items if item["worker"].get("site_code")}
    evaluators = _site_evaluator_map(db, site_codes)
    for item in items:
        w = item["worker"]
        code = w.get("site_code") or ""
        rows.append(
            {
                "site_code": code,
                "site_name": w.get("site_name") or f"현장 {code}",
                "evaluator_name": evaluators.get(code) or "—",
                "name": w.get("name"),
                "functional_grade": _eval_grade_label(w.get("functional_assessment")),
                "safety_grade": _eval_grade_label(w.get("safety_assessment")),
                "fully_complete": "Y" if _is_fully_evaluated(w) else "N",
                "remark": _worker_eval_remark(w),
            }
        )
    return rows


def build_hq_summary_totals(items: list[dict[str, Any]]) -> dict[str, int]:
    workers = [item["worker"] for item in items]
    fully = sum(1 for w in workers if _is_fully_evaluated(w))
    return {
        "workers": len(workers),
        "fully_complete": fully,
        "incomplete": len(workers) - fully,
    }


def serialize_mileage_placeholder(worker: FunctionalEvalWorker) -> dict[str, Any]:
    return {
        "status": "PREPARED",
        "points": worker.mileage_points,
        "note": worker.mileage_note,
        "message": "우수 의견 마일리지 제도 운영 준비 중입니다.",
    }


def _site_code_for_user(user: User, db: Session) -> str:
    if user.site_id:
        site = db.query(Site).filter(Site.id == user.site_id).first()
        if site and site.site_code:
            return site.site_code
    login = (user.login_id or "").strip()
    if login.isdigit():
        return login
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


def _is_primary_site_evaluator(db: Session, user: User, site_code: str) -> bool:
    login_id = (user.login_id or "").strip()
    if login_id == site_code:
        return True
    return login_id == _manager_login_for_site(db, site_code)


def _assert_worker_access(db: Session, user: User, worker: FunctionalEvalWorker) -> None:
    if user.role != Role.SITE_FUNCTIONAL_EVAL:
        return
    login_id = (user.login_id or "").strip()
    site_code = _site_code_for_user(user, db)
    if site_code != worker.site_code:
        raise ValueError("SITE_MISMATCH")
    if _is_primary_site_evaluator(db, user, site_code):
        return
    assigned = (worker.assigned_evaluator_login_id or "").strip()
    if assigned and assigned != login_id:
        raise ValueError("SITE_MISMATCH")
    if not assigned:
        raise ValueError("SITE_MISMATCH")


def list_workers_for_user(db: Session, user: User, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    site_code = _site_code_for_user(user, db)
    login_id = (user.login_id or "").strip()
    work_date = get_latest_attendance_date(db, period.id)
    if work_date is None:
        return []
    rrn_hashes = _attendance_rrn_hashes_for_date(db, period.id, work_date, site_code=site_code)
    if not rrn_hashes:
        return []
    rows = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.period_id == period.id,
            FunctionalEvalWorker.is_site_manager.is_(False),
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.rrn_hash.in_(rrn_hashes),
        )
        .order_by(FunctionalEvalWorker.row_no.asc(), FunctionalEvalWorker.id.asc())
        .all()
    )
    if not _is_primary_site_evaluator(db, user, site_code):
        rows = [r for r in rows if (r.assigned_evaluator_login_id or "").strip() == login_id]
    assess_map = _assessments_map(db, [r.id for r in rows])
    return [serialize_worker(db, row, assessments=assess_map.get(row.id, {})) for row in rows]


def get_worker_history(db: Session, user: User, worker_id: int) -> dict[str, Any]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    _assert_worker_access(db, user, worker)

    permanent = _worker_is_permanently_expelled(db, worker.id)
    worker_payload = serialize_worker(db, worker)

    if permanent:
        latest = _worker_sanction_rows(db, worker.id)
        summary = _serialize_sanction(latest[0], worker.name) if latest else None
        return {
            "worker": worker_payload,
            "history_visible": False,
            "sanctions": [],
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
    for pw in prior_workers:
        rows = (
            db.query(FunctionalEvalSanction)
            .filter(FunctionalEvalSanction.worker_id == pw.id)
            .order_by(FunctionalEvalSanction.created_at.asc())
            .all()
        )
        for row in rows:
            item = _serialize_sanction(row, pw.name)
            item["period_id"] = pw.period_id
            item["from_prior_period"] = True
            prior_sanctions.append(item)

    return {
        "worker": worker_payload,
        "history_visible": True,
        "sanctions": [_serialize_sanction(s, worker.name) for s in current],
        "prior_sanctions": prior_sanctions,
        "mileage": serialize_mileage_placeholder(worker),
    }


def record_sanction(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    user: User,
    worker_id: int,
    violation_code: str,
    note: str | None,
) -> dict[str, Any]:
    assert_period_editable(period)
    if violation_code not in VIOLATION_BY_CODE:
        raise ValueError("UNKNOWN_VIOLATION")

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None or worker.period_id != period.id:
        raise ValueError("WORKER_NOT_FOUND")
    if worker.is_site_manager:
        raise ValueError("CANNOT_SANCTION_SITE_MANAGER")
    _assert_worker_attendance_eligible(db, period, worker)
    _assert_worker_access(db, user, worker)

    prior_count = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.period_id == period.id,
            FunctionalEvalSanction.worker_id == worker.id,
            FunctionalEvalSanction.violation_code == violation_code,
        )
        .count()
    )
    sanction_result, strike = resolve_sanction(violation_code, prior_count)
    item = VIOLATION_BY_CODE[violation_code]

    row = FunctionalEvalSanction(
        period_id=period.id,
        worker_id=worker.id,
        site_code=worker.site_code,
        violation_code=violation_code,
        violation_category=item.category,
        strike_number=strike,
        sanction_result=sanction_result,
        note=(note or "").strip() or None,
        reported_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_sanction(row, worker.name)


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
    del include_inactive  # 출역 대상 기준; 명부 비활성과 무관
    workers = _attendance_target_workers(db, period, site_code=site_code)
    site_codes = {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, site_codes)
    assess_map = _assessments_map(db, [w.id for w in workers])
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
        items.append(
            {
                "worker": worker_payload,
                "sanctions": [_serialize_sanction(s, worker.name) for s in visible_sanctions],
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


def build_hq_summary_response(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
) -> dict[str, Any]:
    """본사 평가 현황 — 현장 목록·진행률만 반환 (근로자 상세는 현장별 API)."""
    return build_hq_sites_overview(
        db,
        period,
        sort_by=sort_by,
        sort_dir=sort_dir,
        site_code=site_code,
    )


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
        if not worker.is_on_reference_roster and not worker.is_active:
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
    return {
        "worker_id": worker_id,
        "eval_type": eval_type,
        "catalog": catalog_for_api()[eval_type],
        "assessment": _serialize_assessment(row, eval_type),
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
    _assert_worker_access(db, user, worker)
    if worker.is_site_manager:
        raise ValueError("CANNOT_EVALUATE_SITE_MANAGER")
    period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == worker.period_id).first()
    if period is None:
        raise ValueError("WORKER_NOT_FOUND")
    if period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")
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
    return _serialize_assessment(row, eval_type)


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
        for idx, (leader_name, meta) in enumerate(ordered_leaders, start=2):
            login_id = f"{site_code}-{idx}"
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
            names = {r.worker_name.strip() for r in team_workers if r.worker_name.strip()}
            rrn_hashes: set[str] = set()
            for r in team_workers:
                if r.worker_rrn_raw:
                    rrn_hashes.add(hash_rrn(r.worker_rrn_raw))
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
