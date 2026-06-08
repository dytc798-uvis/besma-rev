from __future__ import annotations

import io
from datetime import date

import openpyxl
import pytest

from app.modules.functional_eval.eval_catalog import get_criteria
from app.modules.functional_eval.site_grade_workbook import (
    generate_site_grade_workbook_bytes,
    resolve_site_grade_template_path,
    site_grade_export_filename,
)


def test_template_exists():
    path = resolve_site_grade_template_path()
    assert path.is_file()
    assert "기능인등급" in path.name


def test_export_filename_format():
    assert site_grade_export_filename(date(2026, 6, 8)) == "현장별 기능인등급-20260608.xlsx"


def test_generate_workbook_fills_three_sheets():
    workers = [
        {
            "id": 1,
            "site_code": "24025",
            "site_name": "[1.대우건설] 청라C18BL 테스트",
            "row_no": 1,
            "name": "홍길동",
            "age_label": "40세",
            "rrn_masked": "800101-*******",
            "position_name": "반장",
            "job_name": "철근",
            "phone_mobile": "010-1234-5678",
            "functional_assessment": {
                "is_complete": True,
                "grade_code": "A",
                "scores": {c["id"]: "TOP" for c in get_criteria("FUNCTIONAL")},
            },
            "safety_assessment": {
                "is_complete": True,
                "grade_code": "S",
                "scores": {c["id"]: "MID" for c in get_criteria("SAFETY")},
            },
        },
    ]
    raw = generate_site_grade_workbook_bytes(workers)
    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    sheet1 = next(n for n in wb.sheetnames if n.startswith("1."))
    sheet_fn = next(n for n in wb.sheetnames if "2-1" in n)
    sheet_sf = next(n for n in wb.sheetnames if "2-2" in n)
    ws1 = wb[sheet1]
    assert ws1.cell(6, 3).value == 1
    assert ws1.cell(6, 5).value == "홍길동"
    assert ws1.cell(6, 17).value == "A"
    assert ws1.cell(6, 18).value == "S"
    ws_fn = wb[sheet_fn]
    assert ws_fn.cell(7, 8).value == "O"
    ws_sf = wb[sheet_sf]
    assert ws_sf.cell(7, 9).value == "O"
    wb.close()
