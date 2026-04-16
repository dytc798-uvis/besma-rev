"""관리대장 row: 운영(접수·조치) 축 vs 위험성평가 DB 승격 축 — 상수·게이트."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

# --- receipt (현장 접수 판단) ---
RECEIPT_PENDING = "pending"
RECEIPT_ACCEPTED = "accepted"
RECEIPT_REJECTED = "rejected"

# --- operational action progress ---
ACTION_NOT_STARTED = "not_started"
ACTION_IN_PROGRESS = "in_progress"
ACTION_COMPLETED = "completed"

# --- risk DB promotion (별도 축) ---
RISK_DB_REQ_PENDING = "pending"
RISK_DB_REQ_REQUESTED = "requested"

RISK_DB_HQ_PENDING = "pending"
RISK_DB_HQ_APPROVED = "approved"
RISK_DB_HQ_REJECTED = "rejected"


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def receipt_decision_effective(item: Any) -> str:
    """DB 컬럼 우선, 없으면 기존 site 플래그에서 유도."""
    rd = _norm(getattr(item, "receipt_decision", None))
    if rd in (RECEIPT_ACCEPTED, RECEIPT_REJECTED, RECEIPT_PENDING):
        return rd
    if getattr(item, "site_rejected", False):
        return RECEIPT_REJECTED
    if getattr(item, "site_approved", False):
        return RECEIPT_ACCEPTED
    return RECEIPT_PENDING


def risk_db_request_status_effective(item: Any) -> str:
    rs = _norm(getattr(item, "risk_db_request_status", None))
    if rs in (RISK_DB_REQ_REQUESTED, RISK_DB_REQ_PENDING):
        return rs
    return RISK_DB_REQ_PENDING


def risk_db_hq_status_effective(item: Any) -> str:
    hs = _norm(getattr(item, "risk_db_hq_status", None))
    if hs in (RISK_DB_HQ_APPROVED, RISK_DB_HQ_REJECTED, RISK_DB_HQ_PENDING):
        return hs
    if getattr(item, "hq_checked", False):
        return RISK_DB_HQ_APPROVED
    return RISK_DB_HQ_PENDING


def normalize_action_status(raw: str | None) -> str | None:
    """레거시 값을 운영 축으로 정규화. None/빈값은 None."""
    if raw is None:
        return None
    k = _norm(raw).replace("-", "_")
    if k in ("", "none"):
        return None
    if k in ("not_started", "none_yet", "open", "hold", "pending"):
        return ACTION_NOT_STARTED
    if k in ("in_progress", "doing", "progress"):
        return ACTION_IN_PROGRESS
    if k in ("completed", "complete", "done", "closed", "shared", "share_done"):
        return ACTION_COMPLETED
    return raw.strip()[:30] if raw.strip() else None


def worker_voice_item_ready_for_risk_db(item: Any) -> bool:
    """위험성평가 DB 승격(반영 후보) — 접수 승인 + 현장 DB등록요청 + 본사 DB승인 + 현장 반려 아님."""
    if getattr(item, "site_rejected", False):
        return False
    if receipt_decision_effective(item) != RECEIPT_ACCEPTED:
        return False
    if risk_db_request_status_effective(item) != RISK_DB_REQ_REQUESTED:
        return False
    return risk_db_hq_status_effective(item) == RISK_DB_HQ_APPROVED


def nonconformity_item_ready_for_risk_db(item: Any) -> bool:
    return worker_voice_item_ready_for_risk_db(item)


def assert_hq_can_approve_risk_db(item: Any) -> None:
    """HQ가 위험성평가 DB 등록을 승인하기 전 검증. 불충족 시 409."""
    if getattr(item, "site_rejected", False):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SITE rejected receipt; cannot approve risk DB")
    if receipt_decision_effective(item) != RECEIPT_ACCEPTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SITE receipt (accept) required before risk DB approval")
    if risk_db_request_status_effective(item) != RISK_DB_REQ_REQUESTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SITE risk DB registration request required first")
    if risk_db_hq_status_effective(item) == RISK_DB_HQ_APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Risk DB registration already approved")


def assert_hq_can_reject_risk_db(item: Any) -> None:
    """HQ가 위험성평가 DB 등록을 반려하기 전 검증."""
    if risk_db_request_status_effective(item) != RISK_DB_REQ_REQUESTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No SITE risk DB registration request to reject")
    if risk_db_hq_status_effective(item) == RISK_DB_HQ_APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Risk DB registration already approved; cannot reject")
