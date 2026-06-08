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


def _score_to_grade(ratio: float) -> tuple[str, str]:
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


def normalize_grade_code(code: str | None) -> str | None:
    """표시·엑셀용 등급 — D는 C로 통일."""
    text = str(code or "").strip().upper()
    if not text:
        return None
    if text == "D":
        return "C"
    return text
