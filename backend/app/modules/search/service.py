from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.modules.risk_library.models import (
    RiskAssessmentSiteRole,
    RiskLibraryContractor,
    RiskLibraryItem,
    RiskLibraryItemContractor,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
    RiskLibrarySiteAssignment,
)
from app.modules.sites.models import Site


EVALUATION_METHODS = (
    "회사 4×5",
    "도급사 4×4",
    "도급사 4×3",
    "도급사 3×3",
    "상·중·하 직접판정",
)
DEFAULT_EVALUATION_METHOD = EVALUATION_METHODS[0]

WEAK_TOKENS = {
    "작업",
    "위험",
    "위험요인",
    "공사",
    "내용",
    "관련",
}

STRONG_TOKENS = {
    "배관",
    "배선",
    "감전",
    "추락",
    "전주",
    "슬라브",
    "천장",
    "벽체",
    "사다리",
    "협착",
    "낙하",
}

SPECIAL_TOKENS = {
    "천장슬라브": {"천장슬라브", "슬라브", "천장"},
    "전선관": {"전선관", "배관"},
    "벽체 배관": {"벽체", "배관"},
    "천장슬라브 배관": {"천장슬라브", "슬라브", "배관"},
}


def normalize_contractor_key(value: str | None) -> str:
    text = (value or "").strip().lower()
    for token in ("주식회사", "(주)", "㈜"):
        text = text.replace(token, "")
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _risk_grade(risk_r: int | None) -> str:
    score = int(risk_r or 0)
    if score <= 0:
        return ""
    if score <= 8:
        return "하"
    if score <= 15:
        return "중"
    return "상"


def convert_risk_score(
    risk_f: int | None,
    risk_s: int | None,
    *,
    evaluation_method: str,
) -> dict[str, int | str | None]:
    frequency = int(risk_f or 0)
    severity = int(risk_s or 0)
    base_score = frequency * severity if frequency and severity else None
    grade = _risk_grade(base_score)

    if evaluation_method == "상·중·하 직접판정":
        return {"display_f": None, "display_s": None, "display_r": None, "risk_grade": grade}

    display_f = frequency or None
    display_s = severity or None
    if evaluation_method == "도급사 4×4" and severity:
        display_s = (1, 2, 3, 3, 4)[min(max(severity, 1), 5) - 1]
    elif evaluation_method == "도급사 4×3" and severity:
        display_s = (1, 1, 2, 3, 3)[min(max(severity, 1), 5) - 1]
    elif evaluation_method == "도급사 3×3":
        if frequency:
            display_f = (1, 2, 2, 3)[min(max(frequency, 1), 4) - 1]
        if severity:
            display_s = (1, 1, 2, 3, 3)[min(max(severity, 1), 5) - 1]

    display_r = display_f * display_s if display_f and display_s else None
    return {
        "display_f": display_f,
        "display_s": display_s,
        "display_r": display_r,
        "risk_grade": grade,
    }


def _contractor_profile(
    db: Session,
    contractor_name: str | None,
) -> tuple[str | None, str | None, str]:
    contractor_key = normalize_contractor_key(contractor_name)
    if not contractor_key:
        return None, None, DEFAULT_EVALUATION_METHOD
    row = (
        db.query(RiskLibraryContractor)
        .filter(
            RiskLibraryContractor.contractor_key == contractor_key,
            RiskLibraryContractor.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        return contractor_key, (contractor_name or "").strip() or None, DEFAULT_EVALUATION_METHOD
    method = row.evaluation_method if row.evaluation_method in EVALUATION_METHODS else DEFAULT_EVALUATION_METHOD
    return row.contractor_key, row.contractor_name, method


def list_risk_library_contractors(db: Session) -> list[dict[str, str]]:
    profiles = {
        row.contractor_key: row
        for row in db.query(RiskLibraryContractor)
        .filter(RiskLibraryContractor.is_active.is_(True))
        .all()
    }
    names_by_key: dict[str, str] = {}
    for (name,) in (
        db.query(Site.contractor_name)
        .filter(Site.contractor_name.isnot(None))
        .distinct()
        .all()
    ):
        cleaned = (name or "").strip()
        key = normalize_contractor_key(cleaned)
        if key and (key not in names_by_key or len(cleaned) < len(names_by_key[key])):
            names_by_key[key] = cleaned
    for key, profile in profiles.items():
        names_by_key[key] = profile.contractor_name

    return [
        {
            "contractor_key": key,
            "contractor_name": names_by_key[key],
            "evaluation_method": (
                profiles[key].evaluation_method
                if key in profiles and profiles[key].evaluation_method in EVALUATION_METHODS
                else DEFAULT_EVALUATION_METHOD
            ),
        }
        for key in sorted(names_by_key, key=lambda item: names_by_key[item])
    ]


def get_risk_assessment_designation(
    db: Session,
    *,
    site_id: int | None,
    can_edit: bool = False,
) -> dict[str, Any] | None:
    if site_id is None:
        return None
    site = db.query(Site).filter(Site.id == int(site_id)).first()
    if site is None:
        return None
    role = (
        db.query(RiskAssessmentSiteRole)
        .filter(RiskAssessmentSiteRole.site_id == int(site_id))
        .first()
    )
    return {
        "site_id": site.id,
        "site_name": site.site_name,
        "inspector_name": role.inspector_name if role else None,
        "verifier_name": role.verifier_name if role else None,
        "appointed_on": role.appointed_on if role else None,
        "note": role.note if role else None,
        "can_edit": bool(can_edit),
    }


def upsert_risk_assessment_designation(
    db: Session,
    *,
    site_id: int,
    inspector_name: str | None,
    verifier_name: str | None,
    appointed_on,
    note: str | None,
    updated_by_user_id: int,
) -> dict[str, Any]:
    role = (
        db.query(RiskAssessmentSiteRole)
        .filter(RiskAssessmentSiteRole.site_id == int(site_id))
        .first()
    )
    if role is None:
        role = RiskAssessmentSiteRole(site_id=int(site_id))
        db.add(role)
    role.inspector_name = inspector_name
    role.verifier_name = verifier_name
    role.appointed_on = appointed_on
    role.note = note
    role.updated_by_user_id = int(updated_by_user_id)
    role.updated_at = utc_now()
    db.commit()
    return get_risk_assessment_designation(db, site_id=site_id, can_edit=True) or {}


def upsert_risk_library_site_assignment(
    db: Session,
    *,
    site_id: int,
    risk_item_id: int,
    improvement_owner_name: str | None,
    improvement_verifier_name: str | None,
    updated_by_user_id: int,
) -> dict[str, Any]:
    risk_item = (
        db.query(RiskLibraryItem)
        .filter(RiskLibraryItem.id == int(risk_item_id), RiskLibraryItem.is_active.is_(True))
        .first()
    )
    if risk_item is None:
        raise ValueError("risk_item_not_found")
    row = (
        db.query(RiskLibrarySiteAssignment)
        .filter(
            RiskLibrarySiteAssignment.site_id == int(site_id),
            RiskLibrarySiteAssignment.risk_item_id == int(risk_item_id),
        )
        .first()
    )
    if row is None:
        row = RiskLibrarySiteAssignment(site_id=int(site_id), risk_item_id=int(risk_item_id))
        db.add(row)
    row.improvement_owner_name = improvement_owner_name
    row.improvement_verifier_name = improvement_verifier_name
    row.updated_by_user_id = int(updated_by_user_id)
    row.updated_at = utc_now()
    db.commit()
    return {
        "site_id": int(site_id),
        "risk_item_id": int(risk_item_id),
        "improvement_owner_name": row.improvement_owner_name,
        "improvement_verifier_name": row.improvement_verifier_name,
    }


def normalize_query(query: str) -> str:
    normalized = (query or "").strip()
    normalized = re.sub(r"[\t\r\n]+", " ", normalized)
    normalized = re.sub(r"[^\w\s가-힣-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.lower()


def tokenize_query(query: str) -> list[str]:
    normalized = normalize_query(query)
    if not normalized:
        return []
    raw_tokens = [tok for tok in re.split(r"[\s,./()\-:;|]+", normalized) if tok]
    unique_tokens: list[str] = []
    seen: set[str] = set()
    for token in raw_tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    return unique_tokens


def classify_search_mode(query: str, explicit_mode: str | None) -> str:
    mode = (explicit_mode or "").strip().lower()
    if mode in {"quick", "nlp_beta"}:
        return mode
    normalized = normalize_query(query)
    # 문장이 길거나 토큰이 많은 경우를 nlp_beta 후보로 판단 가능하나,
    # 기본값은 quick으로 유지해 예측 가능성을 보장한다.
    if len(normalized) > 40 and len(tokenize_query(normalized)) >= 5:
        return "quick"
    return "quick"


@dataclass
class _ScoredResult:
    row: RiskLibraryItemRevision
    score: float
    matched_tokens: list[str]
    matched_fields: list[str]


def _token_weight(token: str, mode: str) -> float:
    if token in STRONG_TOKENS:
        return 2.0 if mode == "quick" else 4.0
    if token in WEAK_TOKENS:
        return 0.6 if mode == "quick" else 1.0
    return 1.2 if mode == "quick" else 2.0


def _expand_token(token: str) -> set[str]:
    expanded = {token}
    if token in SPECIAL_TOKENS:
        expanded.update(SPECIAL_TOKENS[token])
    return expanded


def _score_text_match(text_value: str, token: str, *, field_name: str, mode: str) -> tuple[float, bool]:
    if not text_value:
        return 0.0, False
    value = (text_value or "").lower()
    if token not in value:
        return 0.0, False

    base = _token_weight(token, mode)
    if field_name == "keyword":
        score = base + (2.0 if token in STRONG_TOKENS else 1.0)
    elif field_name in {"process", "risk_factor"}:
        score = base + (1.2 if token in STRONG_TOKENS else 0.8)
    elif field_name == "counterplan":
        score = base + 0.5
    elif field_name in {"unit_work", "work_category", "trade_type"}:
        score = base + 0.6
    else:
        score = base

    if mode == "quick":
        score *= 0.9
    return score, True


def _collect_fields(row: RiskLibraryItemRevision) -> dict[str, str]:
    return {
        "unit_work": row.unit_work or "",
        "work_category": row.work_category or "",
        "trade_type": row.trade_type or "",
        "process": row.process or "",
        "risk_factor": row.risk_factor or "",
        "counterplan": row.countermeasure or "",
        "note": row.note or "",
        "source_file": row.source_file or "",
        "source_sheet": row.source_sheet or "",
        "source_page_or_section": row.source_page_or_section or "",
    }


def _active_revision_query(
    db: Session,
    *,
    contractor_key: str | None = None,
    contractor_scope_required: bool = False,
):
    query_obj = (
        db.query(RiskLibraryItemRevision)
        .join(RiskLibraryItem, RiskLibraryItem.id == RiskLibraryItemRevision.item_id)
        .filter(
            RiskLibraryItemRevision.is_current.is_(True),
            RiskLibraryItem.is_active.is_(True),
        )
    )
    if contractor_key:
        assigned_to_contractor = exists().where(
            RiskLibraryItemContractor.risk_item_id == RiskLibraryItem.id,
            RiskLibraryItemContractor.contractor_id == RiskLibraryContractor.id,
            RiskLibraryContractor.contractor_key == contractor_key,
            RiskLibraryContractor.is_active.is_(True),
        )
        query_obj = query_obj.filter(
            or_(RiskLibraryItem.is_common.is_(True), assigned_to_contractor)
        )
    elif contractor_scope_required:
        query_obj = query_obj.filter(RiskLibraryItem.is_common.is_(True))
    return query_obj


def risk_item_available_for_contractor(
    db: Session,
    *,
    risk_item_id: int,
    contractor_name: str | None,
    contractor_scope_required: bool = False,
) -> bool:
    contractor_key = normalize_contractor_key(contractor_name)
    query_obj = db.query(RiskLibraryItem.id).filter(
        RiskLibraryItem.id == int(risk_item_id),
        RiskLibraryItem.is_active.is_(True),
    )
    if contractor_key:
        assigned_to_contractor = exists().where(
            RiskLibraryItemContractor.risk_item_id == RiskLibraryItem.id,
            RiskLibraryItemContractor.contractor_id == RiskLibraryContractor.id,
            RiskLibraryContractor.contractor_key == contractor_key,
            RiskLibraryContractor.is_active.is_(True),
        )
        query_obj = query_obj.filter(
            or_(RiskLibraryItem.is_common.is_(True), assigned_to_contractor)
        )
    elif contractor_scope_required:
        query_obj = query_obj.filter(RiskLibraryItem.is_common.is_(True))
    return query_obj.first() is not None


def _apply_unit_work_risk_type_sql(
    query_obj,
    *,
    unit_work_filter: str,
    risk_type_filter: str,
):
    """Python `in` on lowercased concat — SQLite instr + lower 로 동일 의미."""
    if unit_work_filter:
        unit_concat = func.lower(
            func.concat_ws(
                " ",
                func.coalesce(RiskLibraryItemRevision.unit_work, ""),
                RiskLibraryItemRevision.work_category,
                RiskLibraryItemRevision.trade_type,
            )
        )
        query_obj = query_obj.filter(func.instr(unit_concat, unit_work_filter) > 0)
    if risk_type_filter:
        risk_concat = func.lower(
            func.concat_ws(
                " ",
                RiskLibraryItemRevision.risk_factor,
                RiskLibraryItemRevision.countermeasure,
            )
        )
        query_obj = query_obj.filter(func.instr(risk_concat, risk_type_filter) > 0)
    return query_obj


def _revision_row_matches_expanded_pattern(pattern: str):
    """토큰(소문자)이 본문·키워드에 부분 문자열로 들어가는 행만 후보로 남긴다."""
    if not pattern:
        return None
    kw = exists().where(
        RiskLibraryKeyword.risk_revision_id == RiskLibraryItemRevision.id,
        func.instr(func.lower(RiskLibraryKeyword.keyword), pattern) > 0,
    )
    text_cols = (
        RiskLibraryItemRevision.unit_work,
        RiskLibraryItemRevision.work_category,
        RiskLibraryItemRevision.trade_type,
        RiskLibraryItemRevision.process,
        RiskLibraryItemRevision.risk_factor,
        RiskLibraryItemRevision.risk_cause,
        RiskLibraryItemRevision.countermeasure,
        RiskLibraryItemRevision.note,
        RiskLibraryItemRevision.source_file,
        RiskLibraryItemRevision.source_sheet,
        RiskLibraryItemRevision.source_page_or_section,
    )
    col_hits = [
        func.instr(func.lower(func.coalesce(c, "")), pattern) > 0 for c in text_cols
    ]
    return or_(kw, *col_hits)


def _apply_token_sql_prefilter(query_obj, tokens: list[str]):
    expanded: set[str] = set()
    for t in tokens:
        expanded.update(_expand_token(t))
    expanded.discard("")
    if not expanded:
        return query_obj
    ors = [_revision_row_matches_expanded_pattern(p) for p in expanded]
    return query_obj.filter(or_(*ors))


def search_risk_library(
    db: Session,
    *,
    query: str,
    mode: str,
    limit: int = 30,
    offset: int = 0,
    unit_work: str | None = None,
    risk_type: str | None = None,
    contractor_name: str | None = None,
    site_id: int | None = None,
    can_edit_designation: bool = False,
    can_print: bool = True,
    contractor_scope_required: bool = False,
) -> dict[str, Any]:
    normalized_query = normalize_query(query)
    tokens = tokenize_query(normalized_query)
    resolved_mode = classify_search_mode(query, mode)
    unit_work_filter = normalize_query(unit_work or "")
    risk_type_filter = normalize_query(risk_type or "")
    lim = max(1, int(limit))
    off = max(0, int(offset))
    contractor_key, resolved_contractor_name, evaluation_method = _contractor_profile(
        db,
        contractor_name,
    )
    designation = get_risk_assessment_designation(
        db,
        site_id=site_id,
        can_edit=can_edit_designation,
    )

    def serialize_results(rows_with_scores):
        risk_item_ids = [entry[0].item_id for entry in rows_with_scores]
        assignments: dict[int, RiskLibrarySiteAssignment] = {}
        if site_id is not None and risk_item_ids:
            assignments = {
                row.risk_item_id: row
                for row in db.query(RiskLibrarySiteAssignment)
                .filter(
                    RiskLibrarySiteAssignment.site_id == int(site_id),
                    RiskLibrarySiteAssignment.risk_item_id.in_(risk_item_ids),
                )
                .all()
            }
        default_owner = designation.get("inspector_name") if designation else None
        default_verifier = designation.get("verifier_name") if designation else None
        serialized = []
        for row, score, matched_tokens, matched_fields in rows_with_scores:
            assignment = assignments.get(row.item_id)
            converted = convert_risk_score(
                row.risk_f,
                row.risk_s,
                evaluation_method=evaluation_method,
            )
            serialized.append(
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
                    **converted,
                    "evaluation_method": evaluation_method,
                    "improvement_owner_name": (
                        assignment.improvement_owner_name
                        if assignment and assignment.improvement_owner_name
                        else default_owner
                    ),
                    "improvement_verifier_name": (
                        assignment.improvement_verifier_name
                        if assignment and assignment.improvement_verifier_name
                        else default_verifier
                    ),
                    "note": row.note,
                    "source_file": row.source_file,
                    "source_sheet": row.source_sheet,
                    "source_row": row.source_row,
                    "source_page_or_section": row.source_page_or_section,
                    "score": score,
                    "matched_tokens": matched_tokens,
                    "matched_fields": matched_fields,
                }
            )
        return serialized

    response_context = {
        "contractor_key": contractor_key,
        "contractor_name": resolved_contractor_name,
        "evaluation_method": evaluation_method,
        "can_print": bool(can_print),
        "contractor_options": list_risk_library_contractors(db),
        "designation": designation,
    }

    # 검색어 없음: 전량 .all() 금지 — DB count/offset/limit 만 사용 (list_risk_library 와 유사).
    if not tokens:
        q = _active_revision_query(
            db,
            contractor_key=contractor_key,
            contractor_scope_required=contractor_scope_required,
        )
        q = _apply_unit_work_risk_type_sql(
            q, unit_work_filter=unit_work_filter, risk_type_filter=risk_type_filter
        )
        # Browse mode must apply the same exact hazard/countermeasure de-duplication
        # as keyword search before count and pagination.  Ranking in SQL avoids
        # loading the whole risk library merely to remove duplicate seed/import rows.
        ranked = q.with_entities(
            RiskLibraryItemRevision.id.label("revision_id"),
            func.row_number()
            .over(
                partition_by=(
                    func.lower(func.trim(RiskLibraryItemRevision.risk_factor)),
                    func.lower(func.trim(RiskLibraryItemRevision.countermeasure)),
                ),
                order_by=(
                    RiskLibraryItemRevision.risk_r.desc(),
                    RiskLibraryItemRevision.id.asc(),
                ),
            )
            .label("duplicate_rank"),
        ).subquery()
        q = (
            db.query(RiskLibraryItemRevision)
            .join(ranked, ranked.c.revision_id == RiskLibraryItemRevision.id)
            .filter(ranked.c.duplicate_rank == 1)
        )
        total = int(q.count())
        rows = (
            q.order_by(RiskLibraryItemRevision.risk_r.desc(), RiskLibraryItemRevision.id.asc())
            .offset(off)
            .limit(lim)
            .all()
        )
        results = serialize_results([(row, 0.0, [], []) for row in rows])
        return {
            "mode": resolved_mode,
            "normalized_query": normalized_query,
            "tokens": tokens,
            "total": total,
            "limit": lim,
            "offset": off,
            **response_context,
            "results": results,
        }

    q = _active_revision_query(
        db,
        contractor_key=contractor_key,
        contractor_scope_required=contractor_scope_required,
    )
    q = _apply_unit_work_risk_type_sql(
        q, unit_work_filter=unit_work_filter, risk_type_filter=risk_type_filter
    )
    q = _apply_token_sql_prefilter(q, tokens)
    base_rows = q.all()

    row_ids = [r.id for r in base_rows]
    keywords_by_revision: dict[int, set[str]] = {row_id: set() for row_id in row_ids}
    if row_ids:
        keyword_rows = (
            db.query(RiskLibraryKeyword.risk_revision_id, RiskLibraryKeyword.keyword)
            .filter(RiskLibraryKeyword.risk_revision_id.in_(row_ids))
            .all()
        )
        for kw_row in keyword_rows:
            keywords_by_revision[int(kw_row.risk_revision_id)].add((kw_row.keyword or "").lower())

    scored: list[_ScoredResult] = []
    for row in base_rows:
        fields = _collect_fields(row)

        score_total = 0.0
        matched_tokens: set[str] = set()
        matched_fields: set[str] = set()
        revision_keywords = keywords_by_revision.get(row.id, set())

        for token in tokens:
            token_hit = False
            for expanded in _expand_token(token):
                keyword_score, keyword_matched = _score_text_match(
                    " ".join(revision_keywords),
                    expanded,
                    field_name="keyword",
                    mode=resolved_mode,
                )
                if keyword_matched:
                    score_total += keyword_score
                    token_hit = True
                    matched_fields.add("keyword")

                for field_name, field_text in fields.items():
                    score, matched = _score_text_match(
                        field_text,
                        expanded,
                        field_name=field_name,
                        mode=resolved_mode,
                    )
                    if matched:
                        score_total += score
                        token_hit = True
                        matched_fields.add(field_name)

            if token_hit:
                matched_tokens.add(token)

        if score_total <= 0.0:
            continue

        scored.append(
            _ScoredResult(
                row=row,
                score=round(score_total, 2),
                matched_tokens=sorted(matched_tokens),
                matched_fields=sorted(matched_fields),
            )
        )

    scored.sort(key=lambda x: (x.score, x.row.risk_r, -x.row.id), reverse=True)

    # 동일 위험요인/대책 중복은 상위 점수(정렬상 먼저 온 항목) 1건만 남긴다.
    deduped: list[_ScoredResult] = []
    seen_keys: set[str] = set()
    for item in scored:
        key = f"{(item.row.risk_factor or '').strip().lower()}||{(item.row.countermeasure or '').strip().lower()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)

    total = len(deduped)
    paged = deduped[off : off + lim]

    results = serialize_results(
        [
            (item.row, item.score, item.matched_tokens, item.matched_fields)
            for item in paged
        ]
    )

    return {
        "mode": resolved_mode,
        "normalized_query": normalized_query,
        "tokens": tokens,
        "total": total,
        "limit": lim,
        "offset": off,
        **response_context,
        "results": results,
    }
