from fastapi import APIRouter, Query
from sqlalchemy import func

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, Role
from app.modules.documents.models import Document, DocumentStatus
from app.modules.opinions.models import Opinion, OpinionStatus
from app.modules.sites.models import Site


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    db: DbDep,
    current_user: CurrentUserDep,
    site_code: str | None = Query(default=None),
):
    query_docs = db.query(Document)
    query_opinions = db.query(Opinion)

    if current_user.role == Role.SITE and current_user.site_id:
        query_docs = query_docs.filter(Document.site_id == current_user.site_id)
        query_opinions = query_opinions.filter(Opinion.site_id == current_user.site_id)
    elif site_code:
        site_ids_q = db.query(Site.id).filter(Site.site_code == site_code)
        query_docs = query_docs.filter(Document.site_id.in_(site_ids_q))
        query_opinions = query_opinions.filter(Opinion.site_id.in_(site_ids_q))

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
        "documents_by_site": [
            {"site_id": site_id, "count": count} for site_id, count in by_site
        ],
    }

