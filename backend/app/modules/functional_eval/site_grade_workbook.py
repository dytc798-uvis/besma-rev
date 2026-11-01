"""현장별 기능인등급 엑셀 — docs/01.*기능인등급*.xlsx 템플릿 기반 출력."""

from __future__ import annotations

import io
import json
import hashlib
from copy import copy
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Literal

import openpyxl
from openpyxl.formula.translate import Translator
from openpyxl.worksheet.worksheet import Worksheet

from app.modules.functional_eval.eval_catalog import get_criteria, compute_assessment, normalize_grade_code

TEMPLATE_GLOB = "01.*기능인등급*.xlsx"
MODULE_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
SHEET1_DATA_START_ROW = 6
SHEET_EVAL_START_ROW = 7
GRADE_KEYS = ("TOP", "MID", "LOW", "BOTTOM")

# 1. 현장별 인원현황 — 데이터 열 (템플릿 6행 기준)
COL_SITE_CODE = 2
COL_SEQ = 3
COL_SITE_NAME = 4
COL_NAME = 5
COL_AGE = 6
COL_RRN = 7
COL_POSITION = 9
COL_JOB = 10
COL_PHONE = 12
COL_GRADE_FUNCTIONAL = 17
COL_GRADE_SAFETY = 18


class WorkbookReviewRequired(ValueError):
    """The existing record needs its original rubric; never recalculate it silently."""


def _template_profile() -> tuple[Path, dict[str, Any]]:
    try:
        profile = json.loads((MODULE_TEMPLATE_DIR / "workbook-profile.json").read_text(encoding="utf-8"))
        name = profile["template_file"]
        if type(profile["schema"]) is not int or profile["schema"] != 1 or profile.get("no_personnel_data") is not True:
            raise ValueError("profile")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".xlsx"):
            raise ValueError("filename")
        path = MODULE_TEMPLATE_DIR / name
        for entry in [path, MODULE_TEMPLATE_DIR]:
            if entry.is_symlink() or getattr(entry.stat(), "st_file_attributes", 0) & 0x400:
                raise ValueError("reparse")
        if hashlib.sha256(path.read_bytes()).hexdigest() != profile["template_sha256"]:
            raise ValueError("template")
        catalog = Path(__file__).with_name("eval_catalog_data.json")
        if hashlib.sha256(catalog.read_bytes()).hexdigest() != profile["catalog_sha256"]:
            raise ValueError("catalog")
        for kind in ("FUNCTIONAL", "SAFETY"):
            if profile["max_scores"][kind] != sum(max(g["points"] for g in c["grades"]) for c in get_criteria(kind)):
                raise ValueError("rubric")
        return path, profile
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise FileNotFoundError("기능인등급 출력 양식의 연결을 확인해 주세요.") from error


def resolve_site_grade_template_path() -> Path:
    return _template_profile()[0]


def _review_required() -> WorkbookReviewRequired:
    return WorkbookReviewRequired("이 평가의 기준과 출력 양식의 연결을 확인해 주세요. 기존 서명본은 계속 확인할 수 있습니다.")


def _assessment_adjustment(assessment: dict[str, Any] | None, kind: str) -> int:
    if not assessment or not assessment.get("is_complete"):
        return 0
    criteria = get_criteria(kind)
    scores = assessment.get("scores") or {}
    if set(scores) != {c["id"] for c in criteria}:
        raise _review_required()
    try:
        computed = compute_assessment(kind, scores)
    except ValueError as error:
        raise _review_required() from error
    maximum = computed["max_score"]
    if assessment.get("max_score") != maximum:
        raise _review_required()
    bonus, penalty = assessment.get("adjustment_bonus", 0), assessment.get("adjustment_penalty", 0)
    if any(type(v) is not int or v < 0 for v in (bonus, penalty)) or kind != "SAFETY" and (bonus or penalty):
        raise _review_required()
    total = max(0, min(maximum, computed["total_score"] + bonus - penalty))
    expected_grade = "S" if total / maximum > .85 else "A" if total / maximum > .7 else "B" if total / maximum > .5 else "C" if total > 0 else ""
    if assessment.get("total_score") != total or (normalize_grade_code(assessment.get("grade_code")) or "") != expected_grade:
        raise _review_required()
    if assessment.get("base_total_score", computed["total_score"]) != computed["total_score"]:
        raise _review_required()
    return bonus - penalty


def _total_formula(kind: str, row: int, adjustment: int) -> str:
    from openpyxl.utils import get_column_letter as col
    count = len(get_criteria(kind))
    complete = ",".join(f'COUNTIF({col(8+i*4)}{row}:{col(11+i*4)}{row},"O")=1' for i in range(count))
    maximum = sum(max(g["points"] for g in c["grades"]) for c in get_criteria(kind))
    helper = 48 if kind == "FUNCTIONAL" else 44
    # Original helper columns start AV (48) / AR (44), one per score option.
    base = f"SUMPRODUCT($H$5:${col(7+count*4)}$5,{col(helper)}{row}:{col(helper+count*4-1)}{row})"
    if adjustment:
        base = f"MAX(0,MIN({maximum},{base}+({adjustment})))"
    return f'=IF(AND({complete}),{base},"")'


def _copy_extended_style(ws: Worksheet, template_row: int, target_row: int, original_rows: int) -> None:
    if target_row <= original_rows:
        return
    for col in range(1, ws.max_column + 1):
        ws.cell(target_row, col)._style = copy(ws.cell(template_row, col)._style)
    ws.row_dimensions[target_row].height = ws.row_dimensions[template_row].height


def _limit_output_rows(ws: Worksheet, start: int, count: int) -> None:
    last = start + count - 1
    for row in range(start, max(ws.max_row, last) + 1):
        ws.row_dimensions[row].hidden = row > last
    if ws.print_area:
        from openpyxl.worksheet.print_settings import PrintArea
        area = next(iter(PrintArea.from_string(str(ws.print_area)).ranges))
        ws.print_area = f"{openpyxl.utils.get_column_letter(area.min_col)}{area.min_row}:{openpyxl.utils.get_column_letter(area.max_col)}{last}"



def site_grade_export_filename(for_day: date | None = None) -> str:
    d = for_day or date.today()
    return f"현장별 기능인등급-{d:%Y%m%d}.xlsx"


def _find_sheet_name(wb: openpyxl.Workbook, needle: str) -> str:
    for name in wb.sheetnames:
        if needle in name:
            return name
    raise KeyError(f"시트를 찾을 수 없습니다: {needle!r} (sheets={wb.sheetnames})")


def _grade_code(assessment: dict[str, Any] | None) -> str | None:
    if not assessment or not assessment.get("is_complete"):
        return None
    from app.modules.functional_eval.eval_catalog import normalize_grade_code

    code = str(assessment.get("grade_code") or "").strip()
    return normalize_grade_code(code)


def _sheet1_age_or_birth(worker: dict[str, Any]) -> str:
    """2-2/2-1 VLOOKUP(…,4) → 1.인원현황 F열(생년월일·연령 표시)."""
    age = (worker.get("age_label") or "").strip()
    if age:
        return age
    rrn = (worker.get("rrn_masked") or "").replace("-", "").strip()
    if len(rrn) >= 6 and rrn[:6].isdigit():
        yy, mm, dd = rrn[0:2], rrn[2:4], rrn[4:6]
        century = "19" if int(yy) >= 30 else "20"
        return f"{century}{yy}.{mm}.{dd}"
    return ""


def _clear_sheet1_data(ws: Worksheet) -> None:
    max_row = ws.max_row or SHEET1_DATA_START_ROW
    for row in range(SHEET1_DATA_START_ROW, max_row + 1):
        for col in range(COL_SITE_CODE, COL_GRADE_SAFETY + 1):
            ws.cell(row=row, column=col).value = None


def _write_sheet1_row(ws: Worksheet, row: int, seq: int, worker: dict[str, Any]) -> None:
    ws.cell(row=row, column=COL_SITE_CODE, value=worker.get("site_code") or "")
    ws.cell(row=row, column=COL_SEQ, value=seq)
    ws.cell(row=row, column=COL_SITE_NAME, value=worker.get("site_name") or "")
    ws.cell(row=row, column=COL_NAME, value=worker.get("name") or "")
    ws.cell(row=row, column=COL_AGE, value=_sheet1_age_or_birth(worker))
    ws.cell(row=row, column=COL_RRN, value=worker.get("rrn_masked") or "")
    ws.cell(row=row, column=COL_POSITION, value=worker.get("position_name") or "")
    ws.cell(row=row, column=COL_JOB, value=worker.get("job_name") or "")
    ws.cell(row=row, column=COL_PHONE, value=worker.get("phone_mobile") or "")
    ws.cell(row=row, column=COL_GRADE_FUNCTIONAL, value=_grade_code(worker.get("functional_assessment")))
    ws.cell(row=row, column=COL_GRADE_SAFETY, value=_grade_code(worker.get("safety_assessment")))
    # Source fields are data, even when an imported name starts with '='.
    for col in (COL_SITE_CODE, COL_SITE_NAME, COL_NAME, COL_AGE, COL_RRN,
                COL_POSITION, COL_JOB, COL_PHONE, COL_GRADE_FUNCTIONAL, COL_GRADE_SAFETY):
        ws.cell(row, col).data_type = "s"


def _criteria_col_count(eval_type: Literal["FUNCTIONAL", "SAFETY"]) -> int:
    return len(get_criteria(eval_type))


def _eval_mark_end_column(ws: Worksheet, template_row: int, eval_type: Literal["FUNCTIONAL", "SAFETY"]) -> int:
    """평가 O 표시 열 끝 — 카탈로그 항목 수와 템플릿 샘플 행 중 넓은 쪽."""
    end = 8 + _criteria_col_count(eval_type) * 4 - 1
    max_col = ws.max_column or end
    for col in range(8, max_col + 1):
        if ws.cell(template_row, col).value == "O":
            end = max(end, col + 3)
    return end


def _clear_eval_marks(
    ws: Worksheet,
    row: int,
    eval_type: Literal["FUNCTIONAL", "SAFETY"],
    *,
    end_col: int | None = None,
) -> None:
    last_col = end_col if end_col is not None else 8 + _criteria_col_count(eval_type) * 4 - 1
    for col in range(8, last_col + 1):
        # openpyxl: cell(..., value=None)은 기존 값을 지우지 않음
        ws.cell(row=row, column=col).value = None


def _write_eval_marks(
    ws: Worksheet,
    row: int,
    assessment: dict[str, Any] | None,
    eval_type: Literal["FUNCTIONAL", "SAFETY"],
) -> None:
    criteria = get_criteria(eval_type)
    scores = (assessment or {}).get("scores") or {}
    complete = bool((assessment or {}).get("is_complete"))
    for i, crit in enumerate(criteria):
        base = 8 + i * 4
        grade_key = scores.get(crit["id"]) if complete else None
        for off, key in enumerate(GRADE_KEYS):
            ws.cell(row=row, column=base + off).value = "O" if grade_key == key else None


def _copy_eval_formula_row(ws: Worksheet, template_row: int, target_row: int) -> None:
    """2-1 / 2-2 행의 VLOOKUP·합계 수식을 템플릿 7행에서 행 단위로 복사한다."""
    if target_row == template_row:
        return
    max_col = ws.max_column or 80
    for col in range(1, max_col + 1):
        src = ws.cell(row=template_row, column=col)
        dst = ws.cell(row=target_row, column=col)
        if src.data_type == "f" and src.value:
            cell_origin = f"{src.column_letter}{template_row}"
            cell_target = f"{dst.column_letter}{target_row}"
            try:
                dst.value = Translator(str(src.value), origin=cell_origin).translate_formula(cell_target)
            except ValueError:
                # 구형/비표준 수식 — 행 참조만 치환 (VLOOKUP 열 인덱스 보호)
                dst.value = re.sub(
                    rf"\$?{re.escape(src.column_letter)}{template_row}\b",
                    f"{src.column_letter}{target_row}",
                    str(src.value),
                )
        elif col <= 7 and src.data_type != "f":
            dst.value = None


def generate_site_grade_workbook_bytes(workers: list[dict[str, Any]]) -> bytes:
    """템플릿 복사 → 1.인원현황 · 2-1 · 2-2 채움 → xlsx bytes."""
    template, profile = _template_profile()
    sorted_workers = sorted(
        workers,
        key=lambda w: (
            str(w.get("site_code") or ""),
            int(w.get("row_no") or 0),
            int(w.get("id") or 0),
        ),
    )

    if not sorted_workers:
        raise ValueError("NO_ATTENDANCE_WORKERS")
    adjustments = [{kind: _assessment_adjustment(worker.get("functional_assessment" if kind == "FUNCTIONAL" else "safety_assessment"), kind) for kind in ("FUNCTIONAL", "SAFETY")} for worker in sorted_workers]
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "export.xlsx"
        shutil.copy2(template, out_path)
        wb = openpyxl.load_workbook(out_path)

        sheet1_name = _find_sheet_name(wb, "1.")
        sheet_fn_name = _find_sheet_name(wb, "2-1")
        sheet_sf_name = _find_sheet_name(wb, "2-2")
        ws1 = wb[sheet1_name]
        ws_fn = wb[sheet_fn_name]
        ws_sf = wb[sheet_sf_name]

        original_rows = {ws.title: ws.max_row for ws in (ws1, ws_fn, ws_sf)}
        derived = {col: ws1.cell(SHEET1_DATA_START_ROW, col).value for col in profile["roster_derived_formula_columns"]}
        _clear_sheet1_data(ws1)
        n = len(sorted_workers)
        for idx, worker in enumerate(sorted_workers):
            row1 = SHEET1_DATA_START_ROW + idx
            _copy_extended_style(ws1, SHEET1_DATA_START_ROW, row1, original_rows[ws1.title])
            for col, formula in derived.items():
                if not isinstance(formula, str) or not formula.startswith("="):
                    raise FileNotFoundError("기능인등급 출력 양식을 확인해 주세요.")
                ws1.cell(row1, col).value = Translator(formula, origin=ws1.cell(SHEET1_DATA_START_ROW, col).coordinate).translate_formula(ws1.cell(row1, col).coordinate)
            _write_sheet1_row(ws1, row1, idx + 1, worker)

        fn_cols = _criteria_col_count("FUNCTIONAL")
        sf_cols = _criteria_col_count("SAFETY")
        template_eval_row = SHEET_EVAL_START_ROW
        max_template_row = ws_fn.max_row or template_eval_row

        fn_mark_end = _eval_mark_end_column(ws_fn, template_eval_row, "FUNCTIONAL")
        sf_mark_end = _eval_mark_end_column(ws_sf, template_eval_row, "SAFETY")

        for idx in range(n):
            eval_row = SHEET_EVAL_START_ROW + idx
            for ws in (ws_fn, ws_sf):
                _copy_extended_style(ws, template_eval_row, eval_row, original_rows[ws.title])
            if eval_row != template_eval_row:
                _copy_eval_formula_row(ws_fn, template_eval_row, eval_row)
                _copy_eval_formula_row(ws_sf, template_eval_row, eval_row)
            worker = sorted_workers[idx]
            _clear_eval_marks(ws_fn, eval_row, "FUNCTIONAL", end_col=fn_mark_end)
            _clear_eval_marks(ws_sf, eval_row, "SAFETY", end_col=sf_mark_end)
            _write_eval_marks(ws_fn, eval_row, worker.get("functional_assessment"), "FUNCTIONAL")
            _write_eval_marks(ws_sf, eval_row, worker.get("safety_assessment"), "SAFETY")
            ws_fn.cell(eval_row, 44).value = _total_formula("FUNCTIONAL", eval_row, adjustments[idx]["FUNCTIONAL"])
            ws_sf.cell(eval_row, 40).value = _total_formula("SAFETY", eval_row, adjustments[idx]["SAFETY"])

        for row in range(SHEET_EVAL_START_ROW + n, max_template_row + 1):
            _clear_eval_marks(ws_fn, row, "FUNCTIONAL", end_col=fn_mark_end)
            _clear_eval_marks(ws_sf, row, "SAFETY", end_col=sf_mark_end)

        lookup = wb[profile["site_lookup_sheet"]]
        sites = {str(worker.get("site_code") or ""): str(worker.get("site_name") or "") for worker in sorted_workers}
        for number, (code, name) in enumerate(sorted(sites.items()), 2):
            lookup.cell(number, 2).value = code
            lookup.cell(number, 3).value = name
            lookup.cell(number, 2).data_type = "s"
            lookup.cell(number, 3).data_type = "s"
        for ws, start in [(ws1, SHEET1_DATA_START_ROW), (ws_fn, SHEET_EVAL_START_ROW), (ws_sf, SHEET_EVAL_START_ROW)]:
            _limit_output_rows(ws, start, n)
        _limit_output_rows(lookup, 2, len(sites))
        wb.active = wb.sheetnames.index(sheet1_name)
        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        buf.seek(0)
        return buf.getvalue()
