"""Read-only site roster derived from the 2026 vertical weekly meeting workbook."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from app.modules.document_explorer.government_access import is_government_site_record

_ROSTER = Path(__file__).with_name("active_site_scope_20261008.json")


def today_kst() -> date:
    return datetime.now(timezone(timedelta(hours=9))).date()


@lru_cache(maxsize=1)
def active_site_codes() -> frozenset[str]:
    data = json.loads(_ROSTER.read_text(encoding="utf-8"))
    if data.get("schema") != 1 or not isinstance(data.get("site_codes"), list):
        raise ValueError("Invalid active site roster")
    return frozenset(str(code) for code in data["site_codes"])


def in_active_scope(site: object, today: date, scope: str) -> bool:
    if str(getattr(site, "site_code", "") or "") not in active_site_codes():
        return False
    if str(getattr(site, "status", "") or "").upper() in {"COMPLETED", "CLOSED", "INACTIVE"}:
        return False
    end_date = getattr(site, "end_date", None)
    if end_date is not None and end_date < today:
        return False
    if "준공" in str(getattr(site, "site_name", "") or ""):
        return False
    government = is_government_site_record(site)
    return government if scope == "government" else not government
