from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from types import SimpleNamespace

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.modules.approvals.models import ApprovalHistory
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_settings.models import ContractorDocumentBundleItem, DocumentRequirement
from app.modules.documents.models import Document, DocumentUploadHistory
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Person
from app.modules.risk_library.models import (
    DailyWorkPlan,
    DailyWorkPlanConfirmation,
    DailyWorkPlanDocumentLink,
    DailyWorkPlanDistribution,
    DailyWorkPlanDistributionWorker,
    DailyWorkPlanItem,
    DailyWorkPlanItemRiskRef,
    RiskLibraryItemRevision,
)


@dataclass
class DocumentContentNotFoundError(Exception):
    message: str


@dataclass
class DocumentContentInvalidStateError(Exception):
    message: str


_STATUS_NOT_REQUIRED = "NOT_REQUIRED"
_STATUS_NOT_SUBMITTED = "NOT_SUBMITTED"
_STATUS_SUBMITTED = "SUBMITTED"
_STATUS_IN_REVIEW = "IN_REVIEW"
_STATUS_APPROVED = "APPROVED"
_STATUS_REJECTED = "REJECTED"


def _latest_review_comment_map(db: Session, document_ids: list[int]) -> dict[int, str]:
    if not document_ids:
        return {}
    rows = (
        db.query(ApprovalHistory)
        .filter(
            ApprovalHistory.document_id.in_(document_ids),
            ApprovalHistory.action_type.in_(["APPROVE", "REJECT"]),
            ApprovalHistory.comment.isnot(None),
            ApprovalHistory.comment != "",
        )
        .order_by(
            ApprovalHistory.document_id.asc(),
            ApprovalHistory.action_at.desc(),
            ApprovalHistory.id.desc(),
        )
        .all()
    )
    latest: dict[int, str] = {}
    for row in rows:
        if row.document_id in latest:
            continue
        latest[row.document_id] = row.comment
    return latest


def _period_window(period: str, target_date: date) -> tuple[date, date]:
    if period == "all":
        return date.min, date.max
    if period == "day":
        return target_date, target_date
    if period == "week":
        start = target_date - timedelta(days=target_date.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = date(target_date.year, target_date.month, 1)
        if target_date.month == 12:
            next_month = date(target_date.year + 1, 1, 1)
        else:
            next_month = date(target_date.year, target_date.month + 1, 1)
        return start, next_month - timedelta(days=1)
    if period == "quarter":
        quarter_start_month = ((target_date.month - 1) // 3) * 3 + 1
        start = date(target_date.year, quarter_start_month, 1)
        next_q_month = quarter_start_month + 3
        if next_q_month > 12:
            next_q = date(target_date.year + 1, next_q_month - 12, 1)
        else:
            next_q = date(target_date.year, next_q_month, 1)
        return start, next_q - timedelta(days=1)
    if period == "half_year":
        if target_date.month <= 6:
            return date(target_date.year, 1, 1), date(target_date.year, 6, 30)
        return date(target_date.year, 7, 1), date(target_date.year, 12, 31)
    if period == "year":
        return date(target_date.year, 1, 1), date(target_date.year, 12, 31)
    if period == "event":
        return date.min, date.max
    raise ValueError("period must be one of: all, day, week, month, quarter, half_year, year, event")


def _target_frequencies(period: str) -> set[str]:
    if period == "all":
        return {
            "DAILY",
            "WEEKLY",
            "MONTHLY",
            "QUARTERLY",
            "HALF_YEARLY",
            "YEARLY",
            "ONE_TIME",
            "EVENT",
            "ROLLING",
            "ADHOC",
        }
    if period == "day":
        return {"DAILY", "ROLLING", "ONE_TIME", "EVENT"}
    if period == "week":
        return {"DAILY", "WEEKLY", "ROLLING", "ONE_TIME", "EVENT"}
    if period == "month":
        return {"DAILY", "WEEKLY", "MONTHLY", "ROLLING", "ONE_TIME", "EVENT"}
    if period == "quarter":
        return {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "ROLLING", "ONE_TIME", "EVENT"}
    if period == "half_year":
        return {
            "DAILY",
            "WEEKLY",
            "MONTHLY",
            "QUARTERLY",
            "HALF_YEARLY",
            "ROLLING",
            "ONE_TIME",
            "EVENT",
        }
    if period == "year":
        return {
            "DAILY",
            "WEEKLY",
            "MONTHLY",
            "QUARTERLY",
            "HALF_YEARLY",
            "YEARLY",
            "ROLLING",
            "ONE_TIME",
            "EVENT",
        }
    if period == "event":
        return {"EVENT"}
    raise ValueError("period must be one of: all, day, week, month, quarter, half_year, year, event")


def _status_from_doc(doc: Document, inst: DocumentInstance | None, is_required: bool) -> str:
    if doc.current_status == "APPROVED":
        return _STATUS_APPROVED
    if doc.current_status == "REJECTED":
        return _STATUS_REJECTED
    if doc.current_status == "UNDER_REVIEW" or (inst and inst.workflow_status == WorkflowStatus.UNDER_REVIEW):
        return _STATUS_IN_REVIEW
    return _STATUS_SUBMITTED if is_required else _STATUS_NOT_REQUIRED


def _section_from_requirement(requirement: DocumentRequirement) -> str:
    code = (requirement.code or "").upper()
    title = (requirement.title or "").strip()
    text = f"{code} {title}"
    if "준공" in text or "COMPLETION" in code:
        return "COMPLETION"
    return "LEGAL"


def _category_from_requirement(requirement: DocumentRequirement) -> str:
    type_name = (requirement.document_type.name if requirement.document_type else "") or ""
    title = (requirement.title or "").strip()
    combined = f"{type_name} {title}"
    if "중처" in combined:
        return "MIDDLE_LAW"
    if "노동부" in combined and "안전" in combined:
        return "MOEL_SAFETY"
    if "노동부" in combined:
        return "MOEL_GENERAL"
    if "사규" in combined:
        return "INTERNAL_RULE"
    return "GENERAL"


def _pick_latest_for_requirement(
    db: Session,
    *,
    site_id: int,
    requirement: DocumentRequirement,
    from_date: date,
    to_date: date,
    apply_period_filter: bool = True,
) -> tuple[Document | None, DocumentInstance | None]:
    freq = (requirement.frequency or "").upper()

    q = (
        db.query(Document, DocumentInstance)
        .outerjoin(DocumentInstance, Document.instance_id == DocumentInstance.id)
        .filter(
            Document.site_id == site_id,
            or_(
                DocumentInstance.selected_requirement_id == requirement.id,
                Document.document_type == requirement.code,
                Document.document_type == requirement.document_type.code,
            ),
        )
    )

    if apply_period_filter and freq in {"DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "HALF_YEARLY", "YEARLY"}:
        q = q.filter(
            Document.period_start.isnot(None),
            Document.period_end.isnot(None),
            Document.period_start <= to_date,
            Document.period_end >= from_date,
        )

    row = q.order_by(Document.uploaded_at.desc().nullslast(), Document.id.desc()).first()
    if not row:
        return None, None
    return row[0], row[1]


def get_site_requirement_status(
    db: Session,
    *,
    site_id: int,
    period: str,
    target_date: date,
    completion_upload_enabled: bool = False,
) -> list[dict[str, Any]]:
    # MVP 기준: 파일럿(삼성 인정제) 현장 — 시드 기준 SITE002(청라 C18BL)에만 삼성 전용 그룹 오버라이드 적용
    pilot_site_code = "SITE002"
    from_date, to_date = _period_window(period, target_date)
    target_freqs = _target_frequencies(period)

    site = db.query(Site).filter(Site.id == site_id).first()
    group_key = "SAMSUNG" if (site and site.site_code == pilot_site_code) else "GENERAL"

    # base 요구사항(현장 단위) + 그룹 오버라이드(도급사 묶음 단위)를 합친 "실효 요구사항"을 사용한다.
    base_requirements = (
        db.query(DocumentRequirement)
        .filter(
            DocumentRequirement.site_id == site_id,
        )
        .order_by(DocumentRequirement.display_order.asc(), DocumentRequirement.id.asc())
        .all()
    )

    overrides = (
        db.query(ContractorDocumentBundleItem)
        .filter(ContractorDocumentBundleItem.group_key == group_key)
        .all()
    )
    override_map = {o.document_type_id: o for o in overrides}

    effective_requirements: list[SimpleNamespace] = []
    for req in base_requirements:
        o = override_map.get(req.document_type_id)
        effective_requirements.append(
            SimpleNamespace(
                # identity는 base requirement id를 유지(이력/선택 요구사항 참조 정합성)
                id=req.id,
                code=req.code,
                title=req.title,
                document_type_id=req.document_type_id,
                document_type=req.document_type,
                frequency=(o.frequency if o else req.frequency),
                is_enabled=(o.is_enabled if o else req.is_enabled),
                is_required=(o.is_required if o else req.is_required),
                display_order=(o.display_order if o else req.display_order),
                due_rule_text=(o.due_rule_text if o else req.due_rule_text),
                note=(o.note if o else req.note),
            )
        )

    items: list[dict[str, Any]] = []
    effective_requirements.sort(key=lambda r: (r.display_order, r.id))
    for req in effective_requirements:
        section = _section_from_requirement(req)
        if section == "COMPLETION" and not completion_upload_enabled:
            continue
        freq = (req.frequency or "").upper()
        if freq not in target_freqs:
            continue
        if not req.is_enabled:
            items.append(
                {
                    "requirement_id": req.id,
                    "document_type_code": req.code,
                    "title": req.title,
                    "frequency": freq,
                    "is_required": req.is_required,
                    "status": _STATUS_NOT_REQUIRED,
                    "latest_document_id": None,
                    "latest_instance_id": None,
                    "latest_uploaded_at": None,
                    "current_document_id": None,
                    "current_file_name": None,
                    "current_file_path": None,
                    "current_file_download_url": None,
                    "uploaded_at": None,
                    "uploaded_by_user_id": None,
                    "workflow_status": None,
                    "review_note": None,
                    "due_rule_text": req.due_rule_text,
                    "category": _category_from_requirement(req),
                    "section": section,
                    "completion_upload_enabled": completion_upload_enabled,
                }
            )
            continue

        doc, inst = _pick_latest_for_requirement(
            db,
            site_id=site_id,
            requirement=req,
            from_date=from_date,
            to_date=to_date,
        )
        # 기간 내 제출이 없더라도, 최신 반려 이력이 있으면 재업로드 TODO로 노출한다.
        if doc is None:
            latest_doc, latest_inst = _pick_latest_for_requirement(
                db,
                site_id=site_id,
                requirement=req,
                from_date=from_date,
                to_date=to_date,
                apply_period_filter=False,
            )
            if latest_doc is not None and latest_doc.current_status == "REJECTED":
                doc, inst = latest_doc, latest_inst
        if doc is None:
            status = _STATUS_NOT_SUBMITTED if req.is_required else _STATUS_NOT_REQUIRED
            items.append(
                {
                    "requirement_id": req.id,
                    "document_type_code": req.code,
                    "title": req.title,
                    "frequency": freq,
                    "is_required": req.is_required,
                    "status": status,
                    "latest_document_id": None,
                    "latest_instance_id": None,
                    "latest_uploaded_at": None,
                    "current_document_id": None,
                    "current_file_name": None,
                    "current_file_path": None,
                    "current_file_download_url": None,
                    "uploaded_at": None,
                    "uploaded_by_user_id": None,
                    "workflow_status": None,
                    "review_note": None,
                    "due_rule_text": req.due_rule_text,
                    "category": _category_from_requirement(req),
                    "section": section,
                    "completion_upload_enabled": completion_upload_enabled,
                }
            )
            continue

        items.append(
            {
                "requirement_id": req.id,
                "document_type_code": req.code,
                "title": req.title,
                "frequency": freq,
                "is_required": req.is_required,
                "status": _status_from_doc(doc, inst, req.is_required),
                "latest_document_id": doc.id,
                "latest_instance_id": doc.instance_id,
                "latest_uploaded_at": doc.uploaded_at,
                "current_document_id": doc.id,
                "current_file_name": doc.file_name or (Path(doc.file_path).name if doc.file_path else None),
                "current_file_path": doc.file_path,
                "current_file_download_url": f"/documents/{doc.id}/file",
                "uploaded_at": doc.uploaded_at,
                "uploaded_by_user_id": doc.uploaded_by_user_id,
                "workflow_status": (inst.workflow_status if inst else None),
                "review_note": doc.rejection_reason,
                "due_rule_text": req.due_rule_text,
                "category": _category_from_requirement(req),
                "section": section,
                "completion_upload_enabled": completion_upload_enabled,
            }
        )
    latest_doc_ids = [int(row["latest_document_id"]) for row in items if row.get("latest_document_id")]
    comment_map = _latest_review_comment_map(db, latest_doc_ids)
    for row in items:
        doc_id = row.get("latest_document_id")
        if not doc_id:
            continue
        latest_comment = comment_map.get(int(doc_id))
        if latest_comment:
            row["review_note"] = latest_comment

    def sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
        status = str(row.get("status") or "")
        if status == _STATUS_NOT_SUBMITTED:
            rank = 0
        elif status == _STATUS_REJECTED:
            rank = 1
        elif status == _STATUS_IN_REVIEW:
            rank = 2
        elif status == _STATUS_SUBMITTED:
            rank = 3
        elif status == _STATUS_APPROVED:
            rank = 4
        else:
            rank = 5
        uploaded = row.get("latest_uploaded_at")
        ts = 0
        if uploaded is not None:
            ts = -int(uploaded.timestamp())
        return rank, ts, str(row.get("title") or "")

    return sorted(items, key=sort_key)


def get_requirement_document_history(
    db: Session,
    *,
    site_id: int,
    requirement_id: int,
) -> list[dict[str, Any]]:
    requirement = db.query(DocumentRequirement).filter(DocumentRequirement.id == requirement_id).first()
    if requirement is None:
        return []

    histories = (
        db.query(DocumentUploadHistory)
        .join(Document, Document.id == DocumentUploadHistory.document_id)
        .outerjoin(DocumentInstance, DocumentUploadHistory.instance_id == DocumentInstance.id)
        .filter(
            Document.site_id == site_id,
            or_(
                DocumentInstance.selected_requirement_id == requirement_id,
                Document.document_type == requirement.code,
                Document.document_type == requirement.document_type.code,
            ),
        )
        .order_by(DocumentUploadHistory.uploaded_at.desc().nullslast(), DocumentUploadHistory.id.desc())
        .all()
    )

    rows: list[dict[str, Any]] = []
    for h in histories:
        rows.append(
            {
                "history_id": h.id,
                "document_id": h.document_id,
                "instance_id": h.instance_id,
                "version_no": h.version_no,
                "action_type": h.action_type,
                "status": h.document_status,
                "uploaded_at": h.uploaded_at,
                "review_note": h.review_note,
                "uploader_user_id": h.uploaded_by_user_id,
                "file_name": h.file_name,
            }
        )
    return rows


def get_document_content(
    db: Session,
    *,
    document_id: int,
) -> dict[str, Any]:
    # Query 1: document + instance key 정보 조회
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise DocumentContentNotFoundError("Document not found")
    if doc.instance_id is None:
        raise DocumentContentInvalidStateError("Document has no instance_id")

    # Query 2: instance에 연결된 plan + item 전체 조회 (item 없는 plan도 포함)
    rows = (
        db.query(
            DailyWorkPlan.id.label("plan_id"),
            DailyWorkPlan.site_id.label("site_id"),
            DailyWorkPlan.work_date.label("work_date"),
            DailyWorkPlan.author_user_id.label("author_user_id"),
            DailyWorkPlanItem.id.label("item_id"),
            DailyWorkPlanItem.work_name.label("work_name"),
            DailyWorkPlanItem.work_description.label("work_description"),
            DailyWorkPlanItem.team_label.label("team_label"),
            DailyWorkPlanItem.leader_person_id.label("leader_person_id"),
        )
        .join(DailyWorkPlanDocumentLink, DailyWorkPlanDocumentLink.plan_id == DailyWorkPlan.id)
        .outerjoin(DailyWorkPlanItem, DailyWorkPlanItem.plan_id == DailyWorkPlan.id)
        .filter(DailyWorkPlanDocumentLink.instance_id == doc.instance_id)
        .order_by(DailyWorkPlan.id.asc(), DailyWorkPlanItem.id.asc())
        .all()
    )

    plans_map: dict[int, dict[str, Any]] = {}
    item_ids: list[int] = []
    for row in rows:
        plan_id = int(row.plan_id)
        if plan_id not in plans_map:
            plans_map[plan_id] = {
                "plan_id": plan_id,
                "site_id": int(row.site_id),
                "work_date": row.work_date,
                "author_user_id": int(row.author_user_id),
                "items": [],
            }
        if row.item_id is None:
            continue
        item_id = int(row.item_id)
        item_ids.append(item_id)
        plans_map[plan_id]["items"].append(
            {
                "item_id": item_id,
                "work_name": row.work_name,
                "work_description": row.work_description,
                "team_label": row.team_label,
                "leader_person_id": row.leader_person_id,
                "risks": [],
            }
        )

    # Query 3: adopted risk + revision 상세 조회 (risk_cause 제외)
    risks_by_item: dict[int, list[dict[str, Any]]] = {}
    if item_ids:
        risk_rows = (
            db.query(
                DailyWorkPlanItemRiskRef.plan_item_id.label("item_id"),
                DailyWorkPlanItemRiskRef.risk_revision_id.label("risk_revision_id"),
                DailyWorkPlanItemRiskRef.risk_item_id.label("risk_item_id"),
                RiskLibraryItemRevision.risk_factor.label("risk_factor"),
                RiskLibraryItemRevision.countermeasure.label("counterplan"),
                RiskLibraryItemRevision.risk_f.label("frequency"),
                RiskLibraryItemRevision.risk_s.label("severity"),
                RiskLibraryItemRevision.risk_r.label("risk_level"),
            )
            .join(
                RiskLibraryItemRevision,
                RiskLibraryItemRevision.id == DailyWorkPlanItemRiskRef.risk_revision_id,
            )
            .filter(
                DailyWorkPlanItemRiskRef.plan_item_id.in_(item_ids),
                DailyWorkPlanItemRiskRef.link_type == "ADOPTED",
                DailyWorkPlanItemRiskRef.is_selected.is_(True),
            )
            .order_by(
                DailyWorkPlanItemRiskRef.plan_item_id.asc(),
                DailyWorkPlanItemRiskRef.display_order.asc(),
                DailyWorkPlanItemRiskRef.id.asc(),
            )
            .all()
        )
        for row in risk_rows:
            key = int(row.item_id)
            risks_by_item.setdefault(key, []).append(
                {
                    "risk_revision_id": int(row.risk_revision_id),
                    "risk_item_id": int(row.risk_item_id),
                    "risk_factor": row.risk_factor,
                    "counterplan": row.counterplan,
                    "frequency": int(row.frequency),
                    "severity": int(row.severity),
                    "risk_level": int(row.risk_level),
                }
            )

    plans = list(plans_map.values())
    for plan in plans:
        normalized_items = []
        for item in plan["items"]:
            normalized_items.append(
                {
                    "work_name": item["work_name"],
                    "work_description": item["work_description"],
                    "team_label": item["team_label"],
                    "leader_person_id": item["leader_person_id"],
                    "risks": risks_by_item.get(item["item_id"], []),
                }
            )
        plan["items"] = normalized_items

    work_date: date = doc.period_start if doc.period_start is not None else (
        plans[0]["work_date"] if plans else doc.created_at.date()
    )
    site_id = int(doc.site_id)
    if plans:
        site_id = int(plans[0]["site_id"])

    return {
        "document_id": doc.id,
        "instance_id": int(doc.instance_id),
        "site_id": site_id,
        "work_date": work_date,
        "plans": plans,
    }


def get_top_risks(*, plans: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    all_risks: list[dict[str, Any]] = []
    for plan in plans:
        for item in plan.get("items", []):
            for risk in item.get("risks", []):
                all_risks.append(risk)
    all_risks.sort(key=lambda r: int(r.get("risk_level", 0)), reverse=True)
    return all_risks[: max(1, limit)]


def _compute_tbm_daily_monitoring_rows(
    db: Session,
    *,
    site_id: int,
    start_date: date,
    end_date: date,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """
    TBM 월간 집계에서 쓰는 “일별 운영데이터 요약”을 계산한다.

    생성 기준(분모): 해당 월 범위 내 `DailyWorkPlan.work_date` distinct 개수
    완료 기준: 해당 일의 distribution_worker 모두에 대해 `end_signed_at` 존재
    """

    work_date_rows = (
        db.query(DailyWorkPlan.work_date)
        .filter(
            DailyWorkPlan.site_id == site_id,
            DailyWorkPlan.work_date >= start_date,
            DailyWorkPlan.work_date <= end_date,
        )
        .distinct()
        .order_by(DailyWorkPlan.work_date.asc())
        .all()
    )
    work_dates = [row.work_date for row in work_date_rows]

    # 분모가 되는 “생성된 일”은 work_date distinct를 그대로 사용한다.
    generated_days = len(work_dates)
    if generated_days == 0:
        return (
            {
                "generated_days": 0,
                "completed_days": 0,
                "distributed_days": 0,
                "confirmed_days": 0,
                "missing_days": 0,
                "completion_rate_pct": 0.0,
            },
            [],
        )

    dist_counts = (
        db.query(
            DailyWorkPlan.work_date.label("work_date"),
            func.count(DailyWorkPlanDistribution.id).label("distribution_count"),
        )
        .join(DailyWorkPlanDistribution, DailyWorkPlanDistribution.plan_id == DailyWorkPlan.id)
        .filter(
            DailyWorkPlan.site_id == site_id,
            DailyWorkPlan.work_date >= start_date,
            DailyWorkPlan.work_date <= end_date,
        )
        .group_by(DailyWorkPlan.work_date)
        .all()
    )
    dist_count_map = {row.work_date: int(row.distribution_count) for row in dist_counts}

    worker_counts = (
        db.query(
            DailyWorkPlan.work_date.label("work_date"),
            func.count(DailyWorkPlanDistributionWorker.id).label("worker_total"),
            func.sum(
                case(
                    (DailyWorkPlanDistributionWorker.end_signed_at.is_not(None), 1),
                    else_=0,
                )
            ).label("worker_completed"),
        )
        .join(
            DailyWorkPlanDistribution,
            DailyWorkPlanDistribution.id == DailyWorkPlanDistributionWorker.distribution_id,
        )
        .join(DailyWorkPlan, DailyWorkPlan.id == DailyWorkPlanDistribution.plan_id)
        .filter(
            DailyWorkPlan.site_id == site_id,
            DailyWorkPlan.work_date >= start_date,
            DailyWorkPlan.work_date <= end_date,
        )
        .group_by(DailyWorkPlan.work_date)
        .all()
    )
    worker_total_map = {row.work_date: int(row.worker_total) for row in worker_counts}
    worker_completed_map = {row.work_date: int(row.worker_completed) for row in worker_counts}

    conf_counts = (
        db.query(
            DailyWorkPlan.work_date.label("work_date"),
            func.count(DailyWorkPlanConfirmation.id).label("confirmation_count"),
        )
        .join(DailyWorkPlanConfirmation, DailyWorkPlanConfirmation.plan_id == DailyWorkPlan.id)
        .filter(
            DailyWorkPlan.site_id == site_id,
            DailyWorkPlan.work_date >= start_date,
            DailyWorkPlan.work_date <= end_date,
        )
        .group_by(DailyWorkPlan.work_date)
        .all()
    )
    conf_count_map = {row.work_date: int(row.confirmation_count) for row in conf_counts}

    completed_days = 0
    distributed_days = 0
    confirmed_days = 0
    missing_days = 0

    daily_rows: list[dict[str, Any]] = []
    for wd in work_dates:
        distribution_count = dist_count_map.get(wd, 0)
        confirmation_count = conf_count_map.get(wd, 0)
        worker_total = worker_total_map.get(wd, 0)
        worker_completed = worker_completed_map.get(wd, 0)

        distributed = distribution_count > 0
        confirmed = confirmation_count > 0
        completed = worker_total > 0 and worker_completed == worker_total
        missing = not completed

        if completed:
            completed_days += 1
        if distributed:
            distributed_days += 1
        if confirmed:
            confirmed_days += 1
        if missing:
            missing_days += 1

        daily_rows.append(
            {
                "work_date": wd,
                "distributed": distributed,
                "confirmed": confirmed,
                "confirmation_count": confirmation_count,
                "distribution_count": distribution_count,
                "worker_total": worker_total,
                "worker_completed": worker_completed,
                "completed": completed,
                "missing": missing,
            }
        )

    completion_rate_pct = round((completed_days / generated_days) * 100, 1)
    monthly_summary = {
        "generated_days": generated_days,
        "completed_days": completed_days,
        "distributed_days": distributed_days,
        "confirmed_days": confirmed_days,
        "missing_days": missing_days,
        "completion_rate_pct": completion_rate_pct,
    }
    return monthly_summary, daily_rows


def get_tbm_periodic_monthly_monitoring(
    db: Session,
    *,
    site_ids: list[int],
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for site_id in site_ids:
        site = db.query(Site).filter(Site.id == site_id).first()
        if site is None:
            continue
        summary, _ = _compute_tbm_daily_monitoring_rows(
            db,
            site_id=site_id,
            start_date=start_date,
            end_date=end_date,
        )
        result.append(
            {
                "site_id": site_id,
                "site_name": site.site_name,
                **summary,
            }
        )
    return result


def get_tbm_periodic_daily_monitoring(
    db: Session,
    *,
    site_id: int,
    start_date: date,
    end_date: date,
) -> dict[str, Any]:
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise ValueError("site_not_found")

    summary, daily_rows = _compute_tbm_daily_monitoring_rows(
        db,
        site_id=site_id,
        start_date=start_date,
        end_date=end_date,
    )
    summary_with_site = {"site_id": site_id, "site_name": site.site_name, **summary}
    return {
        "site_id": site_id,
        "site_name": site.site_name,
        "summary": summary_with_site,
        "days": daily_rows,
    }


def get_tbm_summary(
    db: Session,
    *,
    document_id: int,
) -> dict[str, Any]:
    content = get_document_content(db, document_id=document_id)
    plans = content["plans"]
    site = db.query(Site).filter(Site.id == content["site_id"]).first()

    author_user_id = plans[0]["author_user_id"] if plans else None
    leader_name = None
    if author_user_id is not None:
        author = db.query(User).filter(User.id == int(author_user_id)).first()
        leader_name = author.name if author else None

    plan_ids = [int(p["plan_id"]) for p in plans]
    workers: list[dict[str, Any]] = []
    worker_count = 0
    if plan_ids:
        distribution_ids = (
            db.query(DailyWorkPlanDistribution.id)
            .filter(
                DailyWorkPlanDistribution.plan_id.in_(plan_ids),
                DailyWorkPlanDistribution.target_date == content["work_date"],
            )
            .all()
        )
        distribution_id_list = [int(row.id) for row in distribution_ids]
        if distribution_id_list:
            worker_rows = (
                db.query(DailyWorkPlanDistributionWorker, Person)
                .join(Person, Person.id == DailyWorkPlanDistributionWorker.person_id)
                .filter(
                    DailyWorkPlanDistributionWorker.distribution_id.in_(distribution_id_list),
                )
                .order_by(
                    DailyWorkPlanDistributionWorker.start_signed_at.is_(None).asc(),
                    DailyWorkPlanDistributionWorker.start_signed_at.asc(),
                    DailyWorkPlanDistributionWorker.end_signed_at.is_(None).asc(),
                    DailyWorkPlanDistributionWorker.end_signed_at.asc(),
                    DailyWorkPlanDistributionWorker.id.asc(),
                )
                .all()
            )
            worker_count = len(worker_rows)
            for worker, person in worker_rows:
                workers.append(
                    {
                        "person_id": person.id,
                        "name": person.name,
                        "ack_status": worker.ack_status,
                        "start_signed_at": worker.start_signed_at,
                        "end_signed_at": worker.end_signed_at,
                        "end_status": worker.end_status,
                        "issue_flag": worker.issue_flag,
                        "start_signature_data": worker.start_signature_data or worker.signature_data,
                        "end_signature_data": worker.end_signature_data,
                    }
                )

    dedup_rows: dict[str, dict[str, Any]] = {}
    for plan in plans:
        for item in plan.get("items", []):
            risks = item.get("risks", [])
            for risk in risks:
                risk_factor = (risk.get("risk_factor") or "").strip()
                if not risk_factor:
                    continue
                counterplan = (risk.get("counterplan") or "").strip()
                existing = dedup_rows.get(risk_factor)
                if existing is None:
                    dedup_rows[risk_factor] = {
                        "work_description": "전체 작업",
                        "risk_factor": risk_factor,
                        "counterplan": counterplan,
                        "risk_level": risk.get("risk_level"),
                    }
                    continue
                if counterplan:
                    existing_set = {
                        token.strip()
                        for token in str(existing.get("counterplan") or "").split(" / ")
                        if token.strip()
                    }
                    if counterplan not in existing_set:
                        merged = [*existing_set, counterplan]
                        existing["counterplan"] = " / ".join(merged)
                prev_level = existing.get("risk_level")
                next_level = risk.get("risk_level")
                if prev_level is None or (next_level is not None and int(next_level) > int(prev_level)):
                    existing["risk_level"] = next_level

    table_rows = list(dedup_rows.values())
    if not table_rows:
        table_rows.append(
            {
                "work_description": "전체 작업",
                "risk_factor": "-",
                "counterplan": "-",
                "risk_level": None,
            }
        )

    top_risks = get_top_risks(plans=plans, limit=5)
    return {
        "document_id": content["document_id"],
        "instance_id": content["instance_id"],
        "site_id": content["site_id"],
        "site_name": site.site_name if site else None,
        "work_date": content["work_date"],
        "tbm_leader_name": leader_name,
        "education_count": worker_count,
        "table_rows": table_rows,
        "top_risks": top_risks,
        "participants": workers,
    }
