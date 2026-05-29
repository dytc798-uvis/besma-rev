from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.modules.functional_eval.attendance import parse_attendance_report_xlsx
from app.modules.functional_eval.roster import hash_rrn


def test_parse_attendance_report_sample():
    path = Path(__file__).resolve().parents[2] / "docs" / "출역일보_20260529180349.xlsx"
    if not path.is_file():
        pytest.skip("sample attendance file not in docs/")
    rows = parse_attendance_report_xlsx(path)
    assert len(rows) >= 1000
    assert rows[0].work_date == date(2026, 5, 29)
    assert rows[0].rrn_hash
    assert rows[0].name


def test_parse_attendance_unique_per_day():
    path = Path(__file__).resolve().parents[2] / "docs" / "출역일보_20260529180349.xlsx"
    if not path.is_file():
        pytest.skip("sample attendance file not in docs/")
    rows = parse_attendance_report_xlsx(path)
    keys = {(r.work_date, r.rrn_hash) for r in rows}
    assert len(keys) == len(rows)


def test_attendance_rrn_matches_roster_format():
    path = Path(__file__).resolve().parents[2] / "docs" / "출역일보_20260529180349.xlsx"
    if not path.is_file():
        pytest.skip("sample attendance file not in docs/")
    rows = parse_attendance_report_xlsx(path)
    sample = rows[0]
    assert len(sample.rrn_raw) >= 13
    assert sample.rrn_hash == hash_rrn(sample.rrn_raw)
