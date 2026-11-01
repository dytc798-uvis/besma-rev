"""ERP .xls (OLE) / .xlsx 공통 시트 읽기."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import olefile
import openpyxl
import xlrd

from app.utils.file_ingestion import OLE_XLS_SIGNATURE, open_xlrd_workbook


def iter_sheet_rows(file_path: Path) -> list[tuple[Any, ...]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    with path.open("rb") as fp:
        sig = fp.read(8)

    if sig.startswith(OLE_XLS_SIGNATURE):
        return _read_xls_rows(path)
    return _read_xlsx_rows(path)


def _read_xls_rows(path: Path) -> list[tuple[Any, ...]]:
    try:
        wb = open_xlrd_workbook(path)
        sheet = wb.sheet_by_index(0)
        return [tuple(sheet.row_values(r)) for r in range(sheet.nrows)]
    except Exception:
        ole = olefile.OleFileIO(str(path))
        try:
            data = ole.openstream("Workbook").read()
        finally:
            ole.close()
        wb = xlrd.open_workbook(file_contents=data)
        sheet = wb.sheet_by_index(0)
        return [tuple(sheet.row_values(r)) for r in range(sheet.nrows)]


def _read_xlsx_rows(path: Path) -> list[tuple[Any, ...]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = [tuple(row) for row in ws.iter_rows(values_only=True)]
    wb.close()
    return rows
