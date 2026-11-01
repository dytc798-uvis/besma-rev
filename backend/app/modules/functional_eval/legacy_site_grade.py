"""25년 12월 수동 기능인등급 엑셀에서 추출한 1회성 평가 스냅샷.

템플릿 xlsx는 구조(수식·서식)만 쓰고, 해당 근로자의 기존 평가는 이 JSON에서 복원한다.
DB에 완료된 평가가 있으면 DB가 우선한다.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.modules.functional_eval.eval_catalog import EvalType, compute_assessment, get_criteria

_LEGACY_PATH = Path(__file__).with_name("legacy_site_grade_data.json")
GRADE_KEYS = ("TOP", "MID", "LOW", "BOTTOM")


def legacy_match_key(site_code: str | None, name: str | None, rrn_masked: str | None) -> str:
    code = str(site_code or "").strip()
    nm = str(name or "").strip()
    rrn = str(rrn_masked or "").replace("-", "").strip()[:6]
    return f"{code}|{nm}|{rrn}"


@lru_cache(maxsize=1)
def _load_legacy_index() -> dict[str, dict[str, Any]]:
    if not _LEGACY_PATH.is_file():
        return {}
    raw = json.loads(_LEGACY_PATH.read_text(encoding="utf-8"))
    index: dict[str, dict[str, Any]] = {}
    for row in raw.get("workers") or []:
        key = legacy_match_key(row.get("site_code"), row.get("name"), row.get("rrn_masked"))
        if key.replace("|", "").strip():
            index[key] = row
    return index


def legacy_worker_record(
    site_code: str | None,
    name: str | None,
    rrn_masked: str | None,
) -> dict[str, Any] | None:
    return _load_legacy_index().get(legacy_match_key(site_code, name, rrn_masked))


def _pick_assessment(
    current: dict[str, Any] | None,
    legacy: dict[str, Any] | None,
    field: Literal["functional_assessment", "safety_assessment"],
) -> dict[str, Any] | None:
    if current and current.get("is_complete"):
        return current
    leg = (legacy or {}).get(field)
    if leg and leg.get("is_complete"):
        return leg
    return current


def apply_legacy_assessments(worker: dict[str, Any]) -> dict[str, Any]:
    """DB 미완료 시 레거시 수동 평가를 worker dict에 병합."""
    legacy = legacy_worker_record(worker.get("site_code"), worker.get("name"), worker.get("rrn_masked"))
    if not legacy:
        return worker
    worker["functional_assessment"] = _pick_assessment(
        worker.get("functional_assessment"), legacy, "functional_assessment"
    )
    worker["safety_assessment"] = _pick_assessment(
        worker.get("safety_assessment"), legacy, "safety_assessment"
    )
    return worker


def parse_eval_marks_from_row(
    ws,
    row: int,
    eval_type: EvalType,
) -> dict[str, Any] | None:
    """2-1 / 2-2 한 행의 O 표시 → assessment dict."""
    criteria = get_criteria(eval_type)
    scores: dict[str, str] = {}
    for i, crit in enumerate(criteria):
        base = 8 + i * 4
        for off, key in enumerate(GRADE_KEYS):
            if ws.cell(row, base + off).value == "O":
                scores[crit["id"]] = key
                break
    if len(scores) != len(criteria):
        return None
    payload = compute_assessment(eval_type, scores)
    payload["is_complete"] = True
    payload["eval_type"] = eval_type
    payload["source"] = "legacy_workbook"
    return payload
