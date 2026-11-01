"""마감 후 제재 신고 — 본사 승인·반려."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.datetime_utils import format_kst_datetime_short, utc_now
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSanction, FunctionalEvalWorker
from app.modules.functional_eval.sanction_evidence import DEFAULT_SANCTION_PENALTY_POINTS
from app.modules.functional_eval.sanctions import resolve_sanction
from app.modules.users.models import User

SANCTION_STATUS_PENDING = "PENDING"
SANCTION_STATUS_APPROVED = "APPROVED"
SANCTION_STATUS_REJECTED = "REJECTED"

SANCTION_STATUS_LABELS = {
    SANCTION_STATUS_PENDING: "승인 대기",
    SANCTION_STATUS_APPROVED: "승인",
    SANCTION_STATUS_REJECTED: "반려",
}


def _serialize_pending(row: FunctionalEvalSanction, worker_name: str) -> dict[str, Any]:
    from app.modules.functional_eval.service import _serialize_sanction

    payload = _serialize_sanction(row, worker_name, None)
    payload["status"] = row.status
    payload["status_label"] = SANCTION_STATUS_LABELS.get(row.status or "", row.status or "")
    payload["created_at_label"] = format_kst_datetime_short(row.created_at)
    return payload


def list_pending_sanctions(db: Session, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalSanction, FunctionalEvalWorker)
        .join(FunctionalEvalWorker, FunctionalEvalWorker.id == FunctionalEvalSanction.worker_id)
        .filter(
            FunctionalEvalSanction.period_id == period.id,
            FunctionalEvalSanction.status == SANCTION_STATUS_PENDING,
        )
        .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
        .all()
    )
    return [_serialize_pending(sanction, worker.name) for sanction, worker in rows]


def approve_sanction(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    user: User,
    sanction_id: int,
) -> dict[str, Any]:
    from app.modules.functional_eval import grade_stats_cache, service as fe_service

    row = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.id == sanction_id,
            FunctionalEvalSanction.period_id == period.id,
        )
        .first()
    )
    if row is None:
        raise ValueError("SANCTION_NOT_FOUND")
    if row.status != SANCTION_STATUS_PENDING:
        raise ValueError("SANCTION_NOT_PENDING")

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")

    prior_count = fe_service._count_approved_sanctions_for_violation(db, worker, row.violation_code)
    sanction_result, strike = resolve_sanction(row.violation_code, prior_count)
    if prior_count > 0:
        points = max(1, min(int(row.penalty_points or DEFAULT_SANCTION_PENALTY_POINTS), 100))
    else:
        points = 0

    row.sanction_result = sanction_result
    row.strike_number = strike
    row.penalty_points = points
    row.status = SANCTION_STATUS_APPROVED
    row.reviewed_by_user_id = user.id
    row.reviewed_at = utc_now()
    db.add(row)
    db.flush()

    from app.modules.functional_eval.sanctions import VIOLATION_BY_CODE

    item = VIOLATION_BY_CODE.get(row.violation_code)
    violation_label = item.label if item else row.violation_code
    display_note = row.note or ("사진 근거" if (row.evidence_type or "").upper() == "PHOTO" else "")
    fe_service._apply_safety_bottom_from_violation(
        db,
        worker=worker,
        user=user,
        sanction_row=row,
        violation_code=row.violation_code,
        violation_label=violation_label,
        note=display_note or "",
    )
    db.commit()
    db.refresh(row)
    grade_stats_cache.mark_dirty(db, period)
    strike_sequence = fe_service._strike_sequence_for_person(db, worker.rrn_hash)
    return fe_service._serialize_sanction(row, worker.name, db, strike_sequence=strike_sequence)


def reject_sanction(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    sanction_id: int,
    user: User,
    reject_note: str | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service as fe_service

    row = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.id == sanction_id,
            FunctionalEvalSanction.period_id == period.id,
        )
        .first()
    )
    if row is None:
        raise ValueError("SANCTION_NOT_FOUND")
    if row.status != SANCTION_STATUS_PENDING:
        raise ValueError("SANCTION_NOT_PENDING")

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")

    row.status = SANCTION_STATUS_REJECTED
    row.reviewed_by_user_id = user.id
    row.reviewed_at = utc_now()
    row.reject_note = (reject_note or "").strip() or None
    db.commit()
    db.refresh(row)
    strike_sequence = fe_service._strike_sequence_for_person(db, worker.rrn_hash)
    return fe_service._serialize_sanction(row, worker.name, db, strike_sequence=strike_sequence)
