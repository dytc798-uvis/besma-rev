import logging
import re
from datetime import date, datetime, timedelta
import mimetypes
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import utc_now
from app.core.auth import DbDep, get_current_user
from app.core.permissions import CurrentUserDep, Role, assert_hq_safe_workspace
from app.modules.approvals.models import ApprovalAction, ApprovalHistory
from app.modules.document_generation.models import DocumentInstance
from app.modules.document_submissions.service import (
    add_review_history,
    map_action_to_history_type,
    transition_instance_workflow_status,
)
from app.modules.documents.ledger_managed import assert_not_ledger_managed_document, assert_not_ledger_managed_document_type
from app.modules.documents.models import (
    Document,
    DocumentComment,
    DocumentStatus,
    DocumentUploadHistory,
    HQChecklistEntry,
)
from app.modules.document_settings.models import DocumentRequirement
from app.modules.documents.service import (
    create_document_comment,
    delete_document_comment,
    DocumentContentInvalidStateError,
    DocumentContentNotFoundError,
    get_requirement_document_history,
    get_site_requirement_status,
    get_document_content,
    get_tbm_summary,
    get_tbm_periodic_monthly_monitoring,
    get_tbm_periodic_daily_monitoring,
    list_document_comments,
    list_document_comments_with_review,
)
from app.schemas.document_dashboard import HQDashboardResponse, RequirementStatusResponse
from app.modules.sites.models import Site
from app.modules.sites.ordering import site_list_priority_order
from app.modules.users.models import User
from app.schemas.document_content import DocumentContentResponse, TbmSummaryResponse
from app.schemas.periodic_monitoring import TbmDailyMonitoringResponse, TbmMonthlyMonitoringResponse


router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
KST_OFFSET = timedelta(hours=9)


class ReviewActionBody(BaseModel):
    action: str
    comment: str | None = None


class DocumentCommentCreateBody(BaseModel):
    comment_text: str


class DocumentCommentResponse(BaseModel):
    id: int
    document_id: int
    instance_id: int | None = None
    user_id: int
    user_name: str
    user_role: str
    comment_text: str
    created_at: datetime
    source: str = "comment"
    review_action: str | None = None
    file_context_label: str | None = None
    deletable: bool = True


class HQCommunicationItemResponse(BaseModel):
    item_key: str
    source: str
    source_id: int
    document_id: int
    title: str
    site_id: int
    site_name: str
    user_name: str
    user_role: str
    comment_text: str
    created_at: datetime


class HQCommunicationListResponse(BaseModel):
    items: list[HQCommunicationItemResponse]


class SiteCommunicationItemResponse(BaseModel):
    item_key: str
    source: str
    source_id: int
    document_id: int
    title: str
    site_id: int
    site_name: str
    user_name: str
    user_role: str
    comment_text: str
    created_at: datetime


class SiteCommunicationListResponse(BaseModel):
    items: list[SiteCommunicationItemResponse]


class SitePeerCommentItemResponse(BaseModel):
    comment_id: int
    document_id: int
    title: str
    comment_text: str
    created_at: datetime
    author_name: str


class SitePeerCommentListResponse(BaseModel):
    items: list[SitePeerCommentItemResponse]


class HQChecklistCatalogItem(BaseModel):
    checklist_code: str
    title: str
    frequency: str


class HQChecklistItemResponse(BaseModel):
    checklist_code: str
    title: str
    frequency: str
    period_label: str
    status: str
    file_name: str | None = None
    uploaded_at: datetime | None = None
    checked_at: datetime | None = None
    improvement_note: str | None = None
    entry_id: int | None = None


class HQChecklistListResponse(BaseModel):
    date: date
    items: list[HQChecklistItemResponse]
    catalog: list[HQChecklistCatalogItem]


class HQChecklistStatusUpdateBody(BaseModel):
    action: str
    note: str | None = None


HQ_CHECKLIST_CATALOG: list[dict[str, str]] = [
    {"checklist_code": "HQ_SAFETY_ROOM_WEEKLY", "title": "(주1회)안전실점검표", "frequency": "WEEKLY"},
    {"checklist_code": "HQ_EXEC_PM_MONTHLY_2X", "title": "(월2회)안전임원/PM 점검표", "frequency": "MONTHLY_2X"},
    {"checklist_code": "HQ_SAFETY_DIRECTOR_MONTHLY", "title": "(월1회)안전보건실장 점검표", "frequency": "MONTHLY"},
    {"checklist_code": "HQ_CEO_MONTHLY", "title": "(월1회)대표이사점검표", "frequency": "MONTHLY"},
]


def _hq_checklist_period_label(freq: str, target: date) -> str:
    if freq == "WEEKLY":
        iso = target.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if freq == "MONTHLY_2X":
        half = 1 if target.day <= 15 else 2
        return f"{target.year:04d}-{target.month:02d}-H{half}"
    return f"{target.year:04d}-{target.month:02d}"


def _hq_checklist_allowed_for_read(current_user) -> bool:
    return current_user.role in {
        Role.SITE,
        Role.HQ_SAFE,
        Role.HQ_SAFE_ADMIN,
        Role.SUPER_ADMIN,
        Role.HQ_OTHER,
    }


def _hq_checklist_allowed_for_write(current_user) -> bool:
    return current_user.role in {Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN}


def _parse_period(period: str) -> str:
    value = (period or "").strip().lower()
    if value not in {"all", "day", "week", "month", "quarter", "half_year", "year", "event"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="period must be one of: all, day, week, month, quarter, half_year, year, event",
        )
    return value


def _to_kst_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value + KST_OFFSET


def _build_pending_documents_summary(rows: list[Document], reference_date: date) -> dict[str, int]:
    ref_dt = datetime.combine(reference_date, datetime.min.time())
    week_start = ref_dt - timedelta(days=6)
    month_start = ref_dt - timedelta(days=29)
    day_count = 0
    week_count = 0
    month_count = 0
    for doc in rows:
        base_dt = _to_kst_datetime(doc.submitted_at or doc.uploaded_at)
        if base_dt is None:
            continue
        if base_dt.date() == reference_date:
            day_count += 1
        if base_dt >= week_start:
            week_count += 1
        if base_dt >= month_start:
            month_count += 1
    return {"day": day_count, "week": week_count, "month": month_count}


def _parse_year_month(year_month: str) -> tuple[int, int, date, date, str]:
    value = (year_month or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})$", value)
    if not m:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="year_month must be in format YYYY-MM",
        )
    y = int(m.group(1))
    month = int(m.group(2))
    if month < 1 or month > 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month must be between 01 and 12",
        )
    start = date(y, month, 1)
    if month == 12:
        end = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(y, month + 1, 1) - timedelta(days=1)
    return y, month, start, end, f"{y:04d}-{month:02d}"


def _site_team_slot(site_name: str) -> str | None:
    m = re.match(r"^\[([1-6])\.", (site_name or "").strip())
    if m:
        return m.group(1)
    if "관급" in (site_name or ""):
        return "gwal"
    return None


def _site_cluster_key(site_name: str | None) -> str:
    name = (site_name or "").strip()
    # 운영 표기(prefix) 차이로 같은 현장이 중복 생성되는 경우를 한 군으로 본다.
    name = re.sub(r"\(삼성인정제\)", "", name)
    name = re.sub(r"\s+", "", name)
    return name.lower()


def _dedupe_sites_by_uploaded_documents(db: Session, sites: list[Site]) -> list[Site]:
    if len(sites) <= 1:
        return sites

    site_ids = [s.id for s in sites]
    uploaded_ids = {
        int(site_id)
        for (site_id,) in (
            db.query(Document.site_id)
            .filter(Document.site_id.in_(site_ids), Document.file_path.isnot(None))
            .group_by(Document.site_id)
            .all()
        )
        if site_id is not None
    }

    grouped: dict[str, list[Site]] = {}
    ordered_keys: list[str] = []
    for site in sites:
        key = (site.site_name or "").strip()
        if key not in grouped:
            grouped[key] = []
            ordered_keys.append(key)
        grouped[key].append(site)

    chosen: list[Site] = []
    for key in ordered_keys:
        rows = grouped[key]
        chosen.append(
            sorted(
                rows,
                key=lambda s: (
                    0 if s.id in uploaded_ids else 1,
                    0 if (s.address or "").strip() else 1,
                    0 if s.site_code == "SITE002" else 1,
                    s.id,
                ),
            )[0]
        )
    return chosen


def _compute_summary(items: list[dict]) -> dict[str, int]:
    summary = {
        "total_required": 0,
        "submitted_count": 0,
        "submitted_pending_count": 0,
        "approved_count": 0,
        "in_review_count": 0,
        "rejected_count": 0,
        "not_submitted_count": 0,
    }
    for item in items:
        if not item.get("is_required", True):
            continue
        summary["total_required"] += 1
        status_value = item.get("status")
        if status_value == "APPROVED":
            summary["approved_count"] += 1
            summary["submitted_count"] += 1
        elif status_value in {"SUBMITTED", "IN_REVIEW", "REJECTED"}:
            summary["submitted_count"] += 1
            if status_value == "SUBMITTED":
                summary["submitted_pending_count"] += 1
            elif status_value == "IN_REVIEW":
                summary["in_review_count"] += 1
            elif status_value == "REJECTED":
                summary["rejected_count"] += 1
        elif status_value == "NOT_SUBMITTED":
            summary["not_submitted_count"] += 1
    return summary


def _compute_completion_window(site: Site, target_date: date) -> tuple[bool, date | None, date | None]:
    if site.end_date is None:
        return False, None, None
    window_end = site.end_date
    window_start = window_end - timedelta(days=183)
    enabled = window_start <= target_date <= window_end
    return enabled, window_start, window_end


def _compute_signal_status(*, not_submitted_count: int, rejected_count: int, pending_review_count: int) -> str:
    if rejected_count > 0:
        return "RED"
    if not_submitted_count > 0 or pending_review_count > 0:
        return "YELLOW"
    return "GREEN"


def _ensure_storage_dir() -> Path:
    documents_dir = settings.storage_root / settings.documents_dir_name
    documents_dir.mkdir(parents=True, exist_ok=True)
    return documents_dir


def _get_document_or_404(db: Session, *, document_id: int) -> Document:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def _assert_document_access(doc: Document, current_user) -> None:
    if current_user.role == Role.SITE and doc.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def _public_user_role(current_user) -> str:
    return "SITE" if current_user.role == Role.SITE else "HQ"


@router.get("")
def list_documents(
    db: DbDep,
    current_user: CurrentUserDep,
    status_filter: str | None = None,
    site_id: int | None = None,
    document_type: str | None = None,
    work_date: date | None = None,
):
    query = db.query(Document)

    if current_user.role == Role.SITE:
        if current_user.site_id:
            query = query.filter(Document.site_id == current_user.site_id)
        else:
            query = query.filter(False)
    elif current_user.role == Role.HQ_OTHER and current_user.site_id:
        query = query.filter(Document.site_id == current_user.site_id)

    if status_filter:
        query = query.filter(Document.current_status == status_filter)
    if site_id:
        query = query.filter(Document.site_id == site_id)
    if document_type:
        query = query.filter(Document.document_type == document_type)
    if work_date:
        query = query.filter(Document.period_start == work_date)

    return query.order_by(Document.created_at.desc()).all()


@router.get("/requirements/status", response_model=RequirementStatusResponse)
def get_requirement_status(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int,
    period: str = "day",
    date_value: date = Query(..., alias="date"),
):
    parsed_period = _parse_period(period)
    if current_user.role == Role.SITE and current_user.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    completion_upload_enabled, completion_window_start, completion_window_end = _compute_completion_window(
        site,
        date_value,
    )

    items = get_site_requirement_status(
        db,
        site_id=site_id,
        period=parsed_period,
        target_date=date_value,
        completion_upload_enabled=completion_upload_enabled,
    )
    summary = _compute_summary(items)
    return {
        "site_id": site_id,
        "period": parsed_period,
        "date": date_value,
        "summary": summary,
        "completion_upload_enabled": completion_upload_enabled,
        "completion_window_start": completion_window_start,
        "completion_window_end": completion_window_end,
        "items": items,
    }


@router.get("/hq-dashboard", response_model=HQDashboardResponse)
def get_hq_dashboard(
    db: DbDep,
    current_user: CurrentUserDep,
    period: str = "day",
    date_value: date = Query(..., alias="date"),
    site_id: int | None = None,
    team_slot: str | None = Query(None, pattern="^(1|2|3|4|5|6|gwal)$"),
    site_code: str | None = None,
):
    assert_hq_safe_workspace(current_user)

    parsed_period = _parse_period(period)
    # 단일 현장(scope) 요청일 때는 전체 현장 목록을 먼저 읽지 않도록 쿼리를 분기한다.
    if site_id is not None:
        sites = (
            db.query(Site)
            .filter(Site.id == int(site_id))
            .order_by(site_list_priority_order(), Site.id.asc())
            .all()
        )
    elif site_code:
        anchor = db.query(Site).filter(Site.site_code == site_code).first()
        if anchor is None:
            sites = []
        else:
            cluster_key = _site_cluster_key(anchor.site_name)
            if cluster_key:
                candidates = db.query(Site).order_by(site_list_priority_order(), Site.id.asc()).all()
                related_sites = [s for s in candidates if _site_cluster_key(s.site_name) == cluster_key]
            else:
                related_sites = [anchor]
            sites = _dedupe_sites_by_uploaded_documents(db, related_sites or [anchor])
    else:
        sites = db.query(Site).order_by(site_list_priority_order(), Site.id.asc()).all()
        sites = _dedupe_sites_by_uploaded_documents(db, sites)

    if team_slot:
        sites = [s for s in sites if _site_team_slot(s.site_name) == team_slot]
    site_summaries: list[dict] = []
    all_items: list[dict] = []
    pending_review_count = 0
    rejected_count = 0
    not_submitted_count = 0
    approved_count = 0
    for site in sites:
        completion_upload_enabled, _, _ = _compute_completion_window(site, date_value)
        items = get_site_requirement_status(
            db,
            site_id=site.id,
            period=parsed_period,
            target_date=date_value,
            completion_upload_enabled=completion_upload_enabled,
        )
        summary = _compute_summary(items)
        rate = 0.0
        if summary["total_required"] > 0:
            rate = round((summary["submitted_count"] / summary["total_required"]) * 100, 1)
        site_summaries.append(
            {
                "site_id": site.id,
                "site_name": site.site_name,
                "total_required": summary["total_required"],
                "submitted_count": summary["submitted_count"],
                "approved_count": summary["approved_count"],
                "in_review_count": summary["in_review_count"],
                "submitted_pending_count": summary["submitted_pending_count"],
                "rejected_count": summary["rejected_count"],
                "not_submitted_count": summary["not_submitted_count"],
                "incomplete_count": summary["not_submitted_count"] + summary["submitted_pending_count"] + summary["in_review_count"] + summary["rejected_count"],
                "submission_rate": rate,
            }
        )
        pending_review_count += summary["submitted_pending_count"] + summary["in_review_count"]
        rejected_count += summary["rejected_count"]
        not_submitted_count += summary["not_submitted_count"]
        approved_count += summary["approved_count"]
        for item in items:
            all_items.append(
                {
                    **item,
                    "site_id": site.id,
                    "site_name": site.site_name,
                }
            )
    uploader_ids = {row.get("uploaded_by_user_id") for row in all_items if row.get("uploaded_by_user_id")}
    uploader_name_map: dict[int, str] = {}
    if uploader_ids:
        users = db.query(User).filter(User.id.in_(list(uploader_ids))).all()
        uploader_name_map = {u.id: u.name for u in users}
    for row in all_items:
        uid = row.get("uploaded_by_user_id")
        row["uploaded_by_name"] = uploader_name_map.get(uid) if uid else None

    site_ids = [s.id for s in sites]

    pending_docs_query = (
        db.query(Document, Site)
        .join(Site, Site.id == Document.site_id)
        .filter(
            Document.site_id.in_(site_ids),
            Document.current_status.in_([DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW]),
        )
        .order_by(Document.uploaded_at.desc().nullslast(), Document.id.desc())
    )
    pending_docs_all = [row[0] for row in pending_docs_query.all()]
    pending_documents = [
        {
            "document_id": d.id,
            "instance_id": d.instance_id,
            "document_no": d.document_no,
            "title": d.title,
            "file_name": d.file_name,
            "site_id": d.site_id,
            "site_name": s.site_name,
            "status": d.current_status,
            "submitted_at": d.submitted_at,
            "uploaded_at": d.uploaded_at,
            "review_note": d.rejection_reason,
            "file_url": f"/documents/{d.id}/file",
        }
        for d, s in pending_docs_query.limit(20).all()
    ]
    pending_documents_summary = _build_pending_documents_summary(pending_docs_all, date_value)

    logger.info(
        "hq-dashboard aggregated: period=%s date=%s site_filter=%s pending_action_count=%s pending_docs=%s pending_instance_ids=%s rejected=%s not_submitted=%s approved=%s",
        parsed_period,
        date_value,
        site_id,
        pending_review_count,
        len(pending_documents),
        [row.get("instance_id") for row in pending_documents[:20]],
        rejected_count,
        not_submitted_count,
        approved_count,
    )

    history_query = (
        db.query(Document, Site, User)
        .join(Site, Site.id == Document.site_id)
        .outerjoin(User, User.id == Document.uploaded_by_user_id)
        .filter(
            Document.site_id.in_(site_ids),
            Document.current_status.in_([DocumentStatus.APPROVED, DocumentStatus.REJECTED]),
        )
        .order_by(Document.reviewed_at.desc().nullslast(), Document.id.desc())
    )
    approval_history = [
        {
            "document_id": d.id,
            "document_no": d.document_no,
            "title": d.title,
            "site_id": d.site_id,
            "site_name": s.site_name,
            "status": d.current_status,
            "reviewed_at": d.reviewed_at,
            "review_note": d.rejection_reason,
            "uploaded_by_name": (u.name if u else None),
        }
        for d, s, u in history_query.limit(30).all()
    ]

    return {
        "period": parsed_period,
        "date": date_value,
        "total_sites": len(sites),
        "pending_review_count": pending_review_count,
        "rejected_count": rejected_count,
        "not_submitted_count": not_submitted_count,
        "approved_count": approved_count,
        "site_summaries": site_summaries,
        "items": all_items,
        "signal_status": _compute_signal_status(
            not_submitted_count=not_submitted_count,
            rejected_count=rejected_count,
            pending_review_count=pending_review_count,
        ),
        "pending_documents": pending_documents,
        "pending_documents_summary": pending_documents_summary,
        "approval_history": approval_history,
    }


@router.get(
    "/periodic-monitoring/tbm/monthly",
    response_model=TbmMonthlyMonitoringResponse,
)
def get_tbm_periodic_monthly(
    db: DbDep,
    current_user: CurrentUserDep,
    year_month: str = Query(..., description="YYYY-MM"),
    site_id: int | None = None,
):
    assert_hq_safe_workspace(current_user)

    y, m, start, end, ym_label = _parse_year_month(year_month)

    sites = db.query(Site).order_by(site_list_priority_order(), Site.id.asc()).all()
    if site_id is not None:
        sites = [s for s in sites if s.id == site_id]

    site_ids = [s.id for s in sites]
    site_summaries = get_tbm_periodic_monthly_monitoring(
        db,
        site_ids=site_ids,
        start_date=start,
        end_date=end,
    )

    return {
        "year": y,
        "month": m,
        "year_month": ym_label,
        "start_date": start,
        "end_date": end,
        "sites": site_summaries,
    }


@router.get(
    "/periodic-monitoring/tbm/daily",
    response_model=TbmDailyMonitoringResponse,
)
def get_tbm_periodic_daily(
    db: DbDep,
    current_user: CurrentUserDep,
    year_month: str = Query(..., description="YYYY-MM"),
    site_id: int = Query(..., description="Site id"),
):
    assert_hq_safe_workspace(current_user)

    y, m, start, end, ym_label = _parse_year_month(year_month)

    try:
        payload = get_tbm_periodic_daily_monitoring(
            db,
            site_id=site_id,
            start_date=start,
            end_date=end,
        )
    except ValueError as exc:
        if str(exc) == "site_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        raise

    return {
        "site_id": payload["site_id"],
        "site_name": payload["site_name"],
        "year": y,
        "month": m,
        "year_month": ym_label,
        "start_date": start,
        "end_date": end,
        "summary": payload["summary"],
        "days": payload["days"],
    }


@router.get("/hq-pending")
def get_hq_pending_documents(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = None,
    site_code: str | None = None,
):
    assert_hq_safe_workspace(current_user)

    query = (
        db.query(Document, Site, DocumentInstance, DocumentRequirement, User)
        .join(Site, Site.id == Document.site_id)
        .outerjoin(DocumentInstance, Document.instance_id == DocumentInstance.id)
        .outerjoin(DocumentRequirement, DocumentRequirement.id == DocumentInstance.selected_requirement_id)
        .outerjoin(User, User.id == Document.uploaded_by_user_id)
        .filter(
            Document.current_status.in_([DocumentStatus.SUBMITTED, DocumentStatus.UNDER_REVIEW]),
        )
    )
    if site_id is not None:
        query = query.filter(Document.site_id == site_id)
    if site_code and site_id is None:
        sc_site = db.query(Site).filter(Site.site_code == site_code).first()
        if sc_site is None:
            return {"items": []}
        query = query.filter(Document.site_id == sc_site.id)

    rows = query.order_by(Document.uploaded_at.desc().nullslast(), Document.id.desc()).all()
    items = []
    for doc, site, inst, req, uploaded_by in rows:
        requirement_name = req.title if req else doc.title
        items.append(
            {
                "site_name": site.site_name,
                "site_id": site.id,
                "document_type_code": doc.document_type,
                "requirement_name": requirement_name,
                "requirement_id": (req.id if req else None),
                "document_id": doc.id,
                "document_no": doc.document_no,
                "file_name": doc.file_name,
                "workflow_status": (inst.workflow_status if inst else None),
                "status": doc.current_status,
                "submitted_at": doc.submitted_at,
                "uploaded_at": doc.uploaded_at,
                "submitted_by": (uploaded_by.name if uploaded_by else None),
                "submitted_by_user_id": doc.uploaded_by_user_id,
                "review_key": {
                    "site_id": site.id,
                    "requirement_id": (req.id if req else None),
                },
                "file_url": f"/documents/{doc.id}/file",
            }
        )
    return {"count": len(items), "items": items}


@router.get("/history")
def get_document_history_by_requirement(
    db: DbDep,
    current_user: CurrentUserDep,
    requirement_id: int,
    site_id: int,
):
    if current_user.role == Role.SITE and current_user.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    req = (
        db.query(DocumentRequirement)
        .filter(DocumentRequirement.id == requirement_id, DocumentRequirement.site_id == site_id)
        .first()
    )
    if req is not None:
        assert_not_ledger_managed_document_type(req.code)
    rows = get_requirement_document_history(
        db,
        site_id=site_id,
        requirement_id=requirement_id,
    )
    return {"site_id": site_id, "requirement_id": requirement_id, "items": rows}


@router.get("/history/{history_id}/file")
def download_document_history_file(
    history_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    disposition: str = Query("attachment"),
):
    history = (
        db.query(DocumentUploadHistory, Document)
        .join(Document, Document.id == DocumentUploadHistory.document_id)
        .filter(DocumentUploadHistory.id == history_id)
        .first()
    )
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History file not found")

    upload_history, doc = history
    if not upload_history.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History file not found")
    if current_user.role == Role.SITE and doc.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    assert_not_ledger_managed_document(doc)

    file_path = settings.storage_root / upload_history.file_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History file not found")

    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")

    fallback_name = upload_history.file_name or file_path.name
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(
        path=file_path,
        media_type=media_type,
        filename=fallback_name,
    )
    response.headers["Content-Disposition"] = (
        f"{resolved_disposition}; filename*=UTF-8''{quote(fallback_name)}"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/badges/site")
def get_site_badge_counts(
    db: DbDep,
    current_user: CurrentUserDep,
    date_value: date = Query(..., alias="date"),
):
    if current_user.role != Role.SITE or not current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    items = get_site_requirement_status(
        db,
        site_id=current_user.site_id,
        period="day",
        target_date=date_value,
    )
    summary = _compute_summary(items)
    return {
        "site_id": current_user.site_id,
        "date": date_value,
        "incomplete_count": summary["not_submitted_count"] + summary["submitted_pending_count"] + summary["in_review_count"] + summary["rejected_count"],
        "rejected_count": summary["rejected_count"],
    }


@router.get("/comments/peer-count")
def get_peer_document_comment_count(
    db: DbDep,
    current_user: CurrentUserDep,
    after: datetime | None = Query(
        None,
        description="이 시각 이후에 등록된 타인 코멘트만 집계. 생략 시 최근 14일로 제한.",
    ),
):
    """현장 계정: 소속 현장 문서에 달린 다른 사용자 코멘트 수(SITE 티커용)."""
    if current_user.role != Role.SITE or not current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    cutoff = after
    if cutoff is None:
        cutoff = utc_now() - timedelta(days=14)
    n = (
        db.query(func.count(DocumentComment.id))
        .join(Document, Document.id == DocumentComment.document_id)
        .filter(
            Document.site_id == int(current_user.site_id),
            DocumentComment.user_id != int(current_user.id),
            DocumentComment.created_at > cutoff,
        )
        .scalar()
    )
    return {"peer_comment_count": int(n or 0)}


@router.get("/comments/peer-items", response_model=SitePeerCommentListResponse)
def get_peer_document_comment_items(
    db: DbDep,
    current_user: CurrentUserDep,
    after: datetime | None = Query(
        None,
        description="이 시각 이후에 등록된 타인 코멘트만 조회. 생략 시 최근 14일로 제한.",
    ),
    limit: int = Query(20, ge=1, le=200),
):
    """현장 계정: 소속 현장 문서에 달린 다른 사용자 코멘트 목록(티커 상세 안내용)."""
    if current_user.role != Role.SITE or not current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    cutoff = after
    if cutoff is None:
        cutoff = utc_now() - timedelta(days=14)

    rows = (
        db.query(DocumentComment, Document, User)
        .join(Document, Document.id == DocumentComment.document_id)
        .join(User, User.id == DocumentComment.user_id)
        .filter(
            Document.site_id == int(current_user.site_id),
            DocumentComment.user_id != int(current_user.id),
            DocumentComment.created_at > cutoff,
        )
        .order_by(DocumentComment.created_at.desc(), DocumentComment.id.desc())
        .limit(limit)
        .all()
    )
    items = [
        {
            "comment_id": int(c.id),
            "document_id": int(d.id),
            "title": d.title,
            "comment_text": c.comment_text,
            "created_at": c.created_at,
            "author_name": u.name,
        }
        for c, d, u in rows
    ]
    return {"items": items}


@router.get("/hq-checklists", response_model=HQChecklistListResponse)
def get_hq_checklists(
    db: DbDep,
    current_user: CurrentUserDep,
    date_value: date = Query(..., alias="date"),
):
    if not _hq_checklist_allowed_for_read(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    items: list[dict] = []
    for row in HQ_CHECKLIST_CATALOG:
        code = row["checklist_code"]
        title = row["title"]
        freq = row["frequency"]
        period_label = _hq_checklist_period_label(freq, date_value)
        entry = (
            db.query(HQChecklistEntry)
            .filter(
                HQChecklistEntry.checklist_code == code,
                HQChecklistEntry.period_label == period_label,
            )
            .order_by(HQChecklistEntry.updated_at.desc(), HQChecklistEntry.id.desc())
            .first()
        )
        if entry is None:
            items.append(
                {
                    "checklist_code": code,
                    "title": title,
                    "frequency": freq,
                    "period_label": period_label,
                    "status": "PENDING_CONFIRM",
                    "file_name": None,
                    "uploaded_at": None,
                    "checked_at": None,
                    "improvement_note": None,
                    "entry_id": None,
                }
            )
            continue
        items.append(
            {
                "checklist_code": code,
                "title": title,
                "frequency": freq,
                "period_label": period_label,
                "status": entry.status,
                "file_name": entry.file_name,
                "uploaded_at": entry.created_at,
                "checked_at": entry.checked_at,
                "improvement_note": entry.improvement_note,
                "entry_id": entry.id,
            }
        )

    return {
        "date": date_value,
        "items": items,
        "catalog": HQ_CHECKLIST_CATALOG,
    }


@router.post("/hq-checklists/upload")
async def upload_hq_checklist(
    db: DbDep,
    current_user: CurrentUserDep,
    checklist_code: Annotated[str, Form(...)],
    work_date: Annotated[date, Form(...)],
    file: Annotated[UploadFile, File(...)],
):
    if not _hq_checklist_allowed_for_write(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    catalog = next((c for c in HQ_CHECKLIST_CATALOG if c["checklist_code"] == checklist_code), None)
    if catalog is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown checklist_code")

    content = await file.read()
    source_name = file.filename or "upload.bin"
    ext = Path(source_name).suffix or ".bin"
    if len(content) > settings.document_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"파일 크기는 {settings.document_upload_max_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
        )
    storage_dir = _ensure_storage_dir()
    ts = int(utc_now().timestamp())
    safe_name = f"{catalog['title'].replace(' ', '')}_{work_date.strftime('%Y%m%d')}{ext or Path(source_name).suffix or '.bin'}"
    filename = f"hqcheck_{checklist_code}_{ts}_{safe_name}"
    stored_path = storage_dir / filename
    stored_path.write_bytes(content)

    period_label = _hq_checklist_period_label(catalog["frequency"], work_date)
    entry = (
        db.query(HQChecklistEntry)
        .filter(
            HQChecklistEntry.checklist_code == checklist_code,
            HQChecklistEntry.period_label == period_label,
        )
        .order_by(HQChecklistEntry.updated_at.desc(), HQChecklistEntry.id.desc())
        .first()
    )
    if entry is None:
        entry = HQChecklistEntry(
            checklist_code=checklist_code,
            checklist_title=catalog["title"],
            frequency=catalog["frequency"],
            period_label=period_label,
            target_date=work_date,
            status="PENDING_CONFIRM",
        )
        db.add(entry)
    entry.checklist_title = catalog["title"]
    entry.frequency = catalog["frequency"]
    entry.target_date = work_date
    entry.file_path = str(stored_path.relative_to(settings.storage_root))
    entry.file_name = safe_name
    entry.file_size = len(content)
    entry.uploaded_by_user_id = current_user.id
    entry.checked_by_user_id = None
    entry.checked_at = None
    entry.improvement_note = None
    entry.status = "PENDING_CONFIRM"

    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"entry_id": entry.id, "status": entry.status}


@router.post("/hq-checklists/{entry_id}/status")
def update_hq_checklist_status(
    entry_id: int,
    body: HQChecklistStatusUpdateBody,
    db: DbDep,
    current_user: CurrentUserDep,
):
    if not _hq_checklist_allowed_for_write(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    entry = db.query(HQChecklistEntry).filter(HQChecklistEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist entry not found")

    action = (body.action or "").strip().lower()
    if action == "confirm":
        entry.status = "CONFIRMED"
        entry.improvement_note = (body.note or "").strip() or None
    elif action == "improve":
        note = (body.note or "").strip()
        if not note:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="improve action requires note")
        entry.status = "IMPROVEMENT_REQUIRED"
        entry.improvement_note = note
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action must be confirm or improve")

    entry.checked_by_user_id = current_user.id
    entry.checked_at = utc_now()
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"entry_id": entry.id, "status": entry.status}


@router.get("/hq-checklists/{entry_id}/file")
def download_hq_checklist_file(
    entry_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    disposition: str = Query("attachment"),
):
    if not _hq_checklist_allowed_for_read(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    entry = db.query(HQChecklistEntry).filter(HQChecklistEntry.id == entry_id).first()
    if entry is None or not entry.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    file_path = settings.storage_root / entry.file_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")
    fallback_name = entry.file_name or file_path.name
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(path=file_path, media_type=media_type, filename=fallback_name)
    response.headers["Content-Disposition"] = f"{resolved_disposition}; filename*=UTF-8''{quote(fallback_name)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/badges/hq")
def get_hq_badge_counts(
    db: DbDep,
    current_user: CurrentUserDep,
    date_value: date = Query(..., alias="date"),
):
    assert_hq_safe_workspace(current_user)
    sites = db.query(Site).order_by(site_list_priority_order(), Site.id.asc()).all()
    pending = 0
    rejected = 0
    not_submitted = 0
    for site in sites:
        items = get_site_requirement_status(db, site_id=site.id, period="day", target_date=date_value)
        summary = _compute_summary(items)
        pending += summary["submitted_pending_count"] + summary["in_review_count"]
        rejected += summary["rejected_count"]
        not_submitted += summary["not_submitted_count"]
    return {
        "date": date_value,
        "pending_review_count": pending,
        "rejected_count": rejected,
        "not_submitted_count": not_submitted,
        "incomplete_count": pending + rejected + not_submitted,
    }


@router.get("/hq-communications", response_model=HQCommunicationListResponse)
def get_hq_communications(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(100, ge=1, le=500),
):
    assert_hq_safe_workspace(current_user)

    entries: list[dict] = []

    my_id = int(current_user.id)
    comment_rows = (
        db.query(DocumentComment, Document, Site, User)
        .join(Document, Document.id == DocumentComment.document_id)
        .join(Site, Site.id == Document.site_id)
        .join(User, User.id == DocumentComment.user_id)
        .filter(
            DocumentComment.user_id != my_id,
            User.role == Role.SITE,
        )
        .order_by(DocumentComment.created_at.desc(), DocumentComment.id.desc())
        .limit(limit)
        .all()
    )
    for c, d, s, u in comment_rows:
        entries.append(
            {
                "item_key": f"comment:{c.id}",
                "source": "comment",
                "source_id": int(c.id),
                "document_id": int(d.id),
                "title": d.title,
                "site_id": int(s.id),
                "site_name": s.site_name,
                "user_name": u.name,
                "user_role": ("SITE" if u.role == Role.SITE else "HQ"),
                "comment_text": c.comment_text,
                "created_at": c.created_at,
            }
        )

    approval_rows = (
        db.query(ApprovalHistory, Document, Site, User)
        .join(Document, Document.id == ApprovalHistory.document_id)
        .join(Site, Site.id == Document.site_id)
        .join(User, User.id == ApprovalHistory.action_by_user_id)
        .filter(
            ApprovalHistory.action_type.in_([ApprovalAction.APPROVE, ApprovalAction.REJECT]),
            ApprovalHistory.comment.isnot(None),
            ApprovalHistory.comment != "",
            ApprovalHistory.action_by_user_id != my_id,
            User.role == Role.SITE,
        )
        .order_by(ApprovalHistory.action_at.desc(), ApprovalHistory.id.desc())
        .limit(limit)
        .all()
    )
    for h, d, s, u in approval_rows:
        action_label = "승인" if h.action_type == ApprovalAction.APPROVE else "반려"
        entries.append(
            {
                "item_key": f"approval:{h.id}",
                "source": "approval",
                "source_id": int(h.id),
                "document_id": int(d.id),
                "title": d.title,
                "site_id": int(s.id),
                "site_name": s.site_name,
                "user_name": u.name,
                "user_role": ("SITE" if u.role == Role.SITE else "HQ"),
                "comment_text": f"[{action_label}] {h.comment}",
                "created_at": h.action_at,
            }
        )

    entries.sort(key=lambda row: row["created_at"], reverse=True)
    return {"items": entries[:limit]}


@router.get("/site-communications", response_model=SiteCommunicationListResponse)
def get_site_communications(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(80, ge=1, le=300),
):
    if current_user.role != Role.SITE or not current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    site_id = int(current_user.site_id)
    entries: list[dict] = []

    # 본사 작성 코멘트만 SITE에 노출
    comment_rows = (
        db.query(DocumentComment, Document, Site, User)
        .join(Document, Document.id == DocumentComment.document_id)
        .join(Site, Site.id == Document.site_id)
        .join(User, User.id == DocumentComment.user_id)
        .filter(
            Document.site_id == site_id,
            User.role.in_([Role.HQ_SAFE, Role.HQ_OTHER, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN]),
        )
        .order_by(DocumentComment.created_at.desc(), DocumentComment.id.desc())
        .limit(limit)
        .all()
    )
    for c, d, s, u in comment_rows:
        entries.append(
            {
                "item_key": f"comment:{c.id}",
                "source": "comment",
                "source_id": int(c.id),
                "document_id": int(d.id),
                "title": d.title,
                "site_id": int(s.id),
                "site_name": s.site_name,
                "user_name": u.name,
                "user_role": "HQ",
                "comment_text": c.comment_text,
                "created_at": c.created_at,
            }
        )

    # 본사 승인/반려 코멘트도 SITE에서 확인
    approval_rows = (
        db.query(ApprovalHistory, Document, Site, User)
        .join(Document, Document.id == ApprovalHistory.document_id)
        .join(Site, Site.id == Document.site_id)
        .join(User, User.id == ApprovalHistory.action_by_user_id)
        .filter(
            Document.site_id == site_id,
            ApprovalHistory.action_type.in_([ApprovalAction.APPROVE, ApprovalAction.REJECT]),
            ApprovalHistory.comment.isnot(None),
            ApprovalHistory.comment != "",
            User.role.in_([Role.HQ_SAFE, Role.HQ_OTHER, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN]),
        )
        .order_by(ApprovalHistory.action_at.desc(), ApprovalHistory.id.desc())
        .limit(limit)
        .all()
    )
    for h, d, s, u in approval_rows:
        action_label = "승인" if h.action_type == ApprovalAction.APPROVE else "반려"
        entries.append(
            {
                "item_key": f"approval:{h.id}",
                "source": "approval",
                "source_id": int(h.id),
                "document_id": int(d.id),
                "title": d.title,
                "site_id": int(s.id),
                "site_name": s.site_name,
                "user_name": u.name,
                "user_role": "HQ",
                "comment_text": f"[{action_label}] {h.comment}",
                "created_at": h.action_at,
            }
        )

    entries.sort(key=lambda row: row["created_at"], reverse=True)
    return {"items": entries[:limit]}


@router.get("/{document_id}")
def get_document(document_id: int, db: DbDep, current_user: CurrentUserDep):
    doc = _get_document_or_404(db, document_id=document_id)
    _assert_document_access(doc, current_user)
    requirement_code: str | None = None
    if doc.instance_id:
        req = (
            db.query(DocumentRequirement.code)
            .join(DocumentInstance, DocumentInstance.selected_requirement_id == DocumentRequirement.id)
            .filter(DocumentInstance.id == doc.instance_id)
            .first()
        )
        if req and req[0]:
            requirement_code = str(req[0]).strip() or None

    payload = {k: v for k, v in vars(doc).items() if not k.startswith("_")}
    payload["document_type_code"] = requirement_code
    return payload


@router.get("/{document_id}/comments", response_model=list[DocumentCommentResponse])
def get_document_comments(document_id: int, db: DbDep, current_user: CurrentUserDep):
    doc = _get_document_or_404(db, document_id=document_id)
    _assert_document_access(doc, current_user)
    assert_not_ledger_managed_document(doc)
    rows = list_document_comments_with_review(db, document_id=document_id)
    return [DocumentCommentResponse(**row) for row in rows]


@router.post("/{document_id}/comments", response_model=DocumentCommentResponse, status_code=status.HTTP_201_CREATED)
def add_document_comment(
    document_id: int,
    body: DocumentCommentCreateBody,
    db: DbDep,
    current_user: CurrentUserDep,
):
    doc = _get_document_or_404(db, document_id=document_id)
    _assert_document_access(doc, current_user)
    assert_not_ledger_managed_document(doc)
    try:
        row = create_document_comment(
            db,
            document=doc,
            user_id=current_user.id,
            user_role=_public_user_role(current_user),
            comment_text=body.comment_text,
        )
    except ValueError as exc:
        if str(exc) == "comment_text_required":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="comment_text is required")
        raise
    return DocumentCommentResponse(**row)


@router.delete("/{document_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document_comment(document_id: int, comment_id: int, db: DbDep, current_user: CurrentUserDep):
    doc = _get_document_or_404(db, document_id=document_id)
    _assert_document_access(doc, current_user)
    assert_not_ledger_managed_document(doc)
    try:
        delete_document_comment(
            db,
            document_id=document_id,
            comment_id=comment_id,
            acting_user=current_user,
        )
    except ValueError as exc:
        if str(exc) == "comment_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        if str(exc) == "comment_delete_forbidden":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this comment")
        raise


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
def get_document_content_view(document_id: int, db: DbDep, current_user: CurrentUserDep):
    doc = _get_document_or_404(db, document_id=document_id)
    _assert_document_access(doc, current_user)

    try:
        payload = get_document_content(db, document_id=document_id)
    except DocumentContentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except DocumentContentInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    return DocumentContentResponse(**payload)


@router.get("/{document_id}/tbm-summary", response_model=TbmSummaryResponse)
def get_document_tbm_summary_view(document_id: int, db: DbDep, current_user: CurrentUserDep):
    doc = _get_document_or_404(db, document_id=document_id)
    _assert_document_access(doc, current_user)

    try:
        payload = get_tbm_summary(db, document_id=document_id)
    except DocumentContentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except DocumentContentInvalidStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)
    return TbmSummaryResponse(**payload)


@router.get("/{document_id}/file")
def download_document_file(
    document_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    disposition: str = Query("attachment"),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not doc.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if current_user.role == Role.SITE and doc.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    file_path = settings.storage_root / doc.file_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")
    fallback_name = doc.file_name or file_path.name
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(
        path=file_path,
        media_type=media_type,
        filename=fallback_name,
    )
    content_disposition = (
        f"{resolved_disposition}; filename*=UTF-8''{quote(fallback_name)}"
    )
    response.headers["Content-Disposition"] = content_disposition
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _download_document_derivative(
    *,
    document_id: int,
    relative_path: str | None,
    db,
    current_user,
    fallback_name: str,
    disposition: str,
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not relative_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if current_user.role == Role.SITE and doc.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    file_path = settings.storage_root / relative_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(path=file_path, media_type=media_type, filename=fallback_name)
    response.headers["Content-Disposition"] = f"{resolved_disposition}; filename*=UTF-8''{quote(fallback_name)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/{document_id}/file/original")
def download_document_original_file(
    document_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    disposition: str = Query("attachment"),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    fallback_name = doc.file_name if doc and doc.file_name else f"document_{document_id}_original"
    return _download_document_derivative(
        document_id=document_id,
        relative_path=(doc.original_file_path if doc else None),
        db=db,
        current_user=current_user,
        fallback_name=fallback_name,
        disposition=disposition,
    )


@router.get("/{document_id}/file/optimized")
def download_document_optimized_file(
    document_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    disposition: str = Query("inline"),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    fallback_name = doc.file_name if doc and doc.file_name else f"document_{document_id}_optimized"
    return _download_document_derivative(
        document_id=document_id,
        relative_path=(doc.optimized_file_path if doc else None),
        db=db,
        current_user=current_user,
        fallback_name=fallback_name,
        disposition=disposition,
    )


@router.post("")
async def create_document(
    db: DbDep,
    current_user: CurrentUserDep,
    title: Annotated[str, Form(...)],
    document_type: Annotated[str, Form(...)],
    site_id: int | None = Form(None),
    description: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    if current_user.role == Role.SITE:
        site_id = current_user.site_id
    if not site_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid site_id")
    assert_not_ledger_managed_document_type(document_type)

    doc = Document(
        document_no=f"DOC-{int(utc_now().timestamp())}",
        title=title,
        document_type=document_type,
        site_id=site_id,
        submitter_user_id=current_user.id,
        current_status=DocumentStatus.DRAFT,
        description=description,
        source_type="MANUAL",
    )

    if file:
        storage_dir = _ensure_storage_dir()
        filename = f"{doc.document_no}_{file.filename}"
        stored_path = storage_dir / filename
        content = await file.read()
        stored_path.write_bytes(content)
        doc.file_path = str(stored_path.relative_to(settings.storage_root))

    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def _add_history(
    db: Session,
    document: Document,
    user: User,
    action_type: str,
    comment: str | None = None,
) -> None:
    history = ApprovalHistory(
        document_id=document.id,
        action_by_user_id=user.id,
        action_type=action_type,
        comment=comment,
    )
    db.add(history)




@router.post("/{document_id}/review")
def review_document(
    document_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    body: ReviewActionBody,
):
    """
    업무 리뷰 전이 단일 진입점 (JSON).
    action: start_review | approve | reject
    """
    assert_hq_safe_workspace(current_user)

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    assert_not_ledger_managed_document(doc)
    if doc.instance_id is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document has no instance_id")

    inst = db.query(DocumentInstance).filter(DocumentInstance.id == doc.instance_id).first()
    if not inst:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")

    # 문서 상태는 기존 DocumentStatus를 유지(호환), instance는 workflow_status만 전이
    if body.action == "start_review":
        doc.current_status = DocumentStatus.UNDER_REVIEW
        before = inst.workflow_status
        transition_instance_workflow_status(inst, action="start_review")
        _add_history(db, doc, current_user, ApprovalAction.START_REVIEW, body.comment)
        add_review_history(
            db,
            inst=inst,
            document_id=doc.id,
            action_type=map_action_to_history_type("start_review"),
            action_by_user_id=current_user.id,
            comment=body.comment,
            from_workflow_status=before,
            to_workflow_status=inst.workflow_status,
        )
        db.add(inst)
        db.commit()
        db.refresh(doc)
        return doc

    # approve/reject는 기존 엔드포인트를 사용하도록 유도하되, JSON 단일 진입점도 허용
    if body.action == "approve":
        # approve_document와 동일 로직
        doc.current_status = DocumentStatus.APPROVED
        doc.reviewed_at = utc_now()
        _add_history(db, doc, current_user, ApprovalAction.APPROVE, body.comment)
        before = inst.workflow_status
        transition_instance_workflow_status(inst, action="approve")
        add_review_history(
            db,
            inst=inst,
            document_id=doc.id,
            action_type=map_action_to_history_type("approve"),
            action_by_user_id=current_user.id,
            comment=body.comment,
            from_workflow_status=before,
            to_workflow_status=inst.workflow_status,
        )
        db.add(inst)
        db.commit()
        db.refresh(doc)
        return doc

    if body.action == "reject":
        doc.current_status = DocumentStatus.REJECTED
        doc.rejection_reason = body.comment
        doc.reviewed_at = utc_now()
        _add_history(db, doc, current_user, ApprovalAction.REJECT, body.comment)
        before = inst.workflow_status
        transition_instance_workflow_status(inst, action="reject")
        add_review_history(
            db,
            inst=inst,
            document_id=doc.id,
            action_type=map_action_to_history_type("reject"),
            action_by_user_id=current_user.id,
            comment=body.comment,
            from_workflow_status=before,
            to_workflow_status=inst.workflow_status,
        )
        db.add(inst)
        db.commit()
        db.refresh(doc)
        return doc

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown action")
