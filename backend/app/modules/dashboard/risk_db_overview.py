"""관리대장(근로자의견·부적합) risk DB / 운영 축 대시보드 집계 — risk_gates와 동일한 판정 기준."""

from __future__ import annotations

from typing import Literal

from sqlalchemy import and_, case, func, literal, or_
from sqlalchemy.orm import Session

from app.modules.safety_features import risk_gates as rg
from app.modules.safety_features.models import NonconformityItem, NonconformityLedger, WorkerVoiceItem, WorkerVoiceLedger

LedgerScope = Literal["worker_voice", "nonconformity", "both"]


def _receipt_effective_expr(model):
    return case(
        (model.receipt_decision.in_([rg.RECEIPT_ACCEPTED, rg.RECEIPT_REJECTED, rg.RECEIPT_PENDING]), model.receipt_decision),
        (model.site_rejected.is_(True), literal(rg.RECEIPT_REJECTED)),
        (model.site_approved.is_(True), literal(rg.RECEIPT_ACCEPTED)),
        else_=literal(rg.RECEIPT_PENDING),
    )


def _risk_req_effective_expr(model):
    return case(
        (model.risk_db_request_status.in_([rg.RISK_DB_REQ_REQUESTED, rg.RISK_DB_REQ_PENDING]), model.risk_db_request_status),
        else_=literal(rg.RISK_DB_REQ_PENDING),
    )


def _hq_effective_expr(model):
    return case(
        (model.risk_db_hq_status.in_([rg.RISK_DB_HQ_APPROVED, rg.RISK_DB_HQ_REJECTED, rg.RISK_DB_HQ_PENDING]), model.risk_db_hq_status),
        (model.hq_checked.is_(True), literal(rg.RISK_DB_HQ_APPROVED)),
        else_=literal(rg.RISK_DB_HQ_PENDING),
    )


def _action_norm_in(model):
    return func.lower(func.replace(func.coalesce(model.action_status, ""), "-", "_"))


def _in_progress_cond(model):
    a = _action_norm_in(model)
    return or_(a == "in_progress", a == "doing", a == "progress")


def _completed_cond(model):
    a = _action_norm_in(model)
    return a.in_(["completed", "complete", "done", "closed", "shared", "share_done"])


def _ready_for_risk_db_cond(model):
    return and_(
        model.site_rejected.is_(False),
        _receipt_effective_expr(model) == literal(rg.RECEIPT_ACCEPTED),
        _risk_req_effective_expr(model) == literal(rg.RISK_DB_REQ_REQUESTED),
        _hq_effective_expr(model) == literal(rg.RISK_DB_HQ_APPROVED),
    )


def _wv_base(db: Session, site_id: int | None):
    q = db.query(WorkerVoiceItem).join(WorkerVoiceLedger, WorkerVoiceLedger.id == WorkerVoiceItem.ledger_id)
    if site_id is not None:
        q = q.filter(WorkerVoiceLedger.site_id == site_id)
    return q


def _nc_base(db: Session, site_id: int | None):
    q = db.query(NonconformityItem).join(NonconformityLedger, NonconformityLedger.id == NonconformityItem.ledger_id)
    if site_id is not None:
        q = q.filter(NonconformityLedger.site_id == site_id)
    return q


def _scoped_sum(db: Session, site_id: int | None, scope: LedgerScope, wv_filter, nc_filter) -> int:
    """scope에 따라 근로자의견만 / 부적합만 / 둘 다 합산."""
    if scope == "worker_voice":
        return _wv_base(db, site_id).filter(wv_filter).count()
    if scope == "nonconformity":
        return _nc_base(db, site_id).filter(nc_filter).count()
    return _wv_base(db, site_id).filter(wv_filter).count() + _nc_base(db, site_id).filter(nc_filter).count()


def _hq_kpis(db: Session, site_id: int | None, scope: LedgerScope) -> dict[str, int]:
    return {
        "pending_requests": _scoped_sum(
            db,
            site_id,
            scope,
            _risk_req_effective_expr(WorkerVoiceItem) == literal(rg.RISK_DB_REQ_REQUESTED),
            _risk_req_effective_expr(NonconformityItem) == literal(rg.RISK_DB_REQ_REQUESTED),
        ),
        "pending_approval": _scoped_sum(
            db,
            site_id,
            scope,
            and_(
                _risk_req_effective_expr(WorkerVoiceItem) == literal(rg.RISK_DB_REQ_REQUESTED),
                _hq_effective_expr(WorkerVoiceItem) == literal(rg.RISK_DB_HQ_PENDING),
            ),
            and_(
                _risk_req_effective_expr(NonconformityItem) == literal(rg.RISK_DB_REQ_REQUESTED),
                _hq_effective_expr(NonconformityItem) == literal(rg.RISK_DB_HQ_PENDING),
            ),
        ),
        "rejected": _scoped_sum(
            db,
            site_id,
            scope,
            _hq_effective_expr(WorkerVoiceItem) == literal(rg.RISK_DB_HQ_REJECTED),
            _hq_effective_expr(NonconformityItem) == literal(rg.RISK_DB_HQ_REJECTED),
        ),
        "approved": _scoped_sum(
            db,
            site_id,
            scope,
            _ready_for_risk_db_cond(WorkerVoiceItem),
            _ready_for_risk_db_cond(NonconformityItem),
        ),
        "reward_candidates": _scoped_sum(
            db,
            site_id,
            scope,
            WorkerVoiceItem.reward_candidate.is_(True),
            NonconformityItem.reward_candidate.is_(True),
        ),
    }


def _site_kpis(db: Session, site_id: int | None, scope: LedgerScope) -> dict[str, int]:
    return {
        "unreceived": _scoped_sum(
            db,
            site_id,
            scope,
            _receipt_effective_expr(WorkerVoiceItem) == literal(rg.RECEIPT_PENDING),
            _receipt_effective_expr(NonconformityItem) == literal(rg.RECEIPT_PENDING),
        ),
        "in_progress": _scoped_sum(
            db,
            site_id,
            scope,
            _in_progress_cond(WorkerVoiceItem),
            _in_progress_cond(NonconformityItem),
        ),
        "action_completed": _scoped_sum(
            db,
            site_id,
            scope,
            _completed_cond(WorkerVoiceItem),
            _completed_cond(NonconformityItem),
        ),
        "db_request_needed": _scoped_sum(
            db,
            site_id,
            scope,
            and_(
                _receipt_effective_expr(WorkerVoiceItem) == literal(rg.RECEIPT_ACCEPTED),
                _risk_req_effective_expr(WorkerVoiceItem) == literal(rg.RISK_DB_REQ_PENDING),
            ),
            and_(
                _receipt_effective_expr(NonconformityItem) == literal(rg.RECEIPT_ACCEPTED),
                _risk_req_effective_expr(NonconformityItem) == literal(rg.RISK_DB_REQ_PENDING),
            ),
        ),
        "db_requested": _scoped_sum(
            db,
            site_id,
            scope,
            _risk_req_effective_expr(WorkerVoiceItem) == literal(rg.RISK_DB_REQ_REQUESTED),
            _risk_req_effective_expr(NonconformityItem) == literal(rg.RISK_DB_REQ_REQUESTED),
        ),
    }


def compute_risk_db_overview(db: Session, site_id: int | None) -> dict:
    """site_id가 None이면 전체 현장 합산(본사). 지정 시 해당 현장만.

    응답: hq/site 각각 combined(합산) + worker_voice + nonconformity.
    """
    wv_hq = _hq_kpis(db, site_id, "worker_voice")
    nc_hq = _hq_kpis(db, site_id, "nonconformity")
    comb_hq = _hq_kpis(db, site_id, "both")

    wv_site = _site_kpis(db, site_id, "worker_voice")
    nc_site = _site_kpis(db, site_id, "nonconformity")
    comb_site = _site_kpis(db, site_id, "both")

    return {
        "hq": {
            "combined": comb_hq,
            "worker_voice": wv_hq,
            "nonconformity": nc_hq,
        },
        "site": {
            "combined": comb_site,
            "worker_voice": wv_site,
            "nonconformity": nc_site,
        },
    }
