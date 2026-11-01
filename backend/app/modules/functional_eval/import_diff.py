"""출역일보·월별집계 diff 유틸."""

from __future__ import annotations

from app.modules.functional_eval.attendance import ParsedAttendanceRow
from app.modules.functional_eval.models import FunctionalEvalAttendanceEntry, FunctionalEvalWorker


def attendance_entry_fields(
    *,
    site_code: str,
    name: str,
    job_name: str | None,
    rep_name: str | None,
    erp_site_label: str | None,
) -> tuple[str, str, str, str, str]:
    return (
        site_code,
        name.strip(),
        (job_name or "").strip(),
        (rep_name or "").strip(),
        (erp_site_label or "").strip(),
    )


def entry_tuple(entry: FunctionalEvalAttendanceEntry) -> tuple[str, str, str, str, str]:
    return attendance_entry_fields(
        site_code=entry.site_code,
        name=entry.name,
        job_name=entry.job_name,
        rep_name=entry.rep_name,
        erp_site_label=entry.erp_site_label,
    )


def row_tuple(row: ParsedAttendanceRow, site_code: str) -> tuple[str, str, str, str, str]:
    return attendance_entry_fields(
        site_code=site_code,
        name=row.name,
        job_name=row.job_name,
        rep_name=row.rep_name,
        erp_site_label=row.erp_site_label,
    )


def worker_needs_attendance_update(
    worker: FunctionalEvalWorker,
    row: ParsedAttendanceRow,
    *,
    site_code: str,
    site_name: str,
    is_manager: bool,
) -> bool:
    if not worker.is_active or worker.removed_at is not None:
        return True
    if worker.site_code != site_code:
        return True
    if (worker.site_name or "") != site_name[:300]:
        return True
    if worker.name.strip() != row.name.strip():
        return True
    if (worker.job_name or "").strip() != (row.job_name or "").strip():
        return True
    masked = row.rrn_masked or worker.rrn_masked
    if masked and worker.rrn_masked != masked:
        return True
    if worker.is_site_manager != is_manager:
        return True
    return False
