from __future__ import annotations

import base64
import hashlib
import re
import shutil
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.etree import ElementTree as ET


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_PNG_DATA_URL = re.compile(r"^data:image/png;base64,(?P<payload>[A-Za-z0-9+/=\r\n]+)$")
_MAX_PNG_BYTES = 12 * 1024 * 1024
_APPROVED_TEMPLATE_SHA256 = "A5A43555CA1E771177EC565F9E4021D9ED93751921BC6C27D5BB1D5D5D4EBBD5"

ET.register_namespace("", _MAIN_NS)


def _cell(sheet: ET.Element, address: str) -> ET.Element:
    sheet_data = sheet.find(f"{{{_MAIN_NS}}}sheetData")
    if sheet_data is None:
        raise ValueError("워크시트 데이터가 없습니다.")
    row_number = int(re.search(r"\d+", address).group())
    row = next(
        (item for item in sheet_data if int(item.attrib.get("r", "0")) == row_number),
        None,
    )
    if row is None:
        row = ET.SubElement(sheet_data, f"{{{_MAIN_NS}}}row", {"r": str(row_number)})
    found = next((item for item in row if item.attrib.get("r") == address), None)
    if found is not None:
        return found
    return ET.SubElement(row, f"{{{_MAIN_NS}}}c", {"r": address})


def _clear_value(cell: ET.Element) -> None:
    for tag in ("f", "v", "is"):
        node = cell.find(f"{{{_MAIN_NS}}}{tag}")
        if node is not None:
            cell.remove(node)


def _write_text(sheet: ET.Element, address: str, value: object) -> None:
    cell = _cell(sheet, address)
    _clear_value(cell)
    cell.attrib["t"] = "inlineStr"
    inline = ET.SubElement(cell, f"{{{_MAIN_NS}}}is")
    text = ET.SubElement(inline, f"{{{_MAIN_NS}}}t")
    rendered = "" if value is None else str(value)
    if rendered != rendered.strip():
        text.attrib[f"{{{_XML_NS}}}space"] = "preserve"
    text.text = rendered


def _write_number(sheet: ET.Element, address: str, value: int | float) -> None:
    cell = _cell(sheet, address)
    _clear_value(cell)
    cell.attrib["t"] = "n"
    ET.SubElement(cell, f"{{{_MAIN_NS}}}v").text = str(value)


def _excel_serial(value: str | date) -> int:
    parsed = value if isinstance(value, date) else date.fromisoformat(value)
    return (parsed - date(1899, 12, 30)).days


def _decode_png(data_url: str | None) -> bytes | None:
    if not data_url:
        return None
    match = _PNG_DATA_URL.fullmatch(data_url.strip())
    if match is None:
        raise ValueError("도면은 PNG 데이터 형식이어야 합니다.")
    try:
        content = base64.b64decode(match.group("payload"), validate=True)
    except ValueError as exc:
        raise ValueError("도면 PNG를 해석할 수 없습니다.") from exc
    if not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("도면 파일이 정상적인 PNG가 아닙니다.")
    if len(content) > _MAX_PNG_BYTES:
        raise ValueError("도면 PNG는 12MB 이하여야 합니다.")
    return content


def _workbook_values(document: dict) -> tuple[dict[str, object], dict[str, object]]:
    work_date = document.get("work_date") or date.today().isoformat()
    worker_count = int(document.get("worker_count") or 0)
    total_count = int(document.get("total_count") or worker_count)
    manager_count = int(document.get("manager_count") or 0)
    signal_count = int(document.get("signal_count") or 0)
    manager_name = document.get("manager_name") or ""
    site_name = document.get("site_name") or "쿠팡 양지 5"
    site_display = re.sub(r"^\[3\.쿠팡\]\s*", "", site_name).replace(" 전기공사", "")
    fixed = {
        "D5": "(주)부현전기",
        "D6": site_name,
        "D7": site_display,
        "D8": manager_name,
        "D9": document.get("start_time") or "07:00",
        "D10": document.get("end_time") or "17:00",
        "D11": "유" if int(document.get("forklift_owned") or 0) > 0 else "무",
        "D12": "유" if int(document.get("lift_owned") or 0) > 0 else "무",
        "D15": document.get("contacts") or manager_name,
    }
    daily = {
        "D5": ("date", _excel_serial(work_date)),
        "D6": float(document.get("progress_rate") or 0) / 100,
        "D7": document.get("start_time") or "07:00",
        "D8": document.get("end_time") or "17:00",
        "D10": manager_count,
        "D11": worker_count,
        "D12": signal_count,
        "D13": int(document.get("fire_watch_count") or 0),
        "D15": document.get("extra_time") or "",
        "D16": int(document.get("extra_people") or 0),
        "D17": document.get("extra_work") or "",
        "D18": document.get("workplace") or "",
        "D20": int(document.get("forklift_used") or 0),
        "D21": int(document.get("lift_used") or 0),
        "D23": document.get("overtime") or "무",
        "D24": document.get("fire_work") or "무",
        "D25": int(document.get("foreign_worker_count") or 0),
        "D26": 0,
        "D27": "무",
        "D29": "유" if "추락" in (document.get("hazard") or "") else "무",
        "D30": "무",
        "D31": "유" if "전기" in (document.get("work_description") or "") else "무",
        "D32": "무",
        "D33": "무",
        "B37": document.get("floor") or "",
        "C37": document.get("work_description") or "",
        "F37": total_count,
        "G37": document.get("hazard") or "",
        "H37": "",
        "I37": "O",
        "B53": document.get("work_description") or "",
        "F53": document.get("hazard") or "",
        "H53": document.get("control") or "",
        "D59": document.get("workplace") or "",
    }
    jobs = document.get("today_jobs") or [
        {
            "floor": document.get("floor") or "",
            "workplace": document.get("workplace") or "",
            "description": document.get("work_description") or "",
            "people": total_count,
        }
    ]
    for index in range(5):
        row = 37 + index
        job = jobs[index] if index < len(jobs) else {}
        daily[f"B{row}"] = job.get("floor") or ""
        daily[f"C{row}"] = " ".join(
            value for value in (job.get("workplace"), job.get("description")) if value
        )
        daily[f"F{row}"] = int(job.get("people") or 0)
        daily[f"G{row}"] = document.get("hazard") or "" if job else ""
        daily[f"H{row}"] = ""
        daily[f"I{row}"] = "O" if job else ""
    return fixed, daily


def _patch_sheet(xml_bytes: bytes, values: dict[str, object]) -> bytes:
    root = ET.fromstring(xml_bytes)
    for address, value in values.items():
        if isinstance(value, tuple) and value[0] == "date":
            _write_number(root, address, value[1])
        elif isinstance(value, (int, float)):
            _write_number(root, address, value)
        else:
            _write_text(root, address, value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _force_recalculation(xml_bytes: bytes) -> bytes:
    root = ET.fromstring(xml_bytes)
    calc = root.find(f"{{{_MAIN_NS}}}calcPr")
    if calc is None:
        calc = ET.SubElement(root, f"{{{_MAIN_NS}}}calcPr")
    calc.attrib.update({"calcMode": "auto", "fullCalcOnLoad": "1", "forceFullCalc": "1"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def generate_submission_workbook(
    template_path: Path,
    output_path: Path,
    document: dict,
    drawing_png: str | None,
) -> Path:
    if not template_path.is_file():
        raise FileNotFoundError("승인된 쿠팡 양지 원본 템플릿이 서버에 없습니다.")
    actual_hash = hashlib.sha256(template_path.read_bytes()).hexdigest().upper()
    if actual_hash != _APPROVED_TEMPLATE_SHA256:
        raise ValueError("쿠팡 양지 원본 템플릿의 무결성 값이 일치하지 않습니다.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    png = _decode_png(drawing_png)
    fixed, daily = _workbook_values(document)
    replacements: dict[str, bytes] = {}
    with zipfile.ZipFile(template_path, "r") as source:
        replacements["xl/worksheets/sheet1.xml"] = _patch_sheet(
            source.read("xl/worksheets/sheet1.xml"),
            daily,
        )
        replacements["xl/worksheets/sheet2.xml"] = _patch_sheet(
            source.read("xl/worksheets/sheet2.xml"),
            fixed,
        )
        replacements["xl/workbook.xml"] = _force_recalculation(
            source.read("xl/workbook.xml")
        )
        if png is not None:
            floor = (document.get("floor") or "").upper()
            replacements["xl/media/image11.png" if floor == "6F" else "xl/media/image10.png"] = png
        temp = output_path.with_name(f".{output_path.name}.{datetime.now().timestamp():.0f}.tmp")
        try:
            with zipfile.ZipFile(temp, "w") as target:
                for item in source.infolist():
                    target.writestr(item, replacements.get(item.filename, source.read(item.filename)))
            with zipfile.ZipFile(temp, "r") as check:
                bad = check.testzip()
                if bad:
                    raise ValueError(f"생성된 XLSX 압축 검증 실패: {bad}")
                required = {
                    "xl/worksheets/sheet1.xml",
                    "xl/worksheets/sheet2.xml",
                    "xl/media/image10.png",
                    "xl/media/image11.png",
                }
                if not required.issubset(check.namelist()):
                    raise ValueError("생성된 XLSX의 필수 구성요소가 누락됐습니다.")
            shutil.move(temp, output_path)
        finally:
            temp.unlink(missing_ok=True)
    return output_path
