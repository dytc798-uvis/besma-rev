"""지게차 모델명 → 제원 조회 (내장 카탈로그 + 웹 검색 보조)."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import Any

from pydantic import BaseModel, Field


class ForkliftEquipmentSpec(BaseModel):
    model: str = ""
    equipment_type: str = ""
    rated_capacity: str = ""
    manufacture_year: str = ""
    length_mm: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    max_lifting_kg: int | None = None
    source: str = Field(description="catalog | web | none")
    confidence: str = Field(default="low", description="high | medium | low")


# 자주 쓰는 모델 — 템플릿 예시(50DN-9VB) 및 현대·두산 계열 대표값
_CATALOG: list[dict[str, Any]] = [
    {
        "match": ["50DN-9VB", "50DN-9", "50DN9VB"],
        "equipment_type": "카운터밸런스형",
        "rated_capacity": "5ton",
        "manufacture_year": "2024년",
        "length_mm": 4510,
        "width_mm": 1740,
        "height_mm": 3025,
        "max_lifting_kg": 11480,
    },
    {
        "match": ["30D-9", "30D9", "30D-9SA"],
        "equipment_type": "카운터밸런스형",
        "rated_capacity": "3ton",
        "length_mm": 3890,
        "width_mm": 1485,
        "height_mm": 2170,
        "max_lifting_kg": 5000,
    },
    {
        "match": ["70D-9", "70D9"],
        "equipment_type": "카운터밸런스형",
        "rated_capacity": "7ton",
        "length_mm": 4890,
        "width_mm": 2280,
        "height_mm": 3120,
        "max_lifting_kg": 16000,
    },
    {
        "match": ["8FGU25", "8FD25"],
        "equipment_type": "카운터밸런스형",
        "rated_capacity": "2.5ton",
        "length_mm": 3560,
        "width_mm": 1485,
        "height_mm": 2130,
        "max_lifting_kg": 2500,
    },
]


def _normalize_model(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip().upper())


def _lookup_catalog(model: str) -> ForkliftEquipmentSpec | None:
    key = _normalize_model(model)
    if not key:
        return None
    for entry in _CATALOG:
        for token in entry["match"]:
            token_u = token.upper().replace(" ", "")
            if key == token_u or token_u in key or key in token_u:
                return ForkliftEquipmentSpec(
                    model=model.strip(),
                    equipment_type=entry.get("equipment_type", "카운터밸런스형"),
                    rated_capacity=entry.get("rated_capacity", ""),
                    manufacture_year=entry.get("manufacture_year", ""),
                    length_mm=entry.get("length_mm"),
                    width_mm=entry.get("width_mm"),
                    height_mm=entry.get("height_mm"),
                    max_lifting_kg=entry.get("max_lifting_kg"),
                    source="catalog",
                    confidence="high",
                )
    return None


def _parse_specs_from_text(text: str, model: str) -> ForkliftEquipmentSpec | None:
    if not text:
        return None
    spec = ForkliftEquipmentSpec(model=model, source="web", confidence="low")
    ton = re.search(r"(\d+(?:\.\d+)?)\s*(?:ton|톤|T\b)", text, re.I)
    if ton:
        spec.rated_capacity = f"{ton.group(1)}ton"
        spec.confidence = "medium"
    kg = re.search(r"(?:최대|허용|적재|인양)[^\d]{0,20}(\d{3,5})\s*kg", text, re.I)
    if not kg:
        kg = re.search(r"(\d{4,5})\s*kg", text, re.I)
    if kg:
        spec.max_lifting_kg = int(kg.group(1))
        spec.confidence = "medium"
    year = re.search(r"(20\d{2})\s*년", text)
    if year:
        spec.manufacture_year = f"{year.group(1)}년"
    for label, attr in (
        (r"전장[^\d]{0,10}(\d{3,5})\s*mm", "length_mm"),
        (r"전폭[^\d]{0,10}(\d{3,5})\s*mm", "width_mm"),
        (r"전고[^\d]{0,10}(\d{3,5})\s*mm", "height_mm"),
    ):
        m = re.search(label, text, re.I)
        if m:
            setattr(spec, attr, int(m.group(1)))
    if spec.rated_capacity or spec.max_lifting_kg:
        return spec
    return None


def _lookup_web(model: str, *, timeout_sec: float = 8.0) -> ForkliftEquipmentSpec | None:
    query = urllib.parse.quote(f"{model} 지게차 정격하중 제원 ton")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BESMA-WorkPlan/1.0 (forklift spec lookup)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None
    # 스니펫 텍스트만 추출해 숫자 패턴 파싱
    snippets = re.findall(r'class="result__snippet[^"]*"[^>]*>([^<]+)', html)
    blob = " ".join(snippets)[:8000]
    return _parse_specs_from_text(blob, model)


def lookup_forklift_equipment_specs(model: str, *, allow_web: bool = True) -> ForkliftEquipmentSpec:
    model = (model or "").strip()
    if not model:
        return ForkliftEquipmentSpec(source="none", confidence="low")

    hit = _lookup_catalog(model)
    if hit:
        return hit

    if allow_web:
        web_hit = _lookup_web(model)
        if web_hit:
            if not web_hit.equipment_type:
                web_hit.equipment_type = "카운터밸런스형"
            return web_hit

    return ForkliftEquipmentSpec(model=model, source="none", confidence="low")
