from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.datetime_utils import kst_today
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster
from app.modules.documents.models import Document, DocumentUploadHistory
from app.modules.sites.models import Site
from app.modules.users.models import User


def _effective_workflow_status(inst: DocumentInstance, doc: Document | None) -> str:
    if doc is None:
        return WorkflowStatus.NOT_SUBMITTED
    return inst.workflow_status


def _is_missing(*, inst: DocumentInstance, doc: Document | None, today: date) -> bool:
    if inst.period_end >= today:
        return False
    if doc is None:
        return True
    return doc.submitted_at is None


def _period_label(inst: DocumentInstance) -> str:
    return f"{inst.period_start.isoformat()} ~ {inst.period_end.isoformat()}"


def _document_name(
    inst: DocumentInstance,
    requirement: DocumentRequirement | None,
    type_master: DocumentTypeMaster | None,
) -> str:
    if requirement is not None:
        return requirement.title
    if type_master is not None:
        return type_master.name
    return inst.document_type_code


def _review_result(effective_workflow: str) -> str | None:
    if effective_workflow == WorkflowStatus.APPROVED:
        return WorkflowStatus.APPROVED
    if effective_workflow == WorkflowStatus.REJECTED:
        return WorkflowStatus.REJECTED
    return None


def _submission_counts_by_document_id(db: Session, document_ids: list[int]) -> dict[int, int]:
    if not document_ids:
        return {}
    rows = (
        db.query(DocumentUploadHistory.document_id, func.count(DocumentUploadHistory.id))
        .filter(DocumentUploadHistory.document_id.in_(document_ids))
        .group_by(DocumentUploadHistory.document_id)
        .all()
    )
    return {int(did): int(cnt) for did, cnt in rows}


def _history_item_dict(
    *,
    inst: DocumentInstance,
    doc: Document | None,
    site: Site,
    req: DocumentRequirement | None,
    dt: DocumentTypeMaster | None,
    uploader: User | None,
    as_of: date,
    submission_count: int,
) -> dict[str, Any]:
    eff = _effective_workflow_status(inst, doc)
    file_name = None
    if doc is not None:
        file_name = doc.file_name or (Path(doc.file_path).name if doc.file_path else None)
    return {
        "instance_id": inst.id,
        "site_id": inst.site_id,
        "site_name": site.site_name or "",
        "document_type_code": inst.document_type_code,
        "document_name": _document_name(inst, req, dt),
        "period_basis": inst.period_basis,
        "period_start": inst.period_start,
        "period_end": inst.period_end,
        "period_label": _period_label(inst),
        "instance_status": inst.status,
        "workflow_status": eff,
        "is_missing": _is_missing(inst=inst, doc=doc, today=as_of),
        "document_id": doc.id if doc is not None else None,
        "current_file_name": file_name,
        "submitted_at": doc.submitted_at if doc is not None else None,
        "reviewed_at": doc.reviewed_at if doc is not None else None,
        "review_note": (doc.rejection_reason if doc is not None else None),
        "review_result": _review_result(eff),
        "submission_count": submission_count,
        "reupload_count": max(submission_count - 1, 0),
        "uploaded_by_name": (uploader.name if uploader is not None else None),
    }


def build_instance_history_query(
    db: Session,
    *,
    site_id: int | None = None,
    site_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    document_type_code: str | None = None,
):
    q = (
        db.query(DocumentInstance, Document, Site, DocumentRequirement, DocumentTypeMaster, User)
        .join(Site, Site.id == DocumentInstance.site_id)
        .outerjoin(Document, Document.instance_id == DocumentInstance.id)
        .outerjoin(DocumentRequirement, DocumentRequirement.id == DocumentInstance.selected_requirement_id)
        .outerjoin(DocumentTypeMaster, DocumentTypeMaster.code == DocumentInstance.document_type_code)
        .outerjoin(User, User.id == Document.uploaded_by_user_id)
    )
    if site_id is not None:
        q = q.filter(DocumentInstance.site_id == site_id)
    if site_code:
        q = q.filter(Site.site_code == site_code)
    if from_date is not None:
        q = q.filter(DocumentInstance.period_start >= from_date)
    if to_date is not None:
        q = q.filter(DocumentInstance.period_start <= to_date)
    if document_type_code:
        q = q.filter(DocumentInstance.document_type_code == document_type_code)
    return q.order_by(
        DocumentInstance.period_start.desc(),
        DocumentInstance.site_id.asc(),
        DocumentInstance.id.desc(),
    )


def list_instance_history_rows(
    db: Session,
    *,
    site_id: int | None = None,
    site_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    document_type_code: str | None = None,
    limit: int = 200,
    offset: int = 0,
    today: date | None = None,
) -> tuple[list[dict[str, Any]], int]:
    as_of = today if today is not None else kst_today()
    base = build_instance_history_query(
        db,
        site_id=site_id,
        site_code=site_code,
        from_date=from_date,
        to_date=to_date,
        document_type_code=document_type_code,
    )
    total = base.count()
    rows = base.offset(offset).limit(limit).all()

    doc_ids = [d.id for _, d, _, _, _, _ in rows if d is not None]
    sub_counts = _submission_counts_by_document_id(db, doc_ids)

    items: list[dict[str, Any]] = []
    for inst, doc, site, req, dt, uploader in rows:
        sc = sub_counts.get(doc.id, 0) if doc is not None else 0
        items.append(
            _history_item_dict(
                inst=inst,
                doc=doc,
                site=site,
                req=req,
                dt=dt,
                uploader=uploader,
                as_of=as_of,
                submission_count=sc,
            )
        )
    return items, total


def get_instance_history_row_by_id(
    db: Session,
    instance_id: int,
    *,
    today: date | None = None,
) -> dict[str, Any] | None:
    as_of = today if today is not None else kst_today()
    row = (
        db.query(DocumentInstance, Document, Site, DocumentRequirement, DocumentTypeMaster, User)
        .join(Site, Site.id == DocumentInstance.site_id)
        .outerjoin(Document, Document.instance_id == DocumentInstance.id)
        .outerjoin(DocumentRequirement, DocumentRequirement.id == DocumentInstance.selected_requirement_id)
        .outerjoin(DocumentTypeMaster, DocumentTypeMaster.code == DocumentInstance.document_type_code)
        .outerjoin(User, User.id == Document.uploaded_by_user_id)
        .filter(DocumentInstance.id == instance_id)
        .first()
    )
    if row is None:
        return None
    inst, doc, site, req, dt, uploader = row
    sc = 0
    if doc is not None:
        sc = _submission_counts_by_document_id(db, [doc.id]).get(doc.id, 0)
    return _history_item_dict(
        inst=inst,
        doc=doc,
        site=site,
        req=req,
        dt=dt,
        uploader=uploader,
        as_of=as_of,
        submission_count=sc,
    )


def summarize_instance_history(
    db: Session,
    *,
    site_id: int | None = None,
    site_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    document_type_code: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    as_of = today if today is not None else kst_today()
    base = build_instance_history_query(
        db,
        site_id=site_id,
        site_code=site_code,
        from_date=from_date,
        to_date=to_date,
        document_type_code=document_type_code,
    )
    rows = base.all()
    total = len(rows)
    approved = under_review = rejected = missing = 0
    for inst, doc, _site, _req, _dt, _uploader in rows:
        eff = _effective_workflow_status(inst, doc)
        if eff == WorkflowStatus.APPROVED:
            approved += 1
        elif eff == WorkflowStatus.UNDER_REVIEW:
            under_review += 1
        elif eff == WorkflowStatus.REJECTED:
            rejected += 1
        if _is_missing(inst=inst, doc=doc, today=as_of):
            missing += 1
    rate = (approved / total * 100.0) if total else 0.0
    return {
        "total_instances": total,
        "approved_count": approved,
        "under_review_count": under_review,
        "rejected_count": rejected,
        "missing_count": missing,
        "completion_rate": round(rate, 4),
    }
