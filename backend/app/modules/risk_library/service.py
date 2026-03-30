from __future__ import annotations

from collections import defaultdict
import base64
import binascii
import hashlib
import math
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.modules.document_generation.constants import DocumentSourceType
from app.modules.document_generation.models import (
    DocumentInstance,
    DocumentInstanceStatus,
    PeriodBasis,
    WorkflowStatus,
)
from app.modules.documents.models import Document, DocumentStatus
from app.modules.risk_library.models import (
    DailyWorkPlanDistribution,
    DailyWorkPlanDistributionWorker,
    DailyWorkPlan,
    SiteAdminPresence,
    DailyWorkPlanConfirmation,
    DailyWorkPlanDocumentLink,
    DailyWorkPlanItem,
    DailyWorkPlanItemRiskRef,
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
    WorkerFeedback,
    RiskLibraryFeedbackCandidate,
)
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Employment, Person


RECOMMEND_TOKEN_STOPWORDS = {
    "작업",
    "공사",
    "구간",
    "주변",
    "부분",
    "관련",
    "진행",
    "예정",
    "확인",
    "점검",
    "필요",
    "포함",
    "사용",
    "관리",
    "현장",
    "기타",
}

OFFICE_WORK_KEYWORDS = {
    "도면",
    "서류",
    "검토",
    "회의",
    "협의",
    "교육",
    "보고",
    "정리",
}

FIELD_WORK_KEYWORDS = {
    "배관",
    "벽체 배관",
    "천장슬라브 배관",
    "슬라브 배관",
    "전선관 배관",
    "매입 배관",
    "배선",
    "결선",
    "전기",
    "설치",
    "포설",
    "조명",
    "인양",
    "용접",
    "절단",
    "고소작업",
}

PHYSICAL_RISK_KEYWORDS = {
    "중량물",
    "낙하",
    "감전",
    "충전부",
    "배관",
    "배선",
    "고소",
    "추락",
    "활선",
    "협착",
    "끼임",
    "사다리",
    "인양",
}

PHRASE_SUFFIXES = {"배관", "배선", "설치", "검토"}


def _normalize_recommendation_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[\t\r\n/,_()（）\[\]{}:;|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_location_noise_token(token: str) -> bool:
    if re.match(r"^\d+동$", token):
        return True
    if re.match(r"^(지하|지상)\d+층$", token):
        return True
    if token.endswith("센터") or token.endswith("동") and any(ch.isdigit() for ch in token):
        return True
    return False


def _extract_recommendation_tokens(text: str) -> set[str]:
    normalized = _normalize_recommendation_text(text)
    raw_tokens = [t for t in normalized.split(" ") if t]
    tokens: set[str] = set()

    for token in raw_tokens:
        if len(token) < 2:
            continue
        if token in RECOMMEND_TOKEN_STOPWORDS:
            continue
        if _is_location_noise_token(token):
            continue
        tokens.add(token)

    for idx in range(len(raw_tokens) - 1):
        left = raw_tokens[idx]
        right = raw_tokens[idx + 1]
        if right in PHRASE_SUFFIXES and len(left) >= 2 and not _is_location_noise_token(left):
            tokens.add(f"{left} {right}")

    if "천장슬라브 배관" in normalized:
        tokens.add("천장슬라브 배관")
        tokens.add("슬라브 배관")
        tokens.add("배관")
    if "벽체 배관" in normalized:
        tokens.add("벽체 배관")
        tokens.add("배관")
    if "전선관 배관" in normalized:
        tokens.add("전선관 배관")
        tokens.add("배관")
    if "매입 배관" in normalized:
        tokens.add("매입 배관")
        tokens.add("배관")
    if "배관" in normalized:
        tokens.add("배관")
    if "배선" in normalized:
        tokens.add("배선")
    if "검토" in normalized:
        tokens.add("검토")

    return tokens


def _build_revision_blob(rev: RiskLibraryItemRevision) -> str:
    return _normalize_recommendation_text(
        " ".join(
            filter(
                None,
                [
                    rev.unit_work,
                    rev.work_category,
                    rev.trade_type,
                    rev.process,
                    rev.risk_factor,
                    rev.risk_cause,
                    rev.countermeasure,
                    rev.note,
                ],
            )
        )
    )


def _collect_rule_hits(normalized_text: str) -> set[str]:
    hits: set[str] = set()
    for keyword in FIELD_WORK_KEYWORDS:
        if keyword in normalized_text:
            hits.add(keyword)
    return hits


def _is_office_work(normalized_text: str, explicit_hits: set[str]) -> bool:
    has_office_keyword = any(keyword in normalized_text for keyword in OFFICE_WORK_KEYWORDS)
    has_field_keyword = any(keyword in explicit_hits for keyword in FIELD_WORK_KEYWORDS)
    return has_office_keyword and not has_field_keyword


def recommend_risks_for_work_item(
    db: Session,
    work_name: str,
    work_description: str,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    text = f"{work_name or ''} {work_description or ''}".strip()
    normalized_text = _normalize_recommendation_text(text)
    if not normalized_text:
        return []

    tokens = _extract_recommendation_tokens(text)
    explicit_hits = _collect_rule_hits(normalized_text)
    office_mode = _is_office_work(normalized_text, explicit_hits)
    if not tokens and not explicit_hits:
        return []

    token_list = sorted(tokens)
    score_rows = (
        db.query(
            RiskLibraryKeyword.risk_revision_id.label("risk_revision_id"),
            func.sum(RiskLibraryKeyword.weight).label("score"),
        )
        .join(
            RiskLibraryItemRevision,
            RiskLibraryItemRevision.id == RiskLibraryKeyword.risk_revision_id,
        )
        .join(RiskLibraryItem, RiskLibraryItem.id == RiskLibraryItemRevision.item_id)
        .filter(
            RiskLibraryItemRevision.is_current.is_(True),
            RiskLibraryItem.is_active.is_(True),
            RiskLibraryKeyword.keyword.in_(token_list),
        )
        .group_by(RiskLibraryKeyword.risk_revision_id)
        .order_by(func.sum(RiskLibraryKeyword.weight).desc())
        .limit(max(1, top_n))
        .all()
    )

    score_map = {int(r.risk_revision_id): float(r.score or 0.0) for r in score_rows}
    revisions = (
        db.query(RiskLibraryItemRevision)
        .join(RiskLibraryItem, RiskLibraryItem.id == RiskLibraryItemRevision.item_id)
        .filter(
            RiskLibraryItemRevision.is_current.is_(True),
            RiskLibraryItem.is_active.is_(True),
        )
        .all()
    )
    revision_ids = [r.id for r in revisions]
    revisions = (
        revisions
    )
    revision_map = {r.id: r for r in revisions}

    # 키워드 히트 목록(설명 용도)
    keyword_rows = (
        db.query(
            RiskLibraryKeyword.risk_revision_id,
            RiskLibraryKeyword.keyword,
            RiskLibraryKeyword.weight,
        )
        .filter(
            RiskLibraryKeyword.risk_revision_id.in_(revision_ids),
            RiskLibraryKeyword.keyword.in_(token_list),
        )
        .all()
    )
    hits_by_revision: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in keyword_rows:
        hits_by_revision[int(row.risk_revision_id)].append(
            {"keyword": row.keyword, "weight": float(row.weight or 0.0)}
        )

    result: list[dict[str, Any]] = []
    for rev in revisions:
        revision_id = rev.id
        score = float(score_map.get(revision_id, 0.0))
        rev_blob = _build_revision_blob(rev)
        synthetic_hits = list(hits_by_revision.get(revision_id, []))

        if "배관" in explicit_hits and "배관" in rev_blob:
            score += 8.0
            synthetic_hits.append({"keyword": "배관", "weight": 8.0})
        if "벽체 배관" in explicit_hits and "벽체" in rev_blob and "배관" in rev_blob:
            score += 4.0
            synthetic_hits.append({"keyword": "벽체 배관", "weight": 4.0})
        if "천장슬라브 배관" in explicit_hits and ("천장슬라브" in rev_blob or "슬라브" in rev_blob) and "배관" in rev_blob:
            score += 4.0
            synthetic_hits.append({"keyword": "천장슬라브 배관", "weight": 4.0})
        elif "슬라브 배관" in explicit_hits and "슬라브" in rev_blob and "배관" in rev_blob:
            score += 3.0
            synthetic_hits.append({"keyword": "슬라브 배관", "weight": 3.0})
        if "배선" in explicit_hits and "배선" in rev_blob:
            score += 6.0
            synthetic_hits.append({"keyword": "배선", "weight": 6.0})

        if score <= 0 and explicit_hits:
            for hit in explicit_hits:
                if hit in rev_blob:
                    score += 1.5
                    synthetic_hits.append({"keyword": hit, "weight": 1.5})

        if office_mode and any(keyword in rev_blob for keyword in PHYSICAL_RISK_KEYWORDS):
            score -= 10.0

        if score <= 0:
            continue

        result.append(
            {
                "risk_item_id": rev.item_id,
                "risk_revision_id": rev.id,
                "unit_work": rev.unit_work,
                "work_category": rev.work_category,
                "trade_type": rev.trade_type,
                "process": rev.process,
                "risk_factor": rev.risk_factor,
                "risk_cause": rev.risk_cause,
                "countermeasure": rev.countermeasure,
                "note": rev.note,
                "source_file": rev.source_file,
                "source_sheet": rev.source_sheet,
                "source_row": rev.source_row,
                "source_page_or_section": rev.source_page_or_section,
                "risk_f": rev.risk_f,
                "risk_s": rev.risk_s,
                "risk_r": rev.risk_r,
                "score": score,
                "matched_keywords": synthetic_hits,
            }
        )
    result.sort(key=lambda row: float(row["score"]), reverse=True)
    return result[: max(1, top_n)]


def list_risk_library_entries(
    db: Session,
    *,
    keyword: str | None = None,
    work_category: str | None = None,
    process: str | None = None,
    risk_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    query_obj = (
        db.query(RiskLibraryItemRevision)
        .join(RiskLibraryItem, RiskLibraryItem.id == RiskLibraryItemRevision.item_id)
        .filter(
            RiskLibraryItemRevision.is_current.is_(True),
            RiskLibraryItem.is_active.is_(True),
        )
    )

    keyword_value = (keyword or "").strip()
    if keyword_value:
        like_value = f"%{keyword_value}%"
        keyword_match_exists = (
            db.query(RiskLibraryKeyword.id)
            .filter(
                RiskLibraryKeyword.risk_revision_id == RiskLibraryItemRevision.id,
                RiskLibraryKeyword.keyword.like(like_value),
            )
            .exists()
        )
        query_obj = query_obj.filter(
            or_(
                RiskLibraryItemRevision.unit_work.like(like_value),
                RiskLibraryItemRevision.work_category.like(like_value),
                RiskLibraryItemRevision.trade_type.like(like_value),
                RiskLibraryItemRevision.process.like(like_value),
                RiskLibraryItemRevision.risk_factor.like(like_value),
                RiskLibraryItemRevision.countermeasure.like(like_value),
                RiskLibraryItemRevision.note.like(like_value),
                RiskLibraryItemRevision.source_page_or_section.like(like_value),
                keyword_match_exists,
            )
        )

    work_category_value = (work_category or "").strip()
    if work_category_value:
        like_value = f"%{work_category_value}%"
        query_obj = query_obj.filter(
            or_(
                RiskLibraryItemRevision.unit_work.like(like_value),
                RiskLibraryItemRevision.work_category.like(like_value),
                RiskLibraryItemRevision.trade_type.like(like_value),
            )
        )

    process_value = (process or "").strip()
    if process_value:
        like_value = f"%{process_value}%"
        query_obj = query_obj.filter(RiskLibraryItemRevision.process.like(like_value))

    risk_type_value = (risk_type or "").strip()
    if risk_type_value:
        like_value = f"%{risk_type_value}%"
        risk_type_keyword_exists = (
            db.query(RiskLibraryKeyword.id)
            .filter(
                RiskLibraryKeyword.risk_revision_id == RiskLibraryItemRevision.id,
                RiskLibraryKeyword.keyword.like(like_value),
            )
            .exists()
        )
        query_obj = query_obj.filter(
            or_(
                RiskLibraryItemRevision.risk_factor.like(like_value),
                RiskLibraryItemRevision.countermeasure.like(like_value),
                risk_type_keyword_exists,
            )
        )

    total = int(query_obj.count())
    rows = (
        query_obj.order_by(
            RiskLibraryItemRevision.risk_r.desc(),
            RiskLibraryItemRevision.id.asc(),
        )
        .offset(max(0, int(offset)))
        .limit(max(1, int(limit)))
        .all()
    )

    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "risk_revision_id": row.id,
                "risk_item_id": row.item_id,
                "unit_work": row.unit_work,
                "work_category": row.work_category,
                "trade_type": row.trade_type,
                "process": row.process,
                "risk_factor": row.risk_factor,
                "counterplan": row.countermeasure,
                "risk_f": row.risk_f,
                "risk_s": row.risk_s,
                "risk_r": row.risk_r,
                "note": row.note,
                "source_file": row.source_file,
                "source_sheet": row.source_sheet,
                "source_row": row.source_row,
                "source_page_or_section": row.source_page_or_section,
            }
        )

    return {
        "total": total,
        "limit": max(1, int(limit)),
        "offset": max(0, int(offset)),
        "items": items,
    }


def create_daily_work_plan(
    db: Session,
    *,
    site_id: int,
    work_date: date,
    author_user_id: int,
) -> DailyWorkPlan:
    plan = DailyWorkPlan(
        site_id=site_id,
        work_date=work_date,
        author_user_id=author_user_id,
        status="DRAFT",
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def get_daily_work_plan(db: Session, plan_id: int) -> DailyWorkPlan | None:
    return db.query(DailyWorkPlan).filter(DailyWorkPlan.id == plan_id).first()


def create_daily_work_plan_item(
    db: Session,
    *,
    plan_id: int,
    work_name: str,
    work_description: str,
    team_label: str | None,
    leader_person_id: int | None,
) -> DailyWorkPlanItem:
    item = DailyWorkPlanItem(
        plan_id=plan_id,
        work_name=work_name,
        work_description=work_description,
        team_label=team_label,
        leader_person_id=leader_person_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def run_recommendation_for_plan_item(
    db: Session,
    *,
    plan_item_id: int,
    top_n: int,
) -> dict[str, int]:
    item = db.query(DailyWorkPlanItem).filter(DailyWorkPlanItem.id == plan_item_id).first()
    if item is None:
        raise ValueError("plan_item_not_found")

    recommendations = recommend_risks_for_work_item(
        db=db,
        work_name=item.work_name,
        work_description=item.work_description,
        top_n=top_n,
    )
    if not recommendations:
        return {"recommended_count": 0, "upserted_count": 0}

    existing_refs = (
        db.query(DailyWorkPlanItemRiskRef)
        .filter(DailyWorkPlanItemRiskRef.plan_item_id == plan_item_id)
        .all()
    )
    existing_by_revision_id = {ref.risk_revision_id: ref for ref in existing_refs}

    upserted_count = 0
    for order, rec in enumerate(recommendations, start=1):
        revision_id = int(rec["risk_revision_id"])
        ref = existing_by_revision_id.get(revision_id)
        if ref is None:
            ref = DailyWorkPlanItemRiskRef(
                plan_item_id=plan_item_id,
                risk_item_id=int(rec["risk_item_id"]),
                risk_revision_id=revision_id,
                link_type="RECOMMENDED",
                is_selected=False,
                source_rule="KEYWORD_MATCH",
                score=float(rec.get("score", 0.0) or 0.0),
                display_order=order,
            )
            db.add(ref)
            upserted_count += 1
            continue

        ref.risk_item_id = int(rec["risk_item_id"])
        ref.source_rule = "KEYWORD_MATCH"
        ref.score = float(rec.get("score", 0.0) or 0.0)
        ref.display_order = order
        if not ref.is_selected:
            ref.link_type = "RECOMMENDED"
        upserted_count += 1

    db.commit()
    return {
        "recommended_count": len(recommendations),
        "upserted_count": upserted_count,
    }


def list_risk_refs_for_plan_item(
    db: Session,
    *,
    plan_item_id: int,
) -> list[dict]:
    refs = (
        db.query(DailyWorkPlanItemRiskRef)
        .filter(DailyWorkPlanItemRiskRef.plan_item_id == plan_item_id)
        .order_by(
            DailyWorkPlanItemRiskRef.is_selected.desc(),
            DailyWorkPlanItemRiskRef.display_order.asc(),
            DailyWorkPlanItemRiskRef.id.asc(),
        )
        .all()
    )
    revision_ids = [r.risk_revision_id for r in refs]
    revisions = {}
    if revision_ids:
        for rev in (
            db.query(RiskLibraryItemRevision)
            .filter(RiskLibraryItemRevision.id.in_(revision_ids))
            .all()
        ):
            revisions[rev.id] = rev

    result = []
    for ref in refs:
        rev = revisions.get(ref.risk_revision_id)
        d = {
            "id": ref.id,
            "plan_item_id": ref.plan_item_id,
            "risk_item_id": ref.risk_item_id,
            "risk_revision_id": ref.risk_revision_id,
            "link_type": ref.link_type,
            "is_selected": ref.is_selected,
            "source_rule": ref.source_rule,
            "score": ref.score,
            "display_order": ref.display_order,
            "created_at": ref.created_at,
            "risk_factor": rev.risk_factor if rev else None,
            "countermeasure": rev.countermeasure if rev else None,
            "risk_r": rev.risk_r if rev else None,
        }
        result.append(d)
    return result


def adopt_risks_for_plan_item_by_revision_ids(
    db: Session,
    *,
    plan_item_id: int,
    risk_revision_ids: list[int],
) -> dict[str, int]:
    item = db.query(DailyWorkPlanItem).filter(DailyWorkPlanItem.id == plan_item_id).first()
    if item is None:
        raise ValueError("plan_item_not_found")

    normalized_ids = sorted({int(x) for x in risk_revision_ids})
    refs = (
        db.query(DailyWorkPlanItemRiskRef)
        .filter(DailyWorkPlanItemRiskRef.plan_item_id == plan_item_id)
        .all()
    )
    refs_by_revision_id = {ref.risk_revision_id: ref for ref in refs}

    adopted_count = 0
    for revision_id in normalized_ids:
        ref = refs_by_revision_id.get(revision_id)
        if ref is None:
            revision = (
                db.query(RiskLibraryItemRevision)
                .filter(
                    RiskLibraryItemRevision.id == revision_id,
                    RiskLibraryItemRevision.is_current.is_(True),
                )
                .first()
            )
            if revision is None:
                continue
            max_order = max((r.display_order for r in refs_by_revision_id.values()), default=0)
            ref = DailyWorkPlanItemRiskRef(
                plan_item_id=plan_item_id,
                risk_item_id=revision.item_id,
                risk_revision_id=revision.id,
                link_type="ADOPTED",
                is_selected=True,
                source_rule="MANUAL_ADOPT",
                score=0.0,
                display_order=max_order + 1,
            )
            db.add(ref)
            refs_by_revision_id[revision_id] = ref
            adopted_count += 1
            continue

        ref.is_selected = True
        ref.link_type = "ADOPTED"
        if ref.source_rule != "MANUAL_ADOPT":
            ref.source_rule = "MANUAL_ADOPT"
        adopted_count += 1

    for revision_id, ref in refs_by_revision_id.items():
        if revision_id not in normalized_ids and ref.is_selected:
            ref.is_selected = False
            if ref.link_type == "ADOPTED":
                ref.link_type = "RECOMMENDED"

    db.commit()
    return {
        "adopted_count": adopted_count,
        "requested_count": len(normalized_ids),
    }


def confirm_daily_work_plan(
    db: Session,
    *,
    plan_id: int,
    confirmed_by_user_id: int,
) -> tuple[DailyWorkPlanConfirmation, bool]:
    existing = (
        db.query(DailyWorkPlanConfirmation)
        .filter(
            DailyWorkPlanConfirmation.plan_id == plan_id,
            DailyWorkPlanConfirmation.confirmed_by_user_id == confirmed_by_user_id,
        )
        .first()
    )
    if existing is not None:
        return existing, False

    confirmation = DailyWorkPlanConfirmation(
        plan_id=plan_id,
        confirmed_by_user_id=confirmed_by_user_id,
        confirmed_at=utc_now(),
    )
    db.add(confirmation)
    db.commit()
    db.refresh(confirmation)
    return confirmation, True


def list_plan_confirmations(
    db: Session,
    *,
    plan_id: int,
) -> list[DailyWorkPlanConfirmation]:
    return (
        db.query(DailyWorkPlanConfirmation)
        .filter(DailyWorkPlanConfirmation.plan_id == plan_id)
        .order_by(DailyWorkPlanConfirmation.confirmed_at.desc(), DailyWorkPlanConfirmation.id.desc())
        .all()
    )


WORKER_SIGNATURE_MIN_BYTES = 256
WORKER_SIGNATURE_MAX_BYTES = 2 * 1024 * 1024
ADMIN_PRESENCE_WINDOW_MINUTES = 10
PNG_DATA_PREFIX = "data:image/png;base64,"
ADMIN_ROLES = {Role.SUPER_ADMIN, Role.HQ_SAFE_ADMIN, Role.HQ_SAFE, Role.SITE}
END_STATUSES = {"NORMAL", "ISSUE"}


def _resolve_distribution_status(visible_from: datetime) -> str:
    return "VISIBLE" if visible_from <= utc_now() else "SCHEDULED"


def _is_tbm_active(distribution: DailyWorkPlanDistribution) -> bool:
    return distribution.tbm_started_at is not None


def _list_active_employments_for_site(
    db: Session,
    *,
    site_code: str,
    target_date: date,
) -> list[Employment]:
    return (
        db.query(Employment)
        .filter(
            Employment.is_active.is_(True),
            Employment.site_code == site_code,
            (Employment.termination_date.is_(None) | (Employment.termination_date >= target_date)),
            (Employment.hire_date.is_(None) | (Employment.hire_date <= target_date)),
        )
        .all()
    )


def _serialize_distribution(distribution: DailyWorkPlanDistribution, *, worker_count: int) -> dict[str, Any]:
    return {
        "id": distribution.id,
        "plan_id": distribution.plan_id,
        "site_id": distribution.site_id,
        "target_date": distribution.target_date,
        "visible_from": distribution.visible_from,
        "distributed_by_user_id": distribution.distributed_by_user_id,
        "distributed_at": distribution.distributed_at,
        "status": distribution.status,
        "tbm_started_at": distribution.tbm_started_at,
        "tbm_started_by_user_id": distribution.tbm_started_by_user_id,
        "parent_distribution_id": distribution.parent_distribution_id,
        "is_reassignment": distribution.is_reassignment,
        "reassignment_reason": distribution.reassignment_reason,
        "reassigned_by_user_id": distribution.reassigned_by_user_id,
        "reassigned_at": distribution.reassigned_at,
        "is_tbm_active": _is_tbm_active(distribution),
        "worker_count": worker_count,
    }


def _serialize_feedback(
    feedback: WorkerFeedback,
    *,
    person_name: str | None = None,
    candidate: RiskLibraryFeedbackCandidate | None = None,
) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "distribution_id": feedback.distribution_id,
        "distribution_worker_id": feedback.distribution_worker_id,
        "person_id": feedback.person_id,
        "person_name": person_name,
        "plan_id": feedback.plan_id,
        "plan_item_id": feedback.plan_item_id,
        "feedback_type": feedback.feedback_type,
        "content": feedback.content,
        "status": feedback.status,
        "created_at": feedback.created_at,
        "reviewed_by_user_id": feedback.reviewed_by_user_id,
        "reviewed_at": feedback.reviewed_at,
        "review_note": feedback.review_note,
        "candidate_id": candidate.id if candidate else None,
        "candidate_status": candidate.status if candidate else None,
    }


def distribute_daily_work_plan(
    db: Session,
    *,
    plan_id: int,
    target_date: date,
    visible_from: datetime,
    distributed_by_user_id: int,
    person_ids: list[int] | None = None,
) -> dict[str, Any]:
    plan = db.query(DailyWorkPlan).filter(DailyWorkPlan.id == plan_id).first()
    if plan is None:
        raise ValueError("daily_work_plan_not_found")

    site = db.query(Site).filter(Site.id == plan.site_id).first()
    if site is None:
        raise ValueError("site_not_found")

    selected_person_ids = {int(pid) for pid in (person_ids or [])}
    employments = _list_active_employments_for_site(
        db,
        site_code=site.site_code,
        target_date=target_date,
    )
    if selected_person_ids:
        employments = [e for e in employments if e.person_id in selected_person_ids]

    distribution = (
        db.query(DailyWorkPlanDistribution)
        .filter(
            DailyWorkPlanDistribution.plan_id == plan_id,
            DailyWorkPlanDistribution.target_date == target_date,
        )
        .first()
    )
    if distribution is None:
        distribution = DailyWorkPlanDistribution(
            plan_id=plan_id,
            site_id=plan.site_id,
            target_date=target_date,
            visible_from=visible_from,
            distributed_by_user_id=distributed_by_user_id,
            distributed_at=utc_now(),
            status=_resolve_distribution_status(visible_from),
        )
        db.add(distribution)
        db.flush()
    else:
        distribution.visible_from = visible_from
        distribution.distributed_by_user_id = distributed_by_user_id
        distribution.distributed_at = utc_now()
        distribution.status = _resolve_distribution_status(visible_from)

    existing_workers = (
        db.query(DailyWorkPlanDistributionWorker)
        .filter(DailyWorkPlanDistributionWorker.distribution_id == distribution.id)
        .all()
    )
    existing_by_person = {row.person_id: row for row in existing_workers}

    for employment in employments:
        if employment.person_id in existing_by_person:
            worker = existing_by_person[employment.person_id]
            if worker.employment_id is None:
                worker.employment_id = employment.id
            continue
        db.add(
            DailyWorkPlanDistributionWorker(
                distribution_id=distribution.id,
                person_id=employment.person_id,
                employment_id=employment.id,
                access_token=secrets.token_urlsafe(24),
                ack_status="PENDING",
            )
        )

    db.commit()
    worker_count = (
        db.query(DailyWorkPlanDistributionWorker)
        .filter(DailyWorkPlanDistributionWorker.distribution_id == distribution.id)
        .count()
    )
    return _serialize_distribution(distribution, worker_count=worker_count)


def get_distribution_detail(db: Session, *, distribution_id: int) -> DailyWorkPlanDistribution | None:
    return (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.id == distribution_id)
        .first()
    )


def list_recent_distributions_for_site(
    db: Session,
    *,
    site_id: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.site_id == site_id)
        .order_by(DailyWorkPlanDistribution.target_date.desc(), DailyWorkPlanDistribution.id.desc())
        .limit(max(1, limit))
        .all()
    )
    result: list[dict[str, Any]] = []
    for distribution in rows:
        worker_count = (
            db.query(func.count(DailyWorkPlanDistributionWorker.id))
            .filter(DailyWorkPlanDistributionWorker.distribution_id == distribution.id)
            .scalar()
            or 0
        )
        result.append(_serialize_distribution(distribution, worker_count=int(worker_count)))
    return result


def start_distribution_tbm(
    db: Session,
    *,
    distribution_id: int,
    started_by_user_id: int,
) -> dict[str, Any]:
    distribution = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.id == distribution_id)
        .first()
    )
    if distribution is None:
        raise ValueError("distribution_not_found")

    if distribution.tbm_started_at is None:
        distribution.tbm_started_at = utc_now()
        distribution.tbm_started_by_user_id = started_by_user_id
        db.commit()
        db.refresh(distribution)

    return {
        "distribution_id": distribution.id,
        "tbm_started_at": distribution.tbm_started_at,
        "tbm_started_by_user_id": distribution.tbm_started_by_user_id,
        "is_tbm_active": _is_tbm_active(distribution),
    }


def list_distribution_workers(
    db: Session,
    *,
    distribution_id: int,
) -> list[dict[str, Any]]:
    rows = (
        db.query(DailyWorkPlanDistributionWorker, Person)
        .join(Person, Person.id == DailyWorkPlanDistributionWorker.person_id)
        .filter(DailyWorkPlanDistributionWorker.distribution_id == distribution_id)
        .order_by(DailyWorkPlanDistributionWorker.id.asc())
        .all()
    )
    result: list[dict[str, Any]] = []
    for worker, person in rows:
        result.append(
            {
                "id": worker.id,
                "distribution_id": worker.distribution_id,
                "person_id": worker.person_id,
                "person_name": person.name,
                "employment_id": worker.employment_id,
                "access_token": worker.access_token,
                "ack_status": worker.ack_status,
                "viewed_at": worker.viewed_at,
                "start_signed_at": worker.start_signed_at,
                "end_signed_at": worker.end_signed_at,
                "end_status": worker.end_status,
                "issue_flag": worker.issue_flag,
                "signed_at": worker.signed_at,
            }
        )
    return result


def list_worker_visible_distributions(
    db: Session,
    *,
    access_token: str | None = None,
    person_id: int | None = None,
    site_id: int | None = None,
) -> list[dict[str, Any]]:
    if not access_token and not person_id:
        raise ValueError("worker_identity_required")
    now = utc_now()
    rows = (
        db.query(
            DailyWorkPlanDistributionWorker,
            DailyWorkPlanDistribution,
            DailyWorkPlan,
        )
        .join(
            DailyWorkPlanDistribution,
            DailyWorkPlanDistribution.id == DailyWorkPlanDistributionWorker.distribution_id,
        )
        .join(DailyWorkPlan, DailyWorkPlan.id == DailyWorkPlanDistribution.plan_id)
        .filter(DailyWorkPlanDistribution.visible_from <= now)
        .order_by(DailyWorkPlanDistribution.visible_from.desc(), DailyWorkPlanDistribution.id.desc())
    )
    if access_token:
        rows = rows.filter(DailyWorkPlanDistributionWorker.access_token == access_token)
    else:
        rows = rows.filter(DailyWorkPlanDistributionWorker.person_id == person_id)
        if site_id:
            rows = rows.filter(DailyWorkPlanDistribution.site_id == site_id)
    rows = rows.all()
    result: list[dict[str, Any]] = []
    for worker_row, distribution, plan in rows:
        result.append(
            {
                "distribution_id": distribution.id,
                "plan_id": distribution.plan_id,
                "site_id": distribution.site_id,
                "work_date": plan.work_date,
                "visible_from": distribution.visible_from,
                "parent_distribution_id": distribution.parent_distribution_id,
                "is_reassignment": distribution.is_reassignment,
                "reassignment_reason": distribution.reassignment_reason,
                "ack_status": worker_row.ack_status,
                "viewed_at": worker_row.viewed_at,
                "start_signed_at": worker_row.start_signed_at,
                "end_signed_at": worker_row.end_signed_at,
                "end_status": worker_row.end_status,
                "issue_flag": worker_row.issue_flag,
                "signed_at": worker_row.signed_at,
            }
        )
    return result


def _get_distribution_worker_for_identity(
    db: Session,
    *,
    distribution_id: int,
    access_token: str | None = None,
    person_id: int | None = None,
    site_id: int | None = None,
) -> DailyWorkPlanDistributionWorker | None:
    query = db.query(DailyWorkPlanDistributionWorker).filter(
        DailyWorkPlanDistributionWorker.distribution_id == distribution_id
    )
    if access_token:
        query = query.filter(DailyWorkPlanDistributionWorker.access_token == access_token)
    elif person_id:
        query = query.filter(DailyWorkPlanDistributionWorker.person_id == person_id)
        if site_id:
            distribution = (
                db.query(DailyWorkPlanDistribution)
                .filter(DailyWorkPlanDistribution.id == distribution_id)
                .first()
            )
            if distribution is None or distribution.site_id != site_id:
                return None
    else:
        return None
    return query.first()


def get_worker_distribution_detail(
    db: Session,
    *,
    distribution_id: int,
    access_token: str | None = None,
    person_id: int | None = None,
    site_id: int | None = None,
) -> dict[str, Any]:
    worker_row = _get_distribution_worker_for_identity(
        db,
        distribution_id=distribution_id,
        access_token=access_token,
        person_id=person_id,
        site_id=site_id,
    )
    if worker_row is None:
        raise ValueError("distribution_worker_not_found")

    distribution = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.id == worker_row.distribution_id)
        .first()
    )
    if distribution is None:
        raise ValueError("distribution_not_found")

    now = utc_now()
    if distribution.visible_from > now:
        raise ValueError("distribution_not_visible_yet")

    if worker_row.viewed_at is None:
        worker_row.viewed_at = now
        if worker_row.ack_status == "PENDING":
            worker_row.ack_status = "VIEWED"
        db.commit()
        db.refresh(worker_row)

    plan = get_daily_work_plan(db, distribution.plan_id)
    if plan is None:
        raise ValueError("daily_work_plan_not_found")

    enriched_items = []
    for item in plan.items:
        risks = []
        for ref in item.risk_refs:
            if not ref.is_selected:
                continue
            rev = (
                db.query(RiskLibraryItemRevision)
                .filter(RiskLibraryItemRevision.id == ref.risk_revision_id)
                .first()
            )
            if rev:
                risks.append({
                    "risk_factor": rev.risk_factor,
                    "counterplan": rev.countermeasure,
                    "risk_level": rev.risk_r,
                })
        enriched_items.append({
            "plan_item_id": item.id,
            "work_name": item.work_name,
            "work_description": item.work_description,
            "team_label": item.team_label,
            "risks": risks,
        })

    plan_dict = {
        "id": plan.id,
        "site_id": plan.site_id,
        "work_date": plan.work_date,
        "author_user_id": plan.author_user_id,
        "status": plan.status,
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "items": enriched_items,
    }

    return {
        "distribution_worker_id": worker_row.id,
        "distribution_id": distribution.id,
        "parent_distribution_id": distribution.parent_distribution_id,
        "is_reassignment": distribution.is_reassignment,
        "reassignment_reason": distribution.reassignment_reason,
        "plan": plan_dict,
        "ack_status": worker_row.ack_status,
        "viewed_at": worker_row.viewed_at,
        "start_signed_at": worker_row.start_signed_at,
        "end_signed_at": worker_row.end_signed_at,
        "end_status": worker_row.end_status,
        "issue_flag": worker_row.issue_flag,
        "signed_at": worker_row.signed_at,
        "is_completed": bool(worker_row.start_signed_at and worker_row.end_signed_at),
    }


def create_worker_feedback(
    db: Session,
    *,
    distribution_id: int,
    feedback_type: str,
    content: str,
    access_token: str | None = None,
    person_id: int | None = None,
    plan_item_id: int | None = None,
) -> dict[str, Any]:
    worker_row = _get_distribution_worker_for_identity(
        db,
        distribution_id=distribution_id,
        access_token=access_token,
        person_id=person_id,
    )
    if worker_row is None:
        raise ValueError("distribution_worker_not_found")

    distribution = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.id == distribution_id)
        .first()
    )
    if distribution is None:
        raise ValueError("distribution_not_found")

    if plan_item_id is not None:
        plan_item = (
            db.query(DailyWorkPlanItem)
            .filter(
                DailyWorkPlanItem.id == plan_item_id,
                DailyWorkPlanItem.plan_id == distribution.plan_id,
            )
            .first()
        )
        if plan_item is None:
            raise ValueError("plan_item_not_found")

    feedback = WorkerFeedback(
        distribution_id=distribution.id,
        distribution_worker_id=worker_row.id,
        person_id=worker_row.person_id,
        plan_id=distribution.plan_id,
        plan_item_id=plan_item_id,
        feedback_type=(feedback_type or "other").strip().lower(),
        content=content.strip(),
        status="pending",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    person = db.query(Person).filter(Person.id == feedback.person_id).first()
    return _serialize_feedback(feedback, person_name=person.name if person else None)


def list_feedbacks_for_distribution(
    db: Session,
    *,
    distribution_id: int,
) -> list[dict[str, Any]]:
    rows = (
        db.query(WorkerFeedback, Person, RiskLibraryFeedbackCandidate)
        .join(Person, Person.id == WorkerFeedback.person_id)
        .outerjoin(
            RiskLibraryFeedbackCandidate,
            RiskLibraryFeedbackCandidate.feedback_id == WorkerFeedback.id,
        )
        .filter(WorkerFeedback.distribution_id == distribution_id)
        .order_by(WorkerFeedback.created_at.desc(), WorkerFeedback.id.desc())
        .all()
    )
    return [
        _serialize_feedback(feedback, person_name=person.name, candidate=candidate)
        for feedback, person, candidate in rows
    ]


def review_worker_feedback(
    db: Session,
    *,
    feedback_id: int,
    status: str,
    review_note: str | None,
    reviewed_by_user_id: int,
) -> dict[str, Any]:
    feedback = db.query(WorkerFeedback).filter(WorkerFeedback.id == feedback_id).first()
    if feedback is None:
        raise ValueError("feedback_not_found")

    normalized_status = (status or "").strip().lower()
    if normalized_status not in {"pending", "approved", "rejected"}:
        raise ValueError("invalid_feedback_status")

    feedback.status = normalized_status
    feedback.review_note = review_note.strip() if review_note else None
    feedback.reviewed_by_user_id = reviewed_by_user_id
    feedback.reviewed_at = utc_now()
    db.commit()
    db.refresh(feedback)

    return {
        "feedback_id": feedback.id,
        "status": feedback.status,
        "reviewed_by_user_id": reviewed_by_user_id,
        "reviewed_at": feedback.reviewed_at,
        "review_note": feedback.review_note,
    }


def promote_feedback_candidate(
    db: Session,
    *,
    feedback_id: int,
    approved_by_user_id: int,
) -> dict[str, Any]:
    feedback = db.query(WorkerFeedback).filter(WorkerFeedback.id == feedback_id).first()
    if feedback is None:
        raise ValueError("feedback_not_found")

    plan_item = None
    if feedback.plan_item_id is not None:
        plan_item = (
            db.query(DailyWorkPlanItem)
            .filter(DailyWorkPlanItem.id == feedback.plan_item_id)
            .first()
        )

    inferred_countermeasure = None
    if feedback.plan_item_id is not None:
        selected_ref = (
            db.query(DailyWorkPlanItemRiskRef, RiskLibraryItemRevision)
            .join(
                RiskLibraryItemRevision,
                RiskLibraryItemRevision.id == DailyWorkPlanItemRiskRef.risk_revision_id,
            )
            .filter(
                DailyWorkPlanItemRiskRef.plan_item_id == feedback.plan_item_id,
                DailyWorkPlanItemRiskRef.is_selected.is_(True),
            )
            .order_by(
                DailyWorkPlanItemRiskRef.display_order.asc(),
                DailyWorkPlanItemRiskRef.id.asc(),
            )
            .first()
        )
        if selected_ref is not None:
            _, revision = selected_ref
            inferred_countermeasure = revision.countermeasure

    candidate = (
        db.query(RiskLibraryFeedbackCandidate)
        .filter(RiskLibraryFeedbackCandidate.feedback_id == feedback.id)
        .first()
    )
    if candidate is None:
        candidate = RiskLibraryFeedbackCandidate(
            feedback_id=feedback.id,
            inferred_unit_work=plan_item.work_name if plan_item else None,
            inferred_process=plan_item.work_description if plan_item else None,
            inferred_risk_factor=feedback.content,
            inferred_countermeasure=inferred_countermeasure,
            source_distribution_id=feedback.distribution_id,
            source_plan_item_id=feedback.plan_item_id,
            status="pending",
            approved_by_user_id=approved_by_user_id,
            approved_at=utc_now(),
        )
        db.add(candidate)
    else:
        candidate.inferred_unit_work = plan_item.work_name if plan_item else candidate.inferred_unit_work
        candidate.inferred_process = (
            plan_item.work_description if plan_item else candidate.inferred_process
        )
        candidate.inferred_risk_factor = feedback.content
        candidate.inferred_countermeasure = inferred_countermeasure or candidate.inferred_countermeasure
        candidate.approved_by_user_id = approved_by_user_id
        candidate.approved_at = utc_now()

    if feedback.status == "pending":
        feedback.status = "approved"
        feedback.reviewed_by_user_id = approved_by_user_id
        feedback.reviewed_at = utc_now()

    db.commit()
    db.refresh(candidate)
    return {
        "feedback_id": feedback.id,
        "candidate_id": candidate.id,
        "status": candidate.status,
        "inferred_unit_work": candidate.inferred_unit_work,
        "inferred_process": candidate.inferred_process,
        "inferred_risk_factor": candidate.inferred_risk_factor,
        "inferred_countermeasure": candidate.inferred_countermeasure,
        "created_at": candidate.created_at,
    }


def create_reassignment_distribution(
    db: Session,
    *,
    distribution_id: int,
    person_ids: list[int],
    new_work_name: str,
    new_work_description: str,
    team_label: str | None,
    selected_risk_revision_ids: list[int],
    reason: str,
    reassigned_by_user_id: int,
) -> dict[str, Any]:
    source_distribution = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.id == distribution_id)
        .first()
    )
    if source_distribution is None:
        raise ValueError("distribution_not_found")

    selected_person_ids = sorted({int(person_id) for person_id in person_ids})
    if not selected_person_ids:
        raise ValueError("person_ids_required")

    source_workers = (
        db.query(DailyWorkPlanDistributionWorker)
        .filter(
            DailyWorkPlanDistributionWorker.distribution_id == distribution_id,
            DailyWorkPlanDistributionWorker.person_id.in_(selected_person_ids),
        )
        .all()
    )
    if len(source_workers) != len(selected_person_ids):
        raise ValueError("distribution_workers_not_found")

    source_plan = db.query(DailyWorkPlan).filter(DailyWorkPlan.id == source_distribution.plan_id).first()
    if source_plan is None:
        raise ValueError("daily_work_plan_not_found")

    reassignment_plan = DailyWorkPlan(
        site_id=source_plan.site_id,
        work_date=source_distribution.target_date,
        author_user_id=reassigned_by_user_id,
        status="DRAFT",
    )
    db.add(reassignment_plan)
    db.flush()

    plan_item = DailyWorkPlanItem(
        plan_id=reassignment_plan.id,
        work_name=new_work_name.strip(),
        work_description=new_work_description.strip(),
        team_label=team_label.strip() if team_label else None,
        leader_person_id=None,
    )
    db.add(plan_item)
    db.flush()

    revision_ids = sorted({int(revision_id) for revision_id in selected_risk_revision_ids})
    for order, revision_id in enumerate(revision_ids, start=1):
        revision = (
            db.query(RiskLibraryItemRevision)
            .filter(
                RiskLibraryItemRevision.id == revision_id,
                RiskLibraryItemRevision.is_current.is_(True),
            )
            .first()
        )
        if revision is None:
            continue
        db.add(
            DailyWorkPlanItemRiskRef(
                plan_item_id=plan_item.id,
                risk_item_id=revision.item_id,
                risk_revision_id=revision.id,
                link_type="ADOPTED",
                is_selected=True,
                source_rule="REASSIGNMENT",
                score=0.0,
                display_order=order,
            )
        )

    now = utc_now()
    reassignment_distribution = DailyWorkPlanDistribution(
        plan_id=reassignment_plan.id,
        site_id=source_distribution.site_id,
        target_date=source_distribution.target_date,
        visible_from=now,
        distributed_by_user_id=reassigned_by_user_id,
        distributed_at=now,
        status="VISIBLE",
        tbm_started_at=source_distribution.tbm_started_at,
        tbm_started_by_user_id=source_distribution.tbm_started_by_user_id,
        parent_distribution_id=source_distribution.id,
        is_reassignment=True,
        reassignment_reason=reason.strip(),
        reassigned_by_user_id=reassigned_by_user_id,
        reassigned_at=now,
    )
    db.add(reassignment_distribution)
    db.flush()

    for source_worker in source_workers:
        db.add(
            DailyWorkPlanDistributionWorker(
                distribution_id=reassignment_distribution.id,
                person_id=source_worker.person_id,
                employment_id=source_worker.employment_id,
                access_token=secrets.token_urlsafe(24),
                ack_status="PENDING",
            )
        )

    db.commit()
    worker_count = (
        db.query(func.count(DailyWorkPlanDistributionWorker.id))
        .filter(DailyWorkPlanDistributionWorker.distribution_id == reassignment_distribution.id)
        .scalar()
        or 0
    )
    return {
        "source_distribution_id": source_distribution.id,
        "reassignment_distribution_id": reassignment_distribution.id,
        "reassignment_plan_id": reassignment_plan.id,
        "worker_count": int(worker_count),
        "is_reassignment": True,
        "reassignment_reason": reassignment_distribution.reassignment_reason or "",
    }


def get_worker_safety_record(
    db: Session,
    *,
    person_id: int,
) -> dict[str, Any]:
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise ValueError("person_not_found")

    employment = (
        db.query(Employment)
        .filter(Employment.person_id == person_id)
        .order_by(Employment.is_active.desc(), Employment.id.desc())
        .first()
    )
    site = None
    if employment and employment.site_code:
        site = db.query(Site).filter(Site.site_code == employment.site_code).first()

    worker_rows = (
        db.query(DailyWorkPlanDistributionWorker, DailyWorkPlanDistribution, DailyWorkPlan)
        .join(
            DailyWorkPlanDistribution,
            DailyWorkPlanDistribution.id == DailyWorkPlanDistributionWorker.distribution_id,
        )
        .join(DailyWorkPlan, DailyWorkPlan.id == DailyWorkPlanDistribution.plan_id)
        .filter(DailyWorkPlanDistributionWorker.person_id == person_id)
        .order_by(DailyWorkPlanDistribution.distributed_at.desc(), DailyWorkPlanDistribution.id.desc())
        .all()
    )

    distributions: list[dict[str, Any]] = []
    for worker_row, distribution, plan in worker_rows:
        items: list[dict[str, Any]] = []
        for item in plan.items:
            risks: list[dict[str, Any]] = []
            for ref in item.risk_refs:
                if not ref.is_selected:
                    continue
                revision = (
                    db.query(RiskLibraryItemRevision)
                    .filter(RiskLibraryItemRevision.id == ref.risk_revision_id)
                    .first()
                )
                if revision is None:
                    continue
                risks.append(
                    {
                        "risk_revision_id": revision.id,
                        "risk_factor": revision.risk_factor,
                        "counterplan": revision.countermeasure,
                        "risk_level": revision.risk_r,
                    }
                )
            items.append(
                {
                    "plan_item_id": item.id,
                    "work_name": item.work_name,
                    "work_description": item.work_description,
                    "team_label": item.team_label,
                    "risks": risks,
                }
            )
        distributions.append(
            {
                "distribution_id": distribution.id,
                "parent_distribution_id": distribution.parent_distribution_id,
                "is_reassignment": distribution.is_reassignment,
                "reassignment_reason": distribution.reassignment_reason,
                "target_date": distribution.target_date,
                "visible_from": distribution.visible_from,
                "distributed_at": distribution.distributed_at,
                "ack_status": worker_row.ack_status,
                "viewed_at": worker_row.viewed_at,
                "start_signed_at": worker_row.start_signed_at,
                "end_signed_at": worker_row.end_signed_at,
                "end_status": worker_row.end_status,
                "issue_flag": worker_row.issue_flag,
                "items": items,
            }
        )

    feedback_rows = (
        db.query(WorkerFeedback, RiskLibraryFeedbackCandidate)
        .outerjoin(
            RiskLibraryFeedbackCandidate,
            RiskLibraryFeedbackCandidate.feedback_id == WorkerFeedback.id,
        )
        .filter(WorkerFeedback.person_id == person_id)
        .order_by(WorkerFeedback.created_at.desc(), WorkerFeedback.id.desc())
        .all()
    )
    feedbacks = [
        _serialize_feedback(feedback, person_name=person.name, candidate=candidate)
        for feedback, candidate in feedback_rows
    ]

    return {
        "person": {
            "person_id": person.id,
            "name": person.name,
            "phone_mobile": person.phone_mobile,
            "site_id": site.id if site else None,
            "site_name": site.site_name if site else None,
            "employment_id": employment.id if employment else None,
            "department_name": employment.department_name if employment else None,
            "position_name": employment.position_name if employment else None,
        },
        "distributions": distributions,
        "feedbacks": feedbacks,
    }


def _validate_signature_payload(*, signature_data: str, signature_mime: str) -> tuple[str, int]:
    if signature_mime != "image/png":
        raise ValueError("invalid_signature_mime")
    if not signature_data.startswith(PNG_DATA_PREFIX):
        raise ValueError("invalid_signature_prefix")
    encoded = signature_data[len(PNG_DATA_PREFIX) :]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("invalid_signature_base64")
    size = len(raw)
    if size < WORKER_SIGNATURE_MIN_BYTES:
        raise ValueError("signature_too_small")
    if size > WORKER_SIGNATURE_MAX_BYTES:
        raise ValueError("signature_too_large")
    signature_hash = hashlib.sha256(raw).hexdigest()
    return signature_hash, size


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def ping_site_admin_presence(
    db: Session,
    *,
    user_id: int,
    site_id: int,
    lat: float | None,
    lng: float | None,
) -> SiteAdminPresence:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise ValueError("user_not_found")
    if user.role not in ADMIN_ROLES:
        raise ValueError("user_not_admin")

    presence = (
        db.query(SiteAdminPresence)
        .filter(SiteAdminPresence.user_id == user_id, SiteAdminPresence.site_id == site_id)
        .first()
    )
    now = utc_now()
    if presence is None:
        presence = SiteAdminPresence(
            user_id=user_id,
            site_id=site_id,
            lat=lat,
            lng=lng,
            last_seen_at=now,
            updated_at=now,
        )
        db.add(presence)
    else:
        presence.lat = lat
        presence.lng = lng
        presence.last_seen_at = now
        presence.updated_at = now
    db.commit()
    db.refresh(presence)
    return presence


def _validate_worker_sign_context(
    db: Session,
    *,
    worker_row: DailyWorkPlanDistributionWorker,
    lat: float,
    lng: float,
) -> None:
    distribution = (
        db.query(DailyWorkPlanDistribution)
        .filter(DailyWorkPlanDistribution.id == worker_row.distribution_id)
        .first()
    )
    if distribution is None:
        raise ValueError("distribution_not_found")

    now = utc_now()
    if distribution.visible_from > now:
        raise ValueError("distribution_not_visible_yet")
    if distribution.tbm_started_at is None:
        raise ValueError("tbm_not_started")

    if settings.test_persona_mode:
        return

    site = db.query(Site).filter(Site.id == distribution.site_id).first()
    if site is None:
        raise ValueError("site_not_found")
    if site.latitude is None or site.longitude is None:
        raise ValueError("site_location_not_configured")

    if site.allowed_radius_m is None:
        raise ValueError("site_location_not_configured")
    allowed_radius_m = int(site.allowed_radius_m)

    dist_m = _haversine_m(float(lat), float(lng), float(site.latitude), float(site.longitude))
    if dist_m > float(allowed_radius_m):
        raise ValueError("worker_out_of_site_radius")

    threshold = now - timedelta(minutes=ADMIN_PRESENCE_WINDOW_MINUTES)
    active_admin_exists = (
        db.query(SiteAdminPresence.id)
        .join(User, User.id == SiteAdminPresence.user_id)
        .filter(
            SiteAdminPresence.site_id == distribution.site_id,
            SiteAdminPresence.last_seen_at >= threshold,
            User.role.in_(tuple(ADMIN_ROLES)),
            User.is_active.is_(True),
        )
        .first()
        is not None
    )
    if not active_admin_exists:
        raise ValueError("active_admin_presence_not_found")


def sign_worker_daily_work_plan(
    db: Session,
    *,
    distribution_id: int,
    access_token: str | None = None,
    person_id: int | None = None,
    signature_data: str,
    signature_mime: str,
    lat: float,
    lng: float,
) -> dict[str, Any]:
    worker_row = _get_distribution_worker_for_identity(
        db,
        distribution_id=distribution_id,
        access_token=access_token,
        person_id=person_id,
    )
    if worker_row is None:
        raise ValueError("distribution_worker_not_found")
    if worker_row.start_signed_at is not None:
        raise ValueError("already_signed")

    signature_hash, _ = _validate_signature_payload(
        signature_data=signature_data,
        signature_mime=signature_mime,
    )
    _validate_worker_sign_context(db, worker_row=worker_row, lat=lat, lng=lng)

    now = utc_now()
    if worker_row.viewed_at is None:
        worker_row.viewed_at = now
    worker_row.start_signed_at = now
    worker_row.signed_at = now  # 기존 호환 필드 유지
    worker_row.signature_data = signature_data  # 기존 호환 필드 유지(시작 서명)
    worker_row.signature_mime = signature_mime
    worker_row.signature_hash = signature_hash
    worker_row.start_signature_data = signature_data
    worker_row.start_signature_mime = signature_mime
    worker_row.start_signature_hash = signature_hash
    worker_row.issue_flag = False
    worker_row.end_status = None
    worker_row.end_signed_at = None
    worker_row.ack_status = "START_SIGNED"
    db.commit()
    db.refresh(worker_row)
    return {
        "distribution_worker_id": worker_row.id,
        "distribution_id": worker_row.distribution_id,
        "ack_status": worker_row.ack_status,
        "viewed_at": worker_row.viewed_at,
        "start_signed_at": worker_row.start_signed_at,
        "end_signed_at": worker_row.end_signed_at,
        "end_status": worker_row.end_status,
        "issue_flag": worker_row.issue_flag,
        "signed_at": worker_row.signed_at,
        "signature_hash": worker_row.signature_hash,
        "message": "안전하지 않으면 작업하지 않습니다. 위험한 상황은 바로 신고바랍니다.",
    }


def sign_worker_daily_work_plan_end(
    db: Session,
    *,
    distribution_id: int,
    access_token: str | None = None,
    person_id: int | None = None,
    end_status: str,
    signature_data: str,
    signature_mime: str,
    lat: float,
    lng: float,
) -> dict[str, Any]:
    worker_row = _get_distribution_worker_for_identity(
        db,
        distribution_id=distribution_id,
        access_token=access_token,
        person_id=person_id,
    )
    if worker_row is None:
        raise ValueError("distribution_worker_not_found")
    if worker_row.start_signed_at is None:
        raise ValueError("start_signature_required")
    if worker_row.end_signed_at is not None:
        raise ValueError("already_end_signed")
    if end_status not in END_STATUSES:
        raise ValueError("invalid_end_status")

    signature_hash, _ = _validate_signature_payload(
        signature_data=signature_data,
        signature_mime=signature_mime,
    )
    _validate_worker_sign_context(db, worker_row=worker_row, lat=lat, lng=lng)

    now = utc_now()
    if worker_row.viewed_at is None:
        worker_row.viewed_at = now
    worker_row.end_signed_at = now
    worker_row.end_status = end_status
    worker_row.issue_flag = end_status == "ISSUE"
    worker_row.end_signature_data = signature_data
    worker_row.end_signature_mime = signature_mime
    worker_row.end_signature_hash = signature_hash
    worker_row.ack_status = "COMPLETED"

    db.commit()
    db.refresh(worker_row)
    return {
        "distribution_worker_id": worker_row.id,
        "distribution_id": worker_row.distribution_id,
        "ack_status": worker_row.ack_status,
        "viewed_at": worker_row.viewed_at,
        "start_signed_at": worker_row.start_signed_at,
        "end_signed_at": worker_row.end_signed_at,
        "end_status": worker_row.end_status,
        "issue_flag": worker_row.issue_flag,
        "signed_at": worker_row.signed_at,
        "signature_hash": worker_row.end_signature_hash or "",
    }


def _list_daily_work_plans_for_site_date(
    db: Session,
    *,
    site_id: int,
    work_date: date,
) -> list[DailyWorkPlan]:
    return (
        db.query(DailyWorkPlan)
        .filter(
            DailyWorkPlan.site_id == site_id,
            DailyWorkPlan.work_date == work_date,
        )
        .order_by(DailyWorkPlan.id.asc())
        .all()
    )


def _get_or_create_workplan_instance(
    db: Session,
    *,
    site_id: int,
    work_date: date,
) -> DocumentInstance:
    instance = (
        db.query(DocumentInstance)
        .filter(
            DocumentInstance.site_id == site_id,
            DocumentInstance.document_type_code == "WORKPLAN_DAILY",
            DocumentInstance.period_basis == "WORKPLAN_DAY",
            DocumentInstance.period_start == work_date,
            DocumentInstance.period_end == work_date,
        )
        .first()
    )
    if instance is not None:
        return instance

    instance = DocumentInstance(
        site_id=site_id,
        document_type_code="WORKPLAN_DAILY",
        period_start=work_date,
        period_end=work_date,
        generation_anchor_date=work_date,
        due_date=work_date,
        status=DocumentInstanceStatus.GENERATED,
        status_reason="WORKPLAN_ASSEMBLED",
        selected_requirement_id=None,
        workflow_status=WorkflowStatus.NOT_SUBMITTED,
        period_basis="WORKPLAN_DAY",
        rule_is_required=True,
        cycle_code=None,
        rule_generation_rule=None,
        rule_generation_value=None,
        rule_due_offset_days=None,
        resolved_from="WORKPLAN",
        resolved_cycle_source="none",
        master_cycle_id=None,
        master_cycle_code=None,
        override_cycle_id=None,
        override_cycle_code=None,
        error_message=None,
    )
    db.add(instance)
    db.flush()
    return instance


def _ensure_draft_document_for_instance(
    db: Session,
    *,
    instance: DocumentInstance,
    submitter_user_id: int,
) -> Document:
    document = db.query(Document).filter(Document.instance_id == instance.id).first()
    if document is not None:
        return document

    document = Document(
        document_no=f"WP-{instance.site_id}-{instance.period_start.isoformat()}",
        title=f"[WORKPLAN] {instance.period_start.isoformat()}",
        document_type=instance.document_type_code,
        site_id=instance.site_id,
        submitter_user_id=submitter_user_id,
        current_status=DocumentStatus.DRAFT,
        description="DailyWorkPlan assemble draft orchestration record",
        period_start=instance.period_start,
        period_end=instance.period_end,
        due_date=instance.due_date,
        source_type=DocumentSourceType.WORKPLAN_ASSEMBLE,
        version_no=1,
        instance_id=instance.id,
    )
    db.add(document)
    db.flush()
    return document


def assemble_daily_work_plan_document(
    db: Session,
    *,
    site_id: int,
    work_date: date,
    assembled_by_user_id: int,
) -> dict[str, Any]:
    plans = _list_daily_work_plans_for_site_date(db, site_id=site_id, work_date=work_date)
    if not plans:
        raise ValueError("daily_work_plan_not_found")

    plan_ids = [p.id for p in plans]
    item_rows = (
        db.query(DailyWorkPlanItem.id)
        .join(DailyWorkPlan, DailyWorkPlan.id == DailyWorkPlanItem.plan_id)
        .filter(
            DailyWorkPlan.site_id == site_id,
            DailyWorkPlan.work_date == work_date,
        )
        .all()
    )
    item_ids = [int(row.id) for row in item_rows]

    adopted_ref_count = 0
    if item_ids:
        adopted_ref_count = (
            db.query(DailyWorkPlanItemRiskRef)
            .filter(
                DailyWorkPlanItemRiskRef.plan_item_id.in_(item_ids),
                DailyWorkPlanItemRiskRef.is_selected.is_(True),
                DailyWorkPlanItemRiskRef.link_type == "ADOPTED",
            )
            .count()
        )

    instance = _get_or_create_workplan_instance(db, site_id=site_id, work_date=work_date)
    document = _ensure_draft_document_for_instance(
        db,
        instance=instance,
        submitter_user_id=assembled_by_user_id,
    )

    existing_links = (
        db.query(DailyWorkPlanDocumentLink)
        .filter(
            DailyWorkPlanDocumentLink.instance_id == instance.id,
            DailyWorkPlanDocumentLink.plan_id.in_(plan_ids),
        )
        .all()
    )
    existing_plan_ids = {link.plan_id for link in existing_links}

    links_upserted = 0
    for plan_id in plan_ids:
        if plan_id in existing_plan_ids:
            continue
        db.add(
            DailyWorkPlanDocumentLink(
                instance_id=instance.id,
                plan_id=plan_id,
                assembled_by_user_id=assembled_by_user_id,
                assembled_at=utc_now(),
            )
        )
        links_upserted += 1

    # assemble은 제출 단계가 아니므로 workflow_status를 변경하지 않는다.
    db.commit()
    return {
        "site_id": site_id,
        "work_date": work_date,
        "document_type_code": instance.document_type_code,
        "instance_id": instance.id,
        "document_id": document.id,
        "document_status": document.current_status,
        "workflow_status": instance.workflow_status,
        "plan_count": len(plan_ids),
        "item_count": len(item_ids),
        "adopted_risk_revision_count": adopted_ref_count,
        "links_upserted": links_upserted,
    }


def get_assembled_document_for_day(
    db: Session,
    *,
    site_id: int,
    work_date: date,
) -> dict[str, Any]:
    instance = (
        db.query(DocumentInstance)
        .filter(
            DocumentInstance.site_id == site_id,
            DocumentInstance.document_type_code == "WORKPLAN_DAILY",
            DocumentInstance.period_basis == "WORKPLAN_DAY",
            DocumentInstance.period_start == work_date,
            DocumentInstance.period_end == work_date,
        )
        .first()
    )
    if instance is None:
        raise ValueError("assembled_document_not_found")

    document = db.query(Document).filter(Document.instance_id == instance.id).first()
    if document is None:
        raise ValueError("assembled_document_not_found")

    links = (
        db.query(DailyWorkPlanDocumentLink)
        .filter(DailyWorkPlanDocumentLink.instance_id == instance.id)
        .order_by(DailyWorkPlanDocumentLink.plan_id.asc())
        .all()
    )
    plan_ids = [link.plan_id for link in links]

    plan_rows: list[dict[str, Any]] = []
    for plan_id in plan_ids:
        item_rows = db.query(DailyWorkPlanItem.id).filter(DailyWorkPlanItem.plan_id == plan_id).all()
        item_ids = [int(row.id) for row in item_rows]
        adopted_count = 0
        if item_ids:
            adopted_count = (
                db.query(DailyWorkPlanItemRiskRef)
                .filter(
                    DailyWorkPlanItemRiskRef.plan_item_id.in_(item_ids),
                    DailyWorkPlanItemRiskRef.is_selected.is_(True),
                    DailyWorkPlanItemRiskRef.link_type == "ADOPTED",
                )
                .count()
            )
        plan_rows.append(
            {
                "plan_id": plan_id,
                "item_count": len(item_ids),
                "adopted_risk_revision_count": adopted_count,
            }
        )

    return {
        "site_id": site_id,
        "work_date": work_date,
        "instance_id": instance.id,
        "document_id": document.id,
        "document_type_code": instance.document_type_code,
        "workflow_status": instance.workflow_status,
        "plans": plan_rows,
    }
