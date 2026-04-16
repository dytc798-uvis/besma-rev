from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.modules.risk_library.models import (
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)

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


def search_risk_library(
    db: Session,
    *,
    query: str,
    mode: str,
    limit: int = 30,
    offset: int = 0,
    unit_work: str | None = None,
    risk_type: str | None = None,
) -> dict[str, Any]:
    normalized_query = normalize_query(query)
    tokens = tokenize_query(normalized_query)
    resolved_mode = classify_search_mode(query, mode)

    base_rows = (
        db.query(RiskLibraryItemRevision)
        .join(RiskLibraryItem, RiskLibraryItem.id == RiskLibraryItemRevision.item_id)
        .filter(
            RiskLibraryItemRevision.is_current.is_(True),
            RiskLibraryItem.is_active.is_(True),
        )
        .all()
    )

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

    unit_work_filter = normalize_query(unit_work or "")
    risk_type_filter = normalize_query(risk_type or "")

    scored: list[_ScoredResult] = []
    for row in base_rows:
        fields = _collect_fields(row)

        if unit_work_filter:
            unit_blob = " ".join([fields["unit_work"], fields["work_category"], fields["trade_type"]]).lower()
            if unit_work_filter not in unit_blob:
                continue
        if risk_type_filter:
            risk_blob = " ".join([fields["risk_factor"], fields["counterplan"]]).lower()
            if risk_type_filter not in risk_blob:
                continue

        if not tokens and not normalized_query:
            # 빈 질의는 목록 조회로 간주
            scored.append(_ScoredResult(row=row, score=0.0, matched_tokens=[], matched_fields=[]))
            continue

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
    paged = deduped[max(0, offset) : max(0, offset) + max(1, limit)]

    results = []
    for item in paged:
        row = item.row
        results.append(
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
                "score": item.score,
                "matched_tokens": item.matched_tokens,
                "matched_fields": item.matched_fields,
            }
        )

    return {
        "mode": resolved_mode,
        "normalized_query": normalized_query,
        "tokens": tokens,
        "total": total,
        "limit": max(1, int(limit)),
        "offset": max(0, int(offset)),
        "results": results,
    }
