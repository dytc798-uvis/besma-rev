"""ERP 출역일보 파싱 (현장명 블록 반복 형식, xls/xlsx)."""

from __future__ import annotations

import re
import math
import io
import struct
import zipfile
import openpyxl
from xml.etree.ElementTree import ParseError
from openpyxl.utils.exceptions import InvalidFileException
from xlrd.biffh import XLRDError
try:
    from lxml.etree import XMLSyntaxError
except ImportError:
    XMLSyntaxError = ParseError
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.modules.functional_eval.roster import hash_rrn, mask_rrn
from app.modules.functional_eval.xls_io import iter_sheet_rows


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


def _parse_attendance_rows(rows: list[tuple], summary: dict | None = None) -> list[ParsedAttendanceRow]:
    if not rows:
        raise ValueError("EMPTY_FILE")

    parsed: list[ParsedAttendanceRow] = []
    seen: set[tuple[date, str]] = set()
    excluded = 0
    profiles: set[str] = set()
    source_dates: set[date] = set()
    i = 0
    while i < len(rows):
        row = rows[i]
        if row and row[0] and str(row[0]).strip().startswith("출역일:"):
            work_date = _parse_work_date(str(row[0]).strip())
            source_dates.add(work_date)
            site_label = str(row[3] or "").strip() if len(row) > 3 else ""
            i += 1
            if i < len(rows) and rows[i] and str(rows[i][0]).strip() == "성명":
                header = rows[i]
                has_amount = len(header) > 7 and str(header[7]).strip() == "합계"
                if len(header) > 4 and not has_amount:
                    raise ValueError("ATTENDANCE_AMOUNT_HEADER_REQUIRED")
                profiles.add("ERP_AMOUNT" if has_amount else "COMPACT_EXPLICIT_ROWS")
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
                    if has_amount:
                        value = r[7] if len(r) > 7 else None
                        if value is None or isinstance(value, str) and not value.strip():
                            amount = 0.0
                        else:
                            try:
                                if isinstance(value, bool):
                                    raise ValueError()
                                amount = float(value)
                            except (TypeError, ValueError):
                                raise ValueError("ATTENDANCE_AMOUNT_INVALID") from None
                        if not math.isfinite(amount) or amount < 0:
                            raise ValueError("ATTENDANCE_AMOUNT_INVALID")
                        if amount == 0:
                            excluded += 1
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

    if len(source_dates) > 1:
        raise ValueError("MULTIPLE_WORK_DATES")
    if not parsed:
        raise ValueError("NO_ATTENDANCE_ROWS")
    if summary is not None:
        summary.update(work_date=next(iter(source_dates)).isoformat(), positive_people=len(parsed),
                       nonpositive_rows_skipped=excluded, amount_checked=profiles == {"ERP_AMOUNT"},
                       site_group_count=len({r.erp_site_label for r in parsed}),
                       coverage_status="UNKNOWN_UPSERT_ONLY")
    return parsed



def parse_attendance_report(file_path: Path) -> list[ParsedAttendanceRow]:
    return _parse_attendance_rows(_attendance_sheet_rows(file_path))



def parse_attendance_report_xlsx(file_path: Path) -> list[ParsedAttendanceRow]:
    """하위 호환 — xls/xlsx 모두 parse_attendance_report 사용."""
    return parse_attendance_report(file_path)


def _attendance_sheet_rows(file_path: Path) -> list[tuple]:
    try:
        with Path(file_path).open("rb") as source:
            is_xlsx = source.read(4).startswith(b"PK")
        if is_xlsx:
            # An invalid read-only workbook can retain its archive in an error
            # traceback. Keep that archive in memory so temporary source files
            # are still released on Windows when parsing fails.
            with io.BytesIO(Path(file_path).read_bytes()) as buffer:
                workbook = None
                try:
                    workbook = openpyxl.load_workbook(buffer, read_only=True, data_only=True)
                    if workbook.active is None:
                        raise ValueError("ATTENDANCE_SHEET_REQUIRED")
                    return [tuple(row) for row in workbook.active.iter_rows(values_only=True)]
                finally:
                    if workbook is not None:
                        workbook.close()
        return iter_sheet_rows(file_path)
    except (OSError, ValueError, KeyError, IndexError, struct.error, zipfile.BadZipFile,
            ParseError, XMLSyntaxError, InvalidFileException, XLRDError) as error:
        raise ValueError("ATTENDANCE_FILE_INVALID") from error



def attendance_report_summary(file_path: Path) -> dict:
    summary: dict = {}
    _parse_attendance_rows(_attendance_sheet_rows(file_path), summary)
    return summary
