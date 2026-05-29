from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.enums import Role, UIType
from app.core.datetime_utils import utc_now
from app.modules.functional_eval.eval_catalog import EvalType, catalog_for_api, compute_assessment, get_criteria
from app.modules.functional_eval.models import (
    FunctionalEvalAssessment,
    FunctionalEvalPeriod,
    FunctionalEvalRosterImportBatch,
    FunctionalEvalSanction,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import (
    ParsedRosterRow,
    RosterDiffItem,
    RosterDiffResult,
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


def serialize_period(period: FunctionalEvalPeriod) -> dict[str, Any]:
    return {
        "id": period.id,
        "title": period.title,
        "deadline_date": period.deadline_date,
        "is_active": period.is_active,
        "is_closed": period_is_closed(period),
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
    rows = (
        db.query(User)
        .filter(
            User.role == Role.SITE_FUNCTIONAL_EVAL,
            User.login_id.in_(site_codes),
        )
        .all()
    )
    return {u.login_id: u.name for u in rows if u.login_id}


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
) -> list[dict[str, Any]]:
    by_site: dict[str, dict[str, Any]] = {}
    for worker in workers:
        code = worker.site_code or ""
        if code not in by_site:
            by_site[code] = {
                "site_code": code,
                "site_name": worker.site_name or site_names.get(code) or f"현장 {code}",
                "evaluator_name": evaluators.get(code) or "—",
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


def build_hq_sites_overview(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
) -> dict[str, Any]:
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_site_manager.is_(False),
        FunctionalEvalWorker.is_active.is_(True),
    )
    if site_code:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    workers = q.all()
    site_codes = {w.site_code for w in workers if w.site_code}
    site_names = _site_name_map(db, site_codes)
    evaluators = _site_evaluator_map(db, site_codes)
    assess_map = _assessments_map(db, [w.id for w in workers])
    sites = _aggregate_site_eval_stats(workers, assess_map, site_names, evaluators)

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
    return {
        "period": serialize_period(period),
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


def _site_code_for_user(user: User) -> str:
    return (user.login_id or "").strip()


def _assert_worker_access(user: User, worker: FunctionalEvalWorker) -> None:
    if user.role == Role.SITE_FUNCTIONAL_EVAL and _site_code_for_user(user) != worker.site_code:
        raise ValueError("SITE_MISMATCH")


def list_workers_for_user(db: Session, user: User, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    site_code = _site_code_for_user(user)
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_site_manager.is_(False),
        FunctionalEvalWorker.is_active.is_(True),
    )
    if user.role == Role.SITE_FUNCTIONAL_EVAL:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    rows = q.order_by(FunctionalEvalWorker.row_no.asc(), FunctionalEvalWorker.id.asc()).all()
    assess_map = _assessments_map(db, [r.id for r in rows])
    return [serialize_worker(db, row, assessments=assess_map.get(row.id, {})) for row in rows]


def get_worker_history(db: Session, user: User, worker_id: int) -> dict[str, Any]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    _assert_worker_access(user, worker)

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
    if not worker.is_active:
        raise ValueError("WORKER_INACTIVE")

    _assert_worker_access(user, worker)

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
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_site_manager.is_(False),
    )
    if not include_inactive:
        q = q.filter(FunctionalEvalWorker.is_active.is_(True))
    if site_code:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    workers = q.all()
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
                is_site_manager=row.is_site_manager,
                is_active=True,
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
            worker.is_site_manager = row.is_site_manager
            worker.is_active = True
            worker.removed_at = None
            worker.updated_at = now
            db.add(worker)

    for rrn_hash, worker in by_hash.items():
        if rrn_hash in incoming_hashes:
            continue
        if not worker.is_active:
            continue
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
    _assert_worker_access(user, worker)
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
    _assert_worker_access(user, worker)
    if worker.is_site_manager:
        raise ValueError("CANNOT_EVALUATE_SITE_MANAGER")
    if not worker.is_active:
        raise ValueError("WORKER_INACTIVE")
    period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == worker.period_id).first()
    if period and period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")

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
