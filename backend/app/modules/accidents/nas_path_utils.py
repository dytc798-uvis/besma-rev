# -*- coding: utf-8 -*-
"""프론트 `accidentNasPath.ts`와 동일 규칙으로 표시용 NAS 경로를 만든다."""

from __future__ import annotations

import re

ACCIDENT_NAS_ROOT = r"Z:\4. 안전보건관리실\104 사고 조사 및 이력 (산재요양승인 내역)"


def _segments(path: str | None) -> list[str]:
    raw = (path or "").strip()
    if not raw:
        return []
    normalized = re.sub(r"[\\/]+$", "", raw)
    return [p for p in re.split(r"[\\/]+", normalized) if p]


def _tail_segment(path: str | None) -> str | None:
    parts = _segments(path)
    return parts[-1] if parts else None


def _year_segment(path: str | None, accident_id: str | None) -> str | None:
    parts = _segments(path)
    for part in parts:
        if re.fullmatch(r"\d{4}", part):
            return part
    id_text = (accident_id or "").strip()
    m = re.match(r"^(\d{4})-", id_text)
    return m.group(1) if m else None


def to_displayed_accident_nas_path(path: str | None, accident_id: str | None = None) -> str:
    raw = (path or "").strip()
    if raw.startswith(ACCIDENT_NAS_ROOT):
        return raw

    tail = _tail_segment(raw) or (accident_id or "").strip()
    year = _year_segment(raw, accident_id)
    if not tail and not year:
        return ACCIDENT_NAS_ROOT
    if not tail:
        return f"{ACCIDENT_NAS_ROOT}\\{year}"
    if not year:
        return f"{ACCIDENT_NAS_ROOT}\\{tail}"
    return f"{ACCIDENT_NAS_ROOT}\\{year}\\{tail}"


def build_explorer_bat_bytes(display_path: str) -> bytes:
    """Windows에서 더블클릭 시 해당 폴더를 탐색기로 연다."""
    path = (display_path or "").strip()
    if not path:
        raise ValueError("empty path")
    # 배치에서 큰따옴표는 "" 로 이스케이프
    inner = path.replace('"', '""')
    lines = ["@echo off", "chcp 65001 >nul", f'start "" explorer "{inner}"', ""]
    return ("\r\n".join(lines)).encode("utf-8-sig")
