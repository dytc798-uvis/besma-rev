from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

EvalType = Literal["FUNCTIONAL", "SAFETY"]

_CATALOG_PATH = Path(__file__).with_name("eval_catalog_data.json")


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, list[dict[str, Any]]]:
    data = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    return {"FUNCTIONAL": data["FUNCTIONAL"], "SAFETY": data["SAFETY"]}


def get_criteria(eval_type: EvalType) -> list[dict[str, Any]]:
    return list(_load_raw()[eval_type])


def catalog_for_api() -> dict[str, Any]:
    functional = get_criteria("FUNCTIONAL")
    safety = get_criteria("SAFETY")
    return {
        "FUNCTIONAL": {
            "title": "2-1 인사고과표(기능)",
            "criteria": functional,
            "max_score": _max_score(functional),
        },
        "SAFETY": {
            "title": "2-2 인사고과표(안전)",
            "criteria": safety,
            "max_score": _max_score(safety),
        },
    }


def _max_score(criteria: list[dict[str, Any]]) -> int:
    total = 0
    for c in criteria:
        grades = c.get("grades") or []
        if grades:
            total += max(g["points"] for g in grades)
    return total


def compute_assessment(eval_type: EvalType, scores: dict[str, str]) -> dict[str, Any]:
    criteria = get_criteria(eval_type)
    by_id = {c["id"]: c for c in criteria}
    total = 0
    normalized: dict[str, str] = {}
    for cid, grade_key in scores.items():
        if cid not in by_id:
            continue
        crit = by_id[cid]
        grade = next((g for g in crit["grades"] if g["key"] == grade_key), None)
        if grade is None:
            raise ValueError(f"INVALID_GRADE:{cid}")
        normalized[cid] = grade_key
        total += int(grade["points"])

    required = {c["id"] for c in criteria}
    if set(normalized.keys()) != required:
        missing = required - set(normalized.keys())
        raise ValueError(f"INCOMPLETE:{','.join(sorted(missing))}")

    max_score = _max_score(criteria)
    ratio = total / max_score if max_score else 0.0
    grade_code, grade_label = _score_to_grade(ratio)
    return {
        "scores": normalized,
        "total_score": total,
        "max_score": max_score,
        "grade_code": grade_code,
        "grade_label": grade_label,
    }


def score_ratio_to_grade(ratio: float) -> tuple[str, str]:
    """엑셀 등급 수식(IF >85 S, >70 A, >50 B, >0 C)과 동일. D등급 없음."""
    pct = ratio * 100.0
    if pct > 85:
        return "S", "S등급"
    if pct > 70:
        return "A", "A등급"
    if pct > 50:
        return "B", "B등급"
    if pct > 0:
        return "C", "C등급"
    return "", ""


def _score_to_grade(ratio: float) -> tuple[str, str]:
    return score_ratio_to_grade(ratio)


def apply_score_point_adjustments(
    total_score: int,
    max_score: int,
    *,
    bonus: int = 0,
    penalty: int = 0,
) -> tuple[int, str, str]:
    """제재 감점·포상 가점을 반영한 총점·등급."""
    cap = max(int(max_score or 0), 0)
    base = int(total_score or 0)
    adjusted = max(0, min(base + int(bonus or 0) - int(penalty or 0), cap))
    ratio = adjusted / cap if cap else 0.0
    return adjusted, *_score_to_grade(ratio)


def normalize_grade_code(code: str | None) -> str | None:
    """표시·엑셀용 등급 — D는 C로 통일."""
    text = str(code or "").strip().upper()
    if not text:
        return None
    if text == "D":
        return "C"
    return text


def build_lowest_grade_scores(eval_type: EvalType) -> dict[str, str]:
    """항목별 최저 점수(문제/BOTTOM) — 전체 C등급 산출용."""
    scores: dict[str, str] = {}
    for crit in get_criteria(eval_type):
        grades = crit.get("grades") or []
        if not grades:
            continue
        lowest = min(grades, key=lambda g: int(g["points"]))
        scores[str(crit["id"])] = str(lowest["key"])
    return scores


def _top_grade_key(crit: dict[str, Any]) -> str | None:
    grades = crit.get("grades") or []
    if not grades:
        return None
    return str(max(grades, key=lambda g: int(g["points"]))["key"])


def build_top_grade_scores(eval_type: EvalType) -> dict[str, str]:
    """항목별 최고 점수(우수/TOP)."""
    scores: dict[str, str] = {}
    for crit in get_criteria(eval_type):
        top = _top_grade_key(crit)
        if top:
            scores[str(crit["id"])] = top
    return scores


def assessment_has_issue(eval_type: EvalType, scores: dict[str, str]) -> bool:
    """평가표 항목 중 하나라도 최고점(우수) 미만이면 True."""
    if not scores:
        return False
    by_id = {c["id"]: c for c in get_criteria(eval_type)}
    for cid, grade_key in scores.items():
        crit = by_id.get(cid)
        if crit is None:
            continue
        top_key = _top_grade_key(crit)
        if top_key is None:
            continue
        if str(grade_key) != top_key:
            return True
    return False


def assessment_has_bottom(eval_type: EvalType, scores: dict[str, str]) -> bool:
    """평가표 항목 중 「문제」(BOTTOM)가 하나라도 있으면 True."""
    if not scores:
        return False
    return any(str(v) == "BOTTOM" for v in scores.values())


def _bottom_grade_key(crit: dict[str, Any]) -> str | None:
    grades = crit.get("grades") or []
    if not grades:
        return None
    return str(min(grades, key=lambda g: int(g["points"]))["key"])


SAFETY_CRITERION_VIOLATION: dict[str, str] = {
    "c1": "INST_TBM",
    "c2": "INST_QR_ACTIVITY",
    "c3": "INST_PPE",
    "c4": "INST_TOOL",
    "c5": "INST_WALKING",
    "c6": "INST_SMOKING_AREA",
    "c7": "INST_HOUSEKEEPING",
    "c8": "INST_HOUSEKEEPING",
}


def violation_safety_criterion_ids(violation_code: str) -> list[str]:
    from app.modules.functional_eval.sanctions import DEFAULT_SANCTION_VIOLATION_CODE

    if violation_code == DEFAULT_SANCTION_VIOLATION_CODE:
        return ["c2"]
    out: list[str] = []
    for cid, vcode in SAFETY_CRITERION_VIOLATION.items():
        if vcode == violation_code and cid not in out:
            out.append(cid)
    return out


def build_safety_scores_with_bottom_for_violation(
    violation_code: str,
    existing_scores: dict[str, str] | None = None,
) -> dict[str, str]:
    """추가 제재 등록 시 — 해당 위반에 대응하는 안전 평가 항목만 「문제」로 반영."""
    criteria = get_criteria("SAFETY")
    scores: dict[str, str] = dict(existing_scores or {})
    for crit in criteria:
        cid = str(crit["id"])
        if cid not in scores:
            top = _top_grade_key(crit)
            if top:
                scores[cid] = top
    for cid in violation_safety_criterion_ids(violation_code):
        crit = next((c for c in criteria if str(c["id"]) == cid), None)
        if crit is None:
            continue
        bottom = _bottom_grade_key(crit)
        if bottom:
            scores[cid] = bottom
    return scores


def violation_safety_targets_already_bottom(
    violation_code: str,
    existing_scores: dict[str, str] | None,
) -> bool:
    """추가 제재 대상 항목이 이미 모두 「문제」(BOTTOM)이면 True."""
    criterion_ids = violation_safety_criterion_ids(violation_code)
    if not criterion_ids:
        return True
    scores = dict(existing_scores or {})
    criteria = get_criteria("SAFETY")
    by_id = {str(c["id"]): c for c in criteria}
    for cid in criterion_ids:
        crit = by_id.get(cid)
        if crit is None:
            continue
        bottom = _bottom_grade_key(crit)
        if bottom and scores.get(cid) != bottom:
            return False
    return True
