"""기능인제 현장별 다단계 승인 (소장 → 안전보건실 → 대표이사)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.modules.functional_eval.constants import (
    APPROVAL_STATUS_CEO_APPROVED,
    APPROVAL_STATUS_HQ_APPROVED,
    APPROVAL_STATUS_IN_PROGRESS,
    APPROVAL_STATUS_LABELS,
    APPROVAL_STATUS_REJECTED,
    APPROVAL_STATUS_SITE_APPROVED,
    CEO_EVAL_LOGIN_IDS,
)
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteApproval, FunctionalEvalWorker
from app.modules.users.models import User


def _role_value(role: Role | str) -> str:
    return role.value if isinstance(role, Role) else str(role)


def get_or_create_site_approval(db: Session, period_id: int, site_code: str) -> FunctionalEvalSiteApproval:
    row = (
        db.query(FunctionalEvalSiteApproval)
        .filter(
            FunctionalEvalSiteApproval.period_id == period_id,
            FunctionalEvalSiteApproval.site_code == site_code,
        )
        .first()
    )
    if row is None:
        row = FunctionalEvalSiteApproval(
            period_id=period_id,
            site_code=site_code,
            status=APPROVAL_STATUS_IN_PROGRESS,
        )
        db.add(row)
        db.flush()
    return row


def is_site_evaluation_editable(status: str) -> bool:
    return status in {APPROVAL_STATUS_IN_PROGRESS, APPROVAL_STATUS_REJECTED}


def serialize_site_approval(row: FunctionalEvalSiteApproval | None) -> dict[str, Any]:
    if row is None:
        return {
            "status": APPROVAL_STATUS_IN_PROGRESS,
            "status_label": APPROVAL_STATUS_LABELS[APPROVAL_STATUS_IN_PROGRESS],
            "site_submitted_at": None,
            "hq_approved_at": None,
            "ceo_approved_at": None,
            "reject_note": None,
            "rejected_stage": None,
        }
    return {
        "status": row.status,
        "status_label": APPROVAL_STATUS_LABELS.get(row.status, row.status),
        "site_submitted_at": row.site_submitted_at.isoformat() if row.site_submitted_at else None,
        "hq_approved_at": row.hq_approved_at.isoformat() if row.hq_approved_at else None,
        "ceo_approved_at": row.ceo_approved_at.isoformat() if row.ceo_approved_at else None,
        "reject_note": row.reject_note,
        "rejected_stage": row.rejected_stage,
    }


def assert_site_editable(db: Session, period_id: int, site_code: str) -> None:
    row = get_or_create_site_approval(db, period_id, site_code)
    if not is_site_evaluation_editable(row.status):
        raise ValueError("SITE_APPROVAL_LOCKED")


def submit_site_approval(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    site_code: str,
    user: User,
    incomplete_count: int,
) -> dict[str, Any]:
    if incomplete_count > 0:
        raise ValueError("INCOMPLETE_EVALUATIONS")
    row = get_or_create_site_approval(db, period.id, site_code)
    if row.status not in {APPROVAL_STATUS_IN_PROGRESS, APPROVAL_STATUS_REJECTED}:
        raise ValueError("INVALID_APPROVAL_TRANSITION")
    now = utc_now()
    row.status = APPROVAL_STATUS_SITE_APPROVED
    row.site_submitted_at = now
    row.site_submitted_by_user_id = user.id
    row.hq_approved_at = None
    row.hq_approved_by_user_id = None
    row.ceo_approved_at = None
    row.ceo_approved_by_user_id = None
    row.reject_note = None
    row.rejected_stage = None
    row.rejected_at = None
    row.rejected_by_user_id = None
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_site_approval(row)


def approve_hq(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    site_code: str,
    user: User,
) -> dict[str, Any]:
    row = get_or_create_site_approval(db, period.id, site_code)
    if row.status != APPROVAL_STATUS_SITE_APPROVED:
        raise ValueError("INVALID_APPROVAL_TRANSITION")
    now = utc_now()
    row.status = APPROVAL_STATUS_HQ_APPROVED
    row.hq_approved_at = now
    row.hq_approved_by_user_id = user.id
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_site_approval(row)


def approve_ceo(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    site_code: str,
    user: User,
) -> dict[str, Any]:
    row = get_or_create_site_approval(db, period.id, site_code)
    if row.status != APPROVAL_STATUS_HQ_APPROVED:
        raise ValueError("INVALID_APPROVAL_TRANSITION")
    now = utc_now()
    row.status = APPROVAL_STATUS_CEO_APPROVED
    row.ceo_approved_at = now
    row.ceo_approved_by_user_id = user.id
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_site_approval(row)


def reject_approval(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    site_code: str,
    user: User,
    stage: str,
    note: str | None,
) -> dict[str, Any]:
    row = get_or_create_site_approval(db, period.id, site_code)
    allowed: dict[str, set[str]] = {
        "HQ": {APPROVAL_STATUS_SITE_APPROVED},
        "CEO": {APPROVAL_STATUS_HQ_APPROVED},
        "SITE": {APPROVAL_STATUS_SITE_APPROVED},
    }
    if row.status not in allowed.get(stage, set()):
        raise ValueError("INVALID_APPROVAL_TRANSITION")
    row.status = APPROVAL_STATUS_REJECTED
    row.rejected_stage = stage
    row.reject_note = (note or "").strip() or None
    row.rejected_at = utc_now()
    row.rejected_by_user_id = user.id
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_site_approval(row)


def list_pending_hq_approvals(db: Session, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalSiteApproval)
        .filter(
            FunctionalEvalSiteApproval.period_id == period.id,
            FunctionalEvalSiteApproval.status == APPROVAL_STATUS_SITE_APPROVED,
        )
        .order_by(FunctionalEvalSiteApproval.site_submitted_at.asc())
        .all()
    )
    return [_serialize_approval_queue_item(db, period, row) for row in rows]


def list_pending_ceo_approvals(db: Session, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalSiteApproval)
        .filter(
            FunctionalEvalSiteApproval.period_id == period.id,
            FunctionalEvalSiteApproval.status == APPROVAL_STATUS_HQ_APPROVED,
        )
        .order_by(FunctionalEvalSiteApproval.hq_approved_at.asc())
        .all()
    )
    return [_serialize_approval_queue_item(db, period, row) for row in rows]


def _serialize_approval_queue_item(
    db: Session,
    period: FunctionalEvalPeriod,
    row: FunctionalEvalSiteApproval,
) -> dict[str, Any]:
    from app.modules.functional_eval.service import serialize_site_approval_summary

    summary = serialize_site_approval_summary(db, period, row.site_code)
    return {
        "site_code": row.site_code,
        **serialize_site_approval(row),
        **summary,
    }


def assert_hq_approver(user: User) -> None:
    if _role_value(user.role) not in {
        Role.HQ_SAFE.value,
        Role.HQ_SAFE_ADMIN.value,
        Role.SUPER_ADMIN.value,
    }:
        raise ValueError("HQ_APPROVER_ONLY")


def assert_ceo_approver(user: User) -> None:
    login_id = (user.login_id or "").strip()
    if login_id in CEO_EVAL_LOGIN_IDS:
        return
    if _role_value(user.role) == Role.SUPER_ADMIN.value:
        return
    raise ValueError("CEO_APPROVER_ONLY")
