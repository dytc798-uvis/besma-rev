from __future__ import annotations

from datetime import date
from typing import Any

from app.modules.sites.service import parse_amount, parse_construction_period


def is_current_missing_site(
    row: dict[str, str], as_of: date
) -> tuple[bool, str | None]:
    code = row.get("현장코드", "")
    if not code or not row.get("현장명") or not row.get("주소"):
        return False, None
    start, end = parse_construction_period(row.get("공사기간"))
    if start and end and end < start:
        return False, "INVALID_PERIOD"
    if start and start > as_of:
        return False, "NOT_STARTED"
    if end and end < as_of:
        return False, "COMPLETED"
    if start or end:
        return True, None
    return code.startswith(as_of.strftime("%y")), None


def site_attrs(row: dict[str, str]) -> dict[str, Any]:
    start, end = parse_construction_period(row.get("공사기간"))
    return {
        "site_code": row["현장코드"],
        "site_name": row["현장명"][:200],
        "start_date": start,
        "end_date": end,
        "contract_type": row.get("구분") or None,
        "client_name": row.get("발주처명") or None,
        "contractor_name": row.get("도급사명") or None,
        "project_amount": parse_amount(row.get("도급금액")),
        "phone_number": row.get("전화번호") or None,
        "address": row.get("주소") or None,
        "work_types": row.get("공종") or None,
        "project_manager": row.get("소장") or None,
        "site_manager": row.get("공무") or None,
        "status": "ACTIVE",
    }
