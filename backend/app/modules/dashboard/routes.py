from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, Role
from app.modules.dashboard.risk_db_overview import compute_risk_db_overview
from app.modules.documents.models import Document, DocumentStatus
from app.modules.opinions.models import Opinion, OpinionStatus
from app.modules.safety_features.models import NonconformityItem, NonconformityLedger, WorkerVoiceItem, WorkerVoiceLedger
from app.modules.sites.models import Site


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_RISK_DB_OVERVIEW_ROLES = frozenset(
    {Role.SITE, Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN, Role.ACCIDENT_ADMIN}
)


@router.get("/summary")
def dashboard_summary(
    db: DbDep,
    current_user: CurrentUserDep,
    site_code: str | None = Query(default=None),
):
    query_docs = db.query(Document)
    query_opinions = db.query(Opinion)
    query_worker_voice = db.query(WorkerVoiceItem).join(WorkerVoiceLedger, WorkerVoiceLedger.id == WorkerVoiceItem.ledger_id)
    query_nonconformity = db.query(NonconformityItem).join(NonconformityLedger, NonconformityLedger.id == NonconformityItem.ledger_id)

    if current_user.role == Role.SITE and current_user.site_id:
        query_docs = query_docs.filter(Document.site_id == current_user.site_id)
        query_opinions = query_opinions.filter(Opinion.site_id == current_user.site_id)
        query_worker_voice = query_worker_voice.filter(WorkerVoiceLedger.site_id == current_user.site_id)
        query_nonconformity = query_nonconformity.filter(NonconformityLedger.site_id == current_user.site_id)
    elif site_code:
        site_ids_q = db.query(Site.id).filter(Site.site_code == site_code)
        query_docs = query_docs.filter(Document.site_id.in_(site_ids_q))
        query_opinions = query_opinions.filter(Opinion.site_id.in_(site_ids_q))
        query_worker_voice = query_worker_voice.filter(WorkerVoiceLedger.site_id.in_(site_ids_q))
        query_nonconformity = query_nonconformity.filter(NonconformityLedger.site_id.in_(site_ids_q))

    total_docs = query_docs.count()
    pending_docs = query_docs.filter(
        Document.current_status.in_(
            [DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW, DocumentStatus.RESUBMITTED]
        )
    ).count()
    rejected_docs = query_docs.filter(Document.current_status == DocumentStatus.REJECTED).count()

    total_opinions = query_opinions.count()
    pending_opinions = query_opinions.filter(
        Opinion.status.in_([OpinionStatus.RECEIVED, OpinionStatus.REVIEWING])
    ).count()
    worker_voice_items = query_worker_voice.count()
    nonconformity_items = query_nonconformity.count()

    by_site_query = db.query(Document.site_id, func.count(Document.id))
    if current_user.role == Role.SITE and current_user.site_id:
        by_site_query = by_site_query.filter(Document.site_id == current_user.site_id)
    elif site_code:
        by_site_query = by_site_query.filter(Document.site_id.in_(db.query(Site.id).filter(Site.site_code == site_code)))
    by_site = by_site_query.group_by(Document.site_id).all()

    return {
        "role": current_user.role,
        "ui_type": current_user.ui_type,
        "total_documents": total_docs,
        "pending_documents": pending_docs,
        "rejected_documents": rejected_docs,
        "total_opinions": total_opinions,
        "pending_opinions": pending_opinions,
        "worker_voice_items": worker_voice_items,
        "nonconformity_items": nonconformity_items,
        "documents_by_site": [
            {"site_id": site_id, "count": count} for site_id, count in by_site
        ],
    }


@router.get("/risk-db-overview")
def risk_db_overview(db: DbDep, current_user: CurrentUserDep):
    """근로자의견·부적합 관리대장: 운영 축 + 위험성평가 DB 승격 축 집계(본사/현장 공용)."""
    if current_user.role not in _RISK_DB_OVERVIEW_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    site_scope: int | None = None
    if current_user.role == Role.SITE:
        if not current_user.site_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SITE without site_id")
        site_scope = current_user.site_id
    return compute_risk_db_overview(db, site_scope)

