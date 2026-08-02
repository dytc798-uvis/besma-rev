from __future__ import annotations

import calendar
import shutil
from copy import copy
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.modules.safety_ledgers.models import SafetyCardExpense, SafetyVehicle, SafetyVehicleLog


CARD_FILENAME = "안전실_법인카드 정산서.xlsx"
VEHICLE_FILENAME = "안전실_업무용승용차 운행기록부.xlsx"
_BLUE = "1F4E78"
_LIGHT_BLUE = "D9EAF7"
_THIN = Side(style="thin", color="A6A6A6")


def _sheet_title(year: int, month: int) -> str:
    return f"{year % 100:02d}년 {month}월"


def _style_table(ws, start_row: int, end_row: int, end_col: int) -> None:
    for row in ws.iter_rows(min_row=start_row, max_row=end_row, min_col=1, max_col=end_col):
        for cell in row:
            cell.border = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
            cell.alignment = Alignment(vertical="center", wrap_text=True)


def build_card_workbook(
    expenses: Iterable[SafetyCardExpense],
    output_path: Path,
    *,
    template_path: Path | None = None,
    site_names_by_date: dict[date, str] | None = None,
) -> Path:
    grouped: dict[tuple[int, int], list[SafetyCardExpense]] = defaultdict(list)
    for row in expenses:
        when = row.used_at or row.created_at
        grouped[(when.year, when.month)].append(row)
    if not grouped:
        now = datetime.now()
        grouped[(now.year, now.month)] = []

    if template_path and template_path.is_file():
        wb = load_workbook(template_path)
        source = wb["5월"] if "5월" in wb.sheetnames else wb.worksheets[0]
        target_sheets = []
        for year, month in sorted(grouped):
            ws = wb.copy_worksheet(source)
            ws.title = f"__safety_card_{year}_{month}"
            target_sheets.append((year, month, ws))
        for ws in list(wb.worksheets):
            if not ws.title.startswith("__safety_card_"):
                wb.remove(ws)
        for year, month, ws in target_sheets:
            ws.title = f"{month}월"
            ws["A2"] = (
                f"사용기간 : {year}년 {month}월 1일 ~ "
                f"{year}년 {month}월 {calendar.monthrange(year, month)[1]}일"
            )
            ws["G2"] = "사용자 : 안전보건실"
            ws["G46"] = "정산인 : 안전보건실 (인)"
            for row_index in range(4, 45):
                ws.cell(row_index, 1, "1" if row_index == 4 else "=ROW()-3")
                for col_index in range(2, 8):
                    ws.cell(row_index, col_index).value = None
            rows = sorted(
                grouped[(year, month)],
                key=lambda item: (item.used_at or item.created_at, item.id),
            )
            if len(rows) > 41:
                raise ValueError(f"{year}년 {month}월 법인카드 내역이 회사 양식의 41행을 초과했습니다.")
            for row_index, item in enumerate(rows, 4):
                when = item.used_at or item.created_at
                ws.cell(row_index, 2, when.date())
                ws.cell(row_index, 3, item.site_name or (site_names_by_date or {}).get(when.date(), ""))
                ws.cell(row_index, 4, item.merchant or "")
                ws.cell(row_index, 5, item.amount)
                ws.cell(row_index, 6, item.description or "")
                note_parts = [
                    item.note,
                ]
                ws.cell(row_index, 7, " / ".join(part for part in note_parts if part))
            ws["E45"] = "=SUM(E4:E44)"
            ws.print_area = "A1:G46"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return output_path

    wb = Workbook()
    wb.remove(wb.active)
    for (year, month), rows in sorted(grouped.items()):
        ws = wb.create_sheet(_sheet_title(year, month))
        ws.merge_cells("A1:G1")
        ws["A1"] = "■ 법인카드 정산서"
        ws["A1"].font = Font(size=18, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=_BLUE)
        ws["A1"].alignment = Alignment(horizontal="center")
        ws.merge_cells("A2:E2")
        ws["A2"] = f"사용기간 : {year}년 {month}월 1일 ~ {year}년 {month}월 {calendar.monthrange(year, month)[1]}일"
        ws["G2"] = "부서 : 안전보건실"
        headers = ["No", "사용일시", "현장명", "사용처", "금액", "내용", "비고(카드끝4자리)"]
        for col, value in enumerate(headers, 1):
            cell = ws.cell(3, col, value)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=_BLUE)
            cell.alignment = Alignment(horizontal="center")
        rows = sorted(rows, key=lambda item: (item.used_at or item.created_at, item.id))
        data_start = 4
        for index, item in enumerate(rows, 1):
            when = item.used_at or item.created_at
            values = [
                index,
                when,
                item.site_name or (site_names_by_date or {}).get(when.date(), ""),
                item.merchant or "",
                item.amount,
                item.description or "",
                " / ".join(x for x in [item.note, f"카드 ****-{item.card_last4}" if item.card_last4 else None] if x),
            ]
            for col, value in enumerate(values, 1):
                ws.cell(data_start + index - 1, col, value)
            ws.cell(data_start + index - 1, 2).number_format = "yyyy-mm-dd hh:mm"
            ws.cell(data_start + index - 1, 5).number_format = '#,##0"원"'
        total_row = max(data_start + len(rows), 5)
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=4)
        ws.cell(total_row, 1, "소계")
        ws.cell(total_row, 5, f"=SUM(E{data_start}:E{total_row - 1})")
        ws.cell(total_row, 5).number_format = '#,##0"원"'
        ws.cell(total_row, 1).font = ws.cell(total_row, 5).font = Font(bold=True)
        _style_table(ws, 3, total_row, 7)
        widths = [7, 19, 24, 24, 14, 38, 24]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.freeze_panes = "A4"
        ws.auto_filter.ref = f"A3:G{max(3, total_row - 1)}"
        ws.sheet_view.showGridLines = False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path


def build_vehicle_workbook(
    vehicle: SafetyVehicle,
    logs: Iterable[SafetyVehicleLog],
    output_path: Path,
    *,
    template_path: Path | None = None,
) -> Path:
    grouped: dict[tuple[int, int], list[SafetyVehicleLog]] = defaultdict(list)
    for row in logs:
        grouped[(row.driven_on.year, row.driven_on.month)].append(row)
    if not grouped:
        now = datetime.now()
        grouped[(now.year, now.month)] = []

    if template_path and template_path.is_file():
        wb = load_workbook(template_path)
        source = wb["7월"] if "7월" in wb.sheetnames else wb.worksheets[0]
        target_sheets = []
        for year, month in sorted(grouped):
            title = f"{month}월"
            if title in wb.sheetnames:
                ws = wb[title]
            else:
                ws = wb.copy_worksheet(source)
                for validation in source.data_validations.dataValidation:
                    ws.add_data_validation(copy(validation))
                ws.title = title
            target_sheets.append((year, month, ws))
        keep = {id(ws) for _year, _month, ws in target_sheets}
        for ws in list(wb.worksheets):
            if id(ws) not in keep:
                wb.remove(ws)

        running_end: int | None = None
        for year, month, ws in target_sheets:
            rows = sorted(grouped[(year, month)], key=lambda item: (item.driven_on, item.created_at, item.id))
            readings = [item.odometer_km for item in rows if item.odometer_km is not None]
            first = rows[0] if rows else None
            inferred_start = (
                max(0, int(first.odometer_km - first.trip_km))
                if first and first.odometer_km is not None and first.trip_km is not None
                else (min(readings) if readings else None)
            )
            start_km = running_end if running_end is not None else inferred_start
            calculated_end = (
                int(round(start_km + sum(float(item.trip_km or 0) for item in rows)))
                if start_km is not None
                else None
            )
            end_candidates = readings + ([calculated_end] if calculated_end is not None else [])
            if end_candidates:
                running_end = max(end_candidates)

            ws["A7"] = vehicle.vehicle_name
            ws["E7"] = vehicle.plate_number
            ws["G7"] = start_km
            ws["H7"] = vehicle.ownership_type
            last_day = calendar.monthrange(year, month)[1]
            for day in range(1, 32):
                row_index = 10 + day
                if day <= last_day:
                    ws.cell(row_index, 1, year)
                    ws.cell(row_index, 2, month)
                    ws.cell(row_index, 3, day)
                    ws.cell(row_index, 4, vehicle.department)
                    for col_index in range(5, 9):
                        ws.cell(row_index, col_index).value = None
                else:
                    for col_index in range(1, 9):
                        ws.cell(row_index, col_index).value = None
            for item in rows:
                row_index = 10 + item.driven_on.day
                ws.cell(row_index, 5, item.driver_name)
                ws.cell(row_index, 6, item.use_type if str(item.use_type).startswith(tuple("1234567")) else "6.업무용(왕복)")
                ws.cell(row_index, 7, item.trip_km)
                ws.cell(row_index, 8, item.purpose or "")
            ws["G42"] = "=SUM(G11:G41,G7)"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        return output_path

    wb = Workbook()
    wb.remove(wb.active)
    running_end: int | None = None
    for (year, month), rows in sorted(grouped.items()):
        rows = sorted(rows, key=lambda item: (item.driven_on, item.created_at, item.id))
        readings = [item.odometer_km for item in rows if item.odometer_km is not None]
        first = rows[0] if rows else None
        inferred_start = (
            max(0, int(first.odometer_km - first.trip_km))
            if first and first.odometer_km is not None and first.trip_km is not None
            else (min(readings) if readings else None)
        )
        start_km = running_end if running_end is not None else inferred_start
        calculated_end = (
            int(round(start_km + sum(float(item.trip_km or 0) for item in rows)))
            if start_km is not None
            else None
        )
        end_candidates = readings + ([calculated_end] if calculated_end is not None else [])
        if end_candidates:
            running_end = max(end_candidates)
        ws = wb.create_sheet(_sheet_title(year, month))
        ws.merge_cells("A1:H1")
        ws["A1"] = "운행기록부 (업무용승용차)"
        ws["A1"].font = Font(size=18, bold=True, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor=_BLUE)
        ws["A1"].alignment = Alignment(horizontal="center")
        info = [
            ("A3", "①차종", "B3", vehicle.vehicle_name),
            ("D3", "②차량번호", "E3", vehicle.plate_number),
            ("G3", "③기초km", "H3", start_km),
            ("A4", "④명의구분", "B4", vehicle.ownership_type),
            ("D4", "부서", "E4", vehicle.department),
            (
                "G4",
                "운전자",
                "H4",
                " · ".join(driver.driver_name for driver in getattr(vehicle, "drivers", []) if driver.is_active),
            ),
        ]
        for label_cell, label, value_cell, value in info:
            ws[label_cell] = label
            ws[label_cell].font = Font(bold=True)
            ws[label_cell].fill = PatternFill("solid", fgColor=_LIGHT_BLUE)
            ws[value_cell] = value
        headers = ["년도", "월", "일", "부서", "성명", "구분", "주행km", "비고"]
        for col, value in enumerate(headers, 1):
            cell = ws.cell(6, col, value)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=_BLUE)
            cell.alignment = Alignment(horizontal="center")
        for index, item in enumerate(rows, 7):
            values = [
                item.driven_on.year,
                item.driven_on.month,
                item.driven_on.day,
                vehicle.department,
                item.driver_name,
                item.use_type,
                item.trip_km,
                item.purpose or "",
            ]
            for col, value in enumerate(values, 1):
                ws.cell(index, col, value)
        total_row = max(7 + len(rows), 8)
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=6)
        ws.cell(total_row, 1, "월 주행거리 합계")
        ws.cell(total_row, 7, f"=SUM(G7:G{total_row - 1})")
        ws.cell(total_row, 1).font = ws.cell(total_row, 7).font = Font(bold=True)
        _style_table(ws, 3, 4, 8)
        _style_table(ws, 6, total_row, 8)
        widths = [9, 7, 7, 16, 13, 19, 12, 42]
        for col, width in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(col)].width = width
        ws.freeze_panes = "A7"
        ws.sheet_view.showGridLines = False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return output_path


def copy_exports_to_nas(paths: Iterable[Path], nas_root: Path | None) -> None:
    if nas_root is None:
        return
    nas_root.mkdir(parents=True, exist_ok=True)
    for source in paths:
        temp = nas_root / f".{source.name}.tmp"
        shutil.copy2(source, temp)
        temp.replace(nas_root / source.name)
