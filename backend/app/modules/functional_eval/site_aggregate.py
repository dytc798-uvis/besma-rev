"""월별현장별집계 ERP xls 파싱."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.modules.functional_eval.xls_io import iter_sheet_rows


@dataclass
class ParsedSiteAggregateRow:
    site_code: str
    erp_site_name: str
    manager_name: str
    erp_man_days: float | None = None
    erp_work_days: float | None = None
    erp_headcount: int | None = None


def _parse_numeric_cell(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_headcount_cell(value) -> int | None:
    num = _parse_numeric_cell(value)
    if num is None:
        return None
    return int(round(num))


def _normalize_site_code(value) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = str(int(float(text)))
    return text.strip()


def parse_monthly_site_aggregate(path: Path) -> list[ParsedSiteAggregateRow]:
    rows = iter_sheet_rows(path)
    if not rows:
        raise ValueError("EMPTY_FILE")

    parsed: list[ParsedSiteAggregateRow] = []
    for raw in rows:
        if not raw or len(raw) < 4:
            continue
        code = _normalize_site_code(raw[1])
        name = str(raw[2]).strip() if raw[2] is not None else ""
        manager = str(raw[3]).strip() if raw[3] is not None else ""
        if not code or not name or not manager:
            continue
        if name in ("현장명", "■ 월별-현장별집계"):
            continue
        parsed.append(
            ParsedSiteAggregateRow(
                site_code=code,
                erp_site_name=name,
                manager_name=manager,
                erp_man_days=_parse_numeric_cell(raw[4]) if len(raw) > 4 else None,
                erp_work_days=_parse_numeric_cell(raw[5]) if len(raw) > 5 else None,
                erp_headcount=_parse_headcount_cell(raw[6]) if len(raw) > 6 else None,
            )
        )

    if not parsed:
        raise ValueError("NO_SITE_AGGREGATE_ROWS")
    return parsed
