from pathlib import Path

import pytest

from app.utils.file_ingestion import parse_excel_with_fallback, validate_worker_file_structure


ROOT = Path("d:/besma-rev/docs/sample/site_import/raw")


def test_parse_xlsx_employees():
    path = ROOT / "employees_raw.xlsx"
    assert path.exists()
    parsed = parse_excel_with_fallback(path)
    assert parsed.row_count > 0
    assert parsed.parser_used in {"openpyxl", "pandas.read_excel"}
    diag = parsed.to_diagnostics(required_columns=["성   명", "직위"])
    assert diag["row_count"] > 0
    assert "columns" in diag


def test_parse_xls_daily_workers():
    path = ROOT / "daily_workers_raw.xls"
    assert path.exists()
    parsed = parse_excel_with_fallback(path)
    assert parsed.row_count > 0
    assert parsed.file_type == "xls"
    validation = validate_worker_file_structure(parsed.headers, ["성   명", "소속현장코드"])
    assert validation["required_columns_ok"] is True


def test_parse_corrupted_xls_diagnosis():
    candidates = list(ROOT.glob("*20260320152536*"))
    assert candidates, "corrupted sample file not found"
    with pytest.raises(ValueError) as exc:
        parse_excel_with_fallback(candidates[0])
    msg = str(exc.value)
    assert "파일 파싱에 실패" in msg

