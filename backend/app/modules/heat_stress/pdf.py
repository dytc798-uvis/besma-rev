from __future__ import annotations

import base64
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.modules.heat_stress.service import ACTION_LABELS, parse_actions


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
