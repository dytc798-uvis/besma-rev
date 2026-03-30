from fastapi import APIRouter

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, Role
from app.modules.approvals.models import ApprovalHistory
from app.modules.documents.models import Document


router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/history")
def list_approval_history(
    db: DbDep,
    current_user: CurrentUserDep,
    document_id: int | None = None,
):
    query = db.query(ApprovalHistory).join(Document, ApprovalHistory.document_id == Document.id)

    if current_user.role == Role.SITE and current_user.site_id:
        query = query.filter(Document.site_id == current_user.site_id)

    if document_id:
        query = query.filter(ApprovalHistory.document_id == document_id)

    return query.order_by(ApprovalHistory.action_at.desc()).all()

