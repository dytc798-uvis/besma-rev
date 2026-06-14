"""등급 인플레이션 방지 — 분포 계산·서명 전 사유 검증."""

from __future__ import annotations

from typing import Any

from app.modules.functional_eval.eval_catalog import normalize_grade_code
from app.modules.functional_eval.service import GRADE_STAT_CODES, _is_fully_evaluated

S_GRADE_RATIO_LIMIT = 0.20
MIN_REASON_LEN = 10


def worker_functional_grade_code(worker: dict[str, Any]) -> str | None:
    """기능(2-1) 등급 — 평가완료 근로자만."""
    if not _is_fully_evaluated(worker):
        return None
    assessment = worker.get("functional_assessment") or {}
    if not assessment.get("is_complete"):
        return None
    code = normalize_grade_code(str(assessment.get("grade_code") or "")) or ""
    return code if code in GRADE_STAT_CODES else None


def compute_grade_inflation_review(workers: list[dict[str, Any]]) -> dict[str, Any]:
    """평가완료 근로자 기준 기능(2-1) 등급 분포."""
    evaluated = [w for w in workers if _is_fully_evaluated(w)]
    counts = {code: 0 for code in GRADE_STAT_CODES}
    for worker in evaluated:
        code = worker_functional_grade_code(worker)
        if code:
            counts[code] += 1
    total = sum(counts.values())
    grades: dict[str, dict[str, float | int]] = {}
    for code in GRADE_STAT_CODES:
        count = counts[code]
        grades[code] = {
            "count": count,
            "pct": round(100.0 * count / total, 1) if total else 0.0,
        }
    s_count = counts["S"]
    c_count = counts["C"]
    s_ratio = (s_count / total) if total else 0.0
    snapshot = {
        "evaluated_total": total,
        "workers_total": len(workers),
        "s_count": s_count,
        "c_count": c_count,
        "s_ratio": round(s_ratio, 4),
        "grades": grades,
        "basis": "functional",
        "s_recommended_max_pct": 20.0,
    }
    s_over_limit = total > 0 and s_ratio > S_GRADE_RATIO_LIMIT
    return {
        "grade_distribution_snapshot": snapshot,
        "s_over_limit": s_over_limit,
        "no_c_grade": False,
        "grade_stats": {
            "functional": {
                "workers_total": len(workers),
                "graded_total": total,
                "ungraded_count": len(workers) - len(evaluated),
                "grades": grades,
            },
        },
    }


def validate_grade_inflation_reasons(
    review: dict[str, Any],
    *,
    s_over_limit_reason: str | None,
    no_c_grade_reason: str | None = None,
) -> None:
    """기능/품질(2-1) S등급 20% 초과 사유만 검증. 안전(2-2)에는 적용하지 않음."""
    if review.get("s_over_limit"):
        text = (s_over_limit_reason or "").strip()
        if len(text) < MIN_REASON_LEN:
            raise ValueError("S_GRADE_OVER_LIMIT_REASON_REQUIRED")


def build_grade_review_metadata(
    review: dict[str, Any],
    *,
    s_over_limit_reason: str | None,
    no_c_grade_reason: str | None,
) -> dict[str, Any]:
    snapshot = dict(review.get("grade_distribution_snapshot") or {})
    meta: dict[str, Any] = {
        "grade_distribution_snapshot": snapshot,
        "s_ratio": snapshot.get("s_ratio"),
        "s_count": snapshot.get("s_count"),
        "c_count": snapshot.get("c_count"),
    }
    if review.get("s_over_limit") and s_over_limit_reason:
        meta["s_over_limit_reason"] = s_over_limit_reason.strip()
    return meta
