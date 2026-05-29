"""ERP 출역일보 xlsx 파싱 (현장명 블록 반복 형식)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import openpyxl

from app.modules.functional_eval.roster import hash_rrn, mask_rrn


@dataclass
class ParsedAttendanceRow:
    work_date: date
    name: str
    rrn_raw: str
    rrn_hash: str
    rrn_masked: str | None
    job_name: str | None
    rep_name: str | None
    erp_site_label: str


def _parse_work_date(cell: str) -> date:
    text = cell.replace("출역일:", "").strip()
    if isinstance(text, datetime):
        return text.date()
    return date.fromisoformat(text[:10])


def parse_attendance_report_xlsx(file_path: Path) -> list[ParsedAttendanceRow]:
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise ValueError("EMPTY_FILE")

    parsed: list[ParsedAttendanceRow] = []
    seen: set[tuple[date, str]] = set()
    i = 0
    while i < len(rows):
        row = rows[i]
        if row and row[0] and str(row[0]).strip().startswith("출역일:"):
            work_date = _parse_work_date(str(row[0]).strip())
            site_label = str(row[3] or "").strip() if len(row) > 3 else ""
            i += 1
            if i < len(rows) and rows[i] and str(rows[i][0]).strip() == "성명":
                i += 1
                while i < len(rows):
                    r = rows[i]
                    if not r or not any(r):
                        i += 1
                        continue
                    first = str(r[0]).strip() if r[0] else ""
                    if first.startswith("출역일:") or first == "합계":
                        break
                    if first == "소계":
                        i += 1
                        continue
                    name = first
                    rrn_cell = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ""
                    digits = re.sub(r"\D", "", rrn_cell)
                    if len(digits) < 13:
                        i += 1
                        continue
                    rrn_hash = hash_rrn(digits)
                    key = (work_date, rrn_hash)
                    if key in seen:
                        i += 1
                        continue
                    seen.add(key)
                    job_name = str(r[2]).strip() if len(r) > 2 and r[2] is not None else None
                    rep_name = str(r[3]).strip() if len(r) > 3 and r[3] is not None else None
                    parsed.append(
                        ParsedAttendanceRow(
                            work_date=work_date,
                            name=name,
                            rrn_raw=digits,
                            rrn_hash=rrn_hash,
                            rrn_masked=mask_rrn(digits),
                            job_name=job_name or None,
                            rep_name=rep_name or None,
                            erp_site_label=site_label,
                        )
                    )
                    i += 1
                continue
        i += 1

    if not parsed:
        raise ValueError("NO_ATTENDANCE_ROWS")
    return parsed
