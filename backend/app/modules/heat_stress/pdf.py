from __future__ import annotations

import base64
import io
from datetime import date, datetime

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.modules.heat_stress.service import ACTION_LABELS, parse_actions, policy_for


def _font() -> str:
    name = "HYSMyeongJo-Medium"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    except Exception:
        return "Helvetica"
    return name


def _signature_bytes(data: str | None) -> bytes | None:
    if not data:
        return None
    try:
        return base64.b64decode(data.split(",", 1)[-1], validate=True)
    except Exception:
        return None


def _text(c: canvas.Canvas, value: str, x: float, y: float, font: str, size: int = 9) -> None:
    c.setFont(font, size)
    c.drawString(x, y, value)


def build_default_pdf(record, site_name: str) -> bytes:
    font = _font()
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    width, height = A4
    _text(c, "체감온도 및 온열질환 예방조치 기록지", 35 * mm, height - 24 * mm, font, 17)
    _text(c, f"현장명: {site_name}", 18 * mm, height - 38 * mm, font, 10)
    _text(c, f"점검일시: {record.measured_at.strftime('%Y-%m-%d %H:%M')}", 110 * mm, height - 38 * mm, font, 10)
    rows = [
        ("작업장소 / 공정", f"{record.work_location} / {record.work_process or '-'}"),
        ("측정구분", "현장 실측" if record.measurement_source == "ON_SITE" else "기상청 자료"),
        ("온도 / 습도", f"{record.air_temperature_c:.1f}℃ / {record.relative_humidity_pct:.1f}%"),
        ("체감온도 / 판정", f"{record.apparent_temperature_c:.1f}℃ / {record.risk_level}"),
        ("법정 필요조치", record.legal_guidance),
        ("회사 안내", record.company_guidance),
        ("실제 실시조치", ", ".join(ACTION_LABELS.get(a, a) for a in parse_actions(record.actual_actions_json)) or "미입력"),
        ("특이사항", record.action_notes or "-"),
        ("조치확인", "추가 조치 필요" if record.action_compliance == "ACTION_REQUIRED" else "기록 완료"),
    ]
    y = height - 50 * mm
    for label, value in rows:
        c.rect(18 * mm, y - 13 * mm, 174 * mm, 13 * mm)
        _text(c, label, 21 * mm, y - 8 * mm, font, 8)
        text = value
        if len(text) > 70:
            text = text[:68] + "…"
        _text(c, text, 52 * mm, y - 8 * mm, font, 8)
        y -= 13 * mm
    _text(c, "※ 자동 안내는 실시 완료 기록이 아닙니다. 위 ‘실제 실시조치’는 작성자가 확인한 내용입니다.", 18 * mm, y - 7 * mm, font, 8)
    y -= 19 * mm
    sig_w = 82 * mm
    for index, (title, name, signed_at, signature) in enumerate([
        ("점검자", record.recorder_name, record.recorder_signed_at, record.recorder_signature_data),
        ("확인자", record.confirmer_name or "확인 대기", record.confirmer_signed_at, record.confirmer_signature_data),
    ]):
        x = 18 * mm + index * 88 * mm
        c.rect(x, y - 34 * mm, sig_w, 34 * mm)
        _text(c, f"{title}: {name}", x + 3 * mm, y - 7 * mm, font, 9)
        if signed_at:
            _text(c, signed_at.strftime("%Y-%m-%d %H:%M"), x + 3 * mm, y - 31 * mm, font, 7)
        raw = _signature_bytes(signature)
        if raw:
            try:
                c.drawImage(ImageReader(io.BytesIO(raw)), x + 25 * mm, y - 27 * mm, 50 * mm, 18 * mm, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
    _text(c, f"양식: {record.template_code} / 기록번호: {record.id}", 18 * mm, 13 * mm, font, 7)
    c.save()
    return out.getvalue()


def _short(value: object, limit: int) -> str:
    text = str(value or "-").strip() or "-"
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"


def _draw_lines(
    c: canvas.Canvas,
    lines: list[str],
    x: float,
    top: float,
    font: str,
    size: float = 7,
    leading: float = 3.4 * mm,
) -> None:
    c.setFont(font, size)
    for index, line in enumerate(lines):
        c.drawString(x, top - index * leading, line)


def build_ledger_pdf(
    rows: list[tuple[object, str]],
    date_from: date | None = None,
    date_to: date | None = None,
    group_by_site: bool = False,
) -> bytes:
    """Build a multi-page heat-stress ledger grouped by site and date when requested."""

    font = _font()
    out = io.BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(out, pagesize=page_size)
    width, height = page_size
    margin_x = 10 * mm
    bottom_y = 12 * mm
    row_height = 23 * mm
    site_height = 8 * mm
    date_height = 7 * mm
    header_height = 8 * mm
    columns = [
        ("시간", 16 * mm),
        ("현장", 34 * mm),
        ("작업장소 / 공정", 42 * mm),
        ("온도 / 습도", 25 * mm),
        ("체감 / 단계", 24 * mm),
        ("실제 실시조치", 55 * mm),
        ("점검자 / 서명", 40 * mm),
        ("관리자 확인 / 서명", 41 * mm),
    ]
    table_width = sum(column_width for _, column_width in columns)
    sort_key = (
        (lambda item: (str(item[1]), item[0].measured_at, item[0].id))
        if group_by_site
        else (lambda item: (item[0].measured_at, item[0].id))
    )
    sorted_rows = sorted(rows, key=sort_key)
    site_names = sorted({str(site_name).strip() for _, site_name in sorted_rows if str(site_name).strip()})
    site_label = site_names[0] if len(site_names) == 1 else "전체 현장"

    if date_from and date_to:
        period_label = date_from.isoformat() if date_from == date_to else f"{date_from.isoformat()} ~ {date_to.isoformat()}"
    elif date_from:
        period_label = f"{date_from.isoformat()} 이후"
    elif date_to:
        period_label = f"{date_to.isoformat()} 이전"
    elif sorted_rows:
        measured_dates = [record.measured_at.date() for record, _ in sorted_rows]
        period_label = f"{min(measured_dates).isoformat()} ~ {max(measured_dates).isoformat()}"
    else:
        period_label = "전체 기간"

    page_number = 0

    def start_page() -> float:
        nonlocal page_number
        if page_number:
            c.showPage()
        page_number += 1
        _text(c, f"체감온도 관리대장 - {site_label}", margin_x, height - 14 * mm, font, 16)
        _text(c, f"현장명: {site_label} / 기간: {period_label}", margin_x, height - 23 * mm, font, 8)
        c.setFont(font, 7)
        c.drawRightString(width - margin_x, height - 23 * mm, f"출력: {datetime.now().strftime('%Y-%m-%d %H:%M')} / {page_number}쪽")
        y = height - 29 * mm
        x = margin_x
        c.setFillColorRGB(0.92, 0.95, 0.97)
        for label, column_width in columns:
            c.rect(x, y - header_height, column_width, header_height, fill=1, stroke=1)
            c.setFillColorRGB(0.1, 0.15, 0.2)
            c.setFont(font, 7)
            c.drawCentredString(x + column_width / 2, y - 5.2 * mm, label)
            c.setFillColorRGB(0.92, 0.95, 0.97)
            x += column_width
        c.setFillColorRGB(0, 0, 0)
        return y - header_height

    def draw_date_heading(y: float, day: date, continued: bool = False) -> float:
        c.setFillColorRGB(0.88, 0.96, 0.94)
        c.rect(margin_x, y - date_height, table_width, date_height, fill=1, stroke=1)
        c.setFillColorRGB(0.05, 0.35, 0.31)
        _text(c, f"{day.strftime('%Y년 %m월 %d일')}" + (" (계속)" if continued else ""), margin_x + 3 * mm, y - 4.8 * mm, font, 8)
        c.setFillColorRGB(0, 0, 0)
        return y - date_height

    def draw_site_heading(y: float, name: str, continued: bool = False) -> float:
        c.setFillColorRGB(0.86, 0.91, 0.98)
        c.rect(margin_x, y - site_height, table_width, site_height, fill=1, stroke=1)
        c.setFillColorRGB(0.08, 0.23, 0.48)
        suffix = " (계속)" if continued else ""
        _text(c, f"현장명: {name}{suffix}", margin_x + 3 * mm, y - 5.4 * mm, font, 9)
        c.setFillColorRGB(0, 0, 0)
        return y - site_height

    def draw_signature(signature_data: str | None, x: float, y: float, cell_width: float) -> None:
        raw = _signature_bytes(signature_data)
        if not raw:
            return
        try:
            c.drawImage(
                ImageReader(io.BytesIO(raw)),
                x + 2 * mm,
                y + 2 * mm,
                cell_width - 4 * mm,
                9 * mm,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception:
            return

    y = start_page()
    if not sorted_rows:
        _text(c, "출력할 체감온도 기록이 없습니다.", margin_x, y - 15 * mm, font, 10)

    current_site: str | None = None
    current_day: date | None = None
    for record, site_name in sorted_rows:
        record_day = record.measured_at.date()
        if group_by_site and site_name != current_site:
            if y - site_height - date_height - row_height < bottom_y:
                y = start_page()
            y = draw_site_heading(y, site_name)
            current_site = site_name
            current_day = None
        if record_day != current_day:
            if y - date_height - row_height < bottom_y:
                y = start_page()
                if group_by_site:
                    y = draw_site_heading(y, site_name, continued=True)
            y = draw_date_heading(y, record_day)
            current_day = record_day
        if y - row_height < bottom_y:
            y = start_page()
            if group_by_site:
                y = draw_site_heading(y, site_name, continued=True)
            y = draw_date_heading(y, record_day, continued=True)

        row_bottom = y - row_height
        x = margin_x
        for _, column_width in columns:
            c.rect(x, row_bottom, column_width, row_height, fill=0, stroke=1)
            x += column_width

        risk_label = policy_for(record.apparent_temperature_c)["risk_label"]
        action_labels = [ACTION_LABELS.get(action, action) for action in parse_actions(record.actual_actions_json)]
        locations = [_short(record.work_location, 18), _short(record.work_process or "-", 18)]
        values = [
            [record.measured_at.strftime("%H:%M")],
            [_short(site_name, 16)],
            locations,
            [f"{record.air_temperature_c:.1f}℃", f"{record.relative_humidity_pct:.0f}%"],
            [f"{record.apparent_temperature_c:.1f}℃", _short(risk_label, 10)],
            [_short(", ".join(action_labels) or "미입력", 30), _short(record.action_notes or "", 30)],
            [_short(record.recorder_name, 12), record.recorder_signed_at.strftime("%H:%M") if record.recorder_signed_at else "-"],
            [
                _short(record.confirmer_name or "확인 대기", 12),
                _short(record.confirmer_title or "", 12),
                record.confirmer_signed_at.strftime("%H:%M") if record.confirmer_signed_at else "-",
            ],
        ]
        x = margin_x
        for index, ((_, column_width), lines) in enumerate(zip(columns, values)):
            _draw_lines(c, lines, x + 2 * mm, y - 5 * mm, font, 6.7)
            if index == 6:
                draw_signature(record.recorder_signature_data, x, row_bottom, column_width)
            elif index == 7:
                draw_signature(record.confirmer_signature_data, x, row_bottom, column_width)
            x += column_width
        y = row_bottom

    c.save()
    return out.getvalue()
