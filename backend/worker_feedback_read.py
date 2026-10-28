"""Additive stored-ledger read endpoint; no sync or write operations."""
import hashlib
import json
from datetime import date, datetime, timezone
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep
from app.modules.functional_eval.models import FunctionalEvalSiteRegistry
from app.modules.sites.models import Site
from app.modules.worker_feedback.models import WorkerFeedbackOpinion
from .routes import _assert_can_read, _is_hq_user, _site_code_for_user, _query_for_user

router = APIRouter(prefix="/worker-feedback", tags=["worker-feedback-desktop"])

def _desktop_canonical_sites(db: DbDep, current_user: Any, site_code: str | None):
    """Exact canonical code linkage only; never infer from submitted titles."""
    sites = {row.site_code: row for row in db.query(Site).all() if row.site_code}
    registry = {row.site_code: row for row in db.query(FunctionalEvalSiteRegistry).all() if row.site_code}
    codes = set(sites) | set(registry)
    if not _is_hq_user(current_user):
        own = _site_code_for_user(db, current_user)
        if not own:
            raise HTTPException(status_code=403, detail="Site context is required")
        if site_code and site_code != own:
            raise HTTPException(status_code=403, detail="Other site access is not allowed")
        codes &= {own}
    if site_code:
        if site_code not in codes:
            raise HTTPException(status_code=422, detail="SITE_CANONICAL_MAPPING_REQUIRED")
        codes &= {site_code}
    result = []
    for code in sorted(codes):
        site = sites.get(code)
        reg = registry.get(code)
        names = {name.strip() for name in [site.site_name if site else None, reg.erp_site_label if reg else None] if name and name.strip()}
        result.append({"site_code": code, "site_id": site.id if site else None,
            "site_name": next(iter(names)) if len(names) == 1 else None,
            "name_status": "verified" if len(names) == 1 else "conflict" if len(names) > 1 else "unavailable"})
    return result


def _submitted_at_value(row):
    if row.submitted_at is None:return None
    # SQLite drops the offset. Restore it only when the original receipt proves it.
    try:
        source=datetime.fromisoformat((row.submitted_at_raw or "").strip().replace("Z","+00:00"))
        if source.utcoffset() is not None and source.replace(tzinfo=None)==row.submitted_at.replace(tzinfo=None):return source.isoformat()
    except (ValueError,TypeError):pass
    return row.submitted_at.isoformat()


@router.get("/desktop-responses")
def list_desktop_worker_feedback_responses(
    db: DbDep,
    current_user: CurrentUserDep,
    site_code: str | None = Query(default=None, min_length=1, max_length=50),
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Read the persisted Google Form ledger without Google fetch or DB writes.

    Keep legacy /responses and its behavior separate. Desktop refresh must not
    accidentally authorize a sync, bonus, evaluation or identity reassignment.
    """
    _assert_can_read(current_user)
    if (from_date is None) != (to_date is None) or (from_date and to_date and from_date > to_date):
        raise HTTPException(status_code=422, detail="VALID_COMPLETE_DATE_RANGE_REQUIRED")
    sites = _desktop_canonical_sites(db, current_user, site_code)
    query = _query_for_user(db, current_user)
    if site_code:
        query = query.filter(WorkerFeedbackOpinion.matched_site_code == site_code)
    # The scope rows are read once; unknown-date coverage and period filtering
    # derive from the same result as the status counts and paged rows.
    scoped_rows = query.order_by(WorkerFeedbackOpinion.submitted_at.desc().nullslast(), WorkerFeedbackOpinion.id.desc()).limit(50001).all()
    if len(scoped_rows) > 50000:
        raise HTTPException(status_code=422, detail="EXACT_SITE_DESKTOP_READ_SCOPE_REQUIRED")
    unknown_dates = sum(row.submitted_at is None for row in scoped_rows)
    all_rows = [row for row in scoped_rows if not from_date or
        row.submitted_at is not None and from_date <= row.submitted_at.date() <= to_date]
    if len(all_rows) > 10000:
        raise HTTPException(status_code=422, detail="NARROWER_DESKTOP_READ_SCOPE_REQUIRED")
    total = len(all_rows)
    summary = {"total": total,
        "receipt_pending": sum(row.action_status == "PENDING" for row in all_rows),
        "action_incomplete": sum(row.action_status in {"PENDING", "RECEIVED"} for row in all_rows),
        "hq_evaluation_pending": sum(row.action_status == "DONE" and row.score_total is None for row in all_rows),
        "risk_db_review_pending": None}
    rows = all_rows
    by_code = {site["site_code"]: site for site in sites}
    items = []
    for row in rows:
        canonical = by_code.get(row.matched_site_code)
        items.append({"id": row.id, "source": "GOOGLE_FORMS", "submitted_at": _submitted_at_value(row),
            "worker_name": row.worker_name, "opinion_type": row.opinion_type, "content": row.content,
            "matched_site_code": row.matched_site_code,
            "matched_site_name": canonical["site_name"] if canonical else None,
            "site_name_status": canonical["name_status"] if canonical else "unavailable",
            "match_status": row.match_status, "action_status": row.action_status,
            "site_received_at": row.site_received_at.isoformat() if row.site_received_at else None,
            "action_taken_at": row.action_taken_at.isoformat() if row.action_taken_at else None,
            "action_result": row.action_result, "score_total": row.score_total,
            "bonus_points": row.bonus_points,
            "bonus_awarded_at": row.bonus_awarded_at.isoformat() if row.bonus_awarded_at else None})
    scope = {"site_code": site_code, "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None, "period_basis": "stored_submitted_at", "timezone": "unverified"}
    scope_complete = not (from_date and unknown_dates)
    token = hashlib.sha256(json.dumps({"scope": scope, "sites": sites, "items": items,
        "scope_complete": scope_complete, "unknown_dates": unknown_dates if from_date else 0},
        separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    page = items[offset:offset + limit]
    return {"schema": "besma.google-feedback.desktop.v1", "source": "GOOGLE_FORMS",
        "scope": scope, "sites": sites, "summary": summary, "total_count": total, "returned_count": len(page),
        "offset": offset, "limit": limit, "has_more": offset + len(page) < total,
        # complete describes this single response, not the client's accumulated pages.
        "complete": offset == 0 and len(page) == total,
        "scope_complete": scope_complete,
        "excluded_unknown_submitted_date_count": unknown_dates if from_date else 0,
        "snapshot_token": token, "items": page,
        # No verified durable successful-receipt timestamp exists in this ledger.
        "source_sync_performed": False, "last_sync_at": None, "freshness_verified": False,
        "read_at_utc": datetime.now(timezone.utc).isoformat()}


