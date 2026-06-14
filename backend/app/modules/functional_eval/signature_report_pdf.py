"""기능인제 서명·평가완료보고서 PDF (한글 HYGothic)."""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.modules.functional_eval.eval_catalog import normalize_grade_code

KOREAN_FONT = "HYGothic-Medium"
_FONT_REGISTERED = False

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def ensure_korean_font() -> str:
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont(KOREAN_FONT))
        _FONT_REGISTERED = True
    return KOREAN_FONT


def _grade_cell(assessment: dict[str, Any] | None) -> str:
    if not assessment or not assessment.get("is_complete"):
        return "미평가"
    code = normalize_grade_code(str(assessment.get("grade_code") or "")) or ""
    label = str(assessment.get("grade_label") or "").strip()
    if code:
        return f"{code}({label.replace('등급', '')})" if label else code
    return label or "—"


def _draw_signature_image(c: canvas.Canvas, signature_data: str, x: float, y: float, w: float, h: float) -> None:
    from PIL import Image
    from reportlab.lib.utils import ImageReader

    from app.modules.functional_eval.signature_service import _decode_png_bytes

    png_bytes = _decode_png_bytes(signature_data)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    c.drawImage(ImageReader(img), x, y, width=w, height=h, preserveAspectRatio=True, anchor="sw", mask="auto")


def _draw_worker_table(
    c: canvas.Canvas,
    *,
    font: str,
    y: float,
    title: str,
    workers: list[dict[str, Any]],
) -> float:
    c.setFont(font, 11)
    c.drawString(MARGIN, y, title)
    y -= 8 * mm
    col_x = [MARGIN, MARGIN + 12 * mm, MARGIN + 52 * mm, MARGIN + 82 * mm, MARGIN + 112 * mm]
    headers = ["No", "성명", "기능(2-1)", "안전(2-2)", "비고"]
    c.setFont(font, 9)
    for i, h in enumerate(headers):
        c.drawString(col_x[i], y, h)
    y -= 5 * mm
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 4 * mm
    c.setFont(font, 9)
    for idx, w in enumerate(workers, start=1):
        if y < 25 * mm:
            c.showPage()
            c.setFont(font, 9)
            y = PAGE_H - 25 * mm
        c.drawString(col_x[0], y, str(idx))
        c.drawString(col_x[1], y, str(w.get("name") or "")[:10])
        c.drawString(col_x[2], y, _grade_cell(w.get("functional_assessment")))
        c.drawString(col_x[3], y, _grade_cell(w.get("safety_assessment")))
        c.drawString(col_x[4], y, str(w.get("note") or "")[:12])
        y -= 5 * mm
    return y - 6 * mm


def _draw_approval_boxes(
    c: canvas.Canvas,
    *,
    font: str,
    y_bottom: float,
    boxes: list[dict[str, Any]],
    signature_overlays: list[dict[str, Any]] | None = None,
) -> None:
    """boxes: role, name, signed. signature_overlays: role, signature_data, x_offset index."""
    box_h = 26 * mm
    box_y = y_bottom
    n = max(len(boxes), 1)
    col_w = (PAGE_W - 2 * MARGIN) / n
    c.setFont(font, 10)
    c.drawString(MARGIN, box_y + box_h + 3 * mm, "결재")
    overlays_by_role = {o["role"]: o for o in (signature_overlays or [])}
    for idx, box in enumerate(boxes):
        x = MARGIN + idx * col_w
        c.rect(x, box_y, col_w - 2 * mm, box_h, stroke=1, fill=0)
        c.setFont(font, 8)
        c.drawString(x + 2 * mm, box_y + box_h - 4 * mm, str(box.get("role") or ""))
        name = str(box.get("name") or "").strip()
        if name:
            c.setFont(font, 7)
            c.drawString(x + 2 * mm, box_y + 3 * mm, name[:14])
        role = box.get("role") or ""
        ov = overlays_by_role.get(role)
        if ov and ov.get("signature_data"):
            _draw_signature_image(c, ov["signature_data"], x + 8 * mm, box_y + 14 * mm, col_w - 12 * mm, 10 * mm)


def generate_consent_pdf(
    *,
    signer_name: str,
    signer_login_id: str,
    consent_body: str,
    signature_data: str,
    signed_at: datetime,
) -> bytes:
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(font, 16)
    title = "기능인인정제 평가 동의서"
    tw = c.stringWidth(title, font, 16)
    c.drawString((PAGE_W - tw) / 2, PAGE_H - 28 * mm, title)

    c.setFont(font, 10)
    y = PAGE_H - 42 * mm
    for line in consent_body.strip().splitlines():
        text = line.strip()
        if text:
            c.drawString(MARGIN, y, text)
            y -= 6 * mm

    y -= 4 * mm
    c.drawString(MARGIN, y, f"서명자: {signer_name} ({signer_login_id})")
    y -= 6 * mm
    c.drawString(MARGIN, y, f"서명일시: {signed_at.strftime('%Y-%m-%d %H:%M')}")

    sig_w, sig_h = 70 * mm, 22 * mm
    _draw_signature_image(c, signature_data, (PAGE_W - sig_w) / 2, PAGE_H - 95 * mm, sig_w, sig_h)
    c.save()
    return buf.getvalue()


def generate_team_completion_report_pdf(
    *,
    period_title: str,
    site_name: str,
    team_leader_name: str,
    team_leader_login: str,
    workers: list[dict[str, Any]],
    signature_data: str,
    signed_at: datetime,
    manager_approval: dict[str, Any] | None = None,
) -> bytes:
    """팀장 평가완료보고서 — 팀원 등급표 + 팀장 서명 + (선택) 소장 승인."""
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(font, 16)
    title = "평가완료보고서"
    tw = c.stringWidth(title, font, 16)
    c.drawString((PAGE_W - tw) / 2, PAGE_H - 28 * mm, title)
    c.setFont(font, 10)
    y = PAGE_H - 40 * mm
    for line in [
        f"평가기간: {period_title}",
        f"현장: {site_name}",
        f"작성: 팀장 {team_leader_name} ({team_leader_login})",
        f"팀원 {len(workers)}명 · 서명일시: {signed_at.strftime('%Y-%m-%d %H:%M')}",
    ]:
        c.drawString(MARGIN, y, line)
        y -= 6 * mm

    y = _draw_worker_table(c, font=font, y=y - 4 * mm, title="■ 팀원 평가 등급", workers=workers)

    c.setFont(font, 10)
    c.drawString(MARGIN, y, "팀장 서명")
    _draw_signature_image(c, signature_data, MARGIN, y - 4 * mm, 60 * mm, 18 * mm)

    boxes = [
        {"role": "팀장", "name": team_leader_name, "signed": True},
        {"role": "소장", "name": (manager_approval or {}).get("signer_name", ""), "signed": bool(manager_approval)},
        {"role": "안전보건실장", "name": "", "signed": False},
        {"role": "대표이사", "name": "", "signed": False},
    ]
    overlays = [{"role": "팀장", "signature_data": signature_data}]
    if manager_approval and manager_approval.get("signature_data"):
        overlays.append({"role": "소장", "signature_data": manager_approval["signature_data"]})
    _draw_approval_boxes(c, font=font, y_bottom=22 * mm, boxes=boxes, signature_overlays=overlays)
    c.save()
    return buf.getvalue()


def generate_site_completion_report_pdf(
    *,
    period_title: str,
    site_name: str,
    site_code: str,
    manager_name: str,
    manager_login: str,
    team_sections: list[dict[str, Any]],
    direct_workers: list[dict[str, Any]],
    signature_data: str,
    signed_at: datetime,
    prior_signatures: list[dict[str, Any]] | None = None,
) -> bytes:
    """소장 평가완료보고서 — 갑지(서명) + 팀장별·직영 등급표."""
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    # --- 갑지 ---
    c.setFont(font, 18)
    title = "평가완료보고서 (갑지)"
    tw = c.stringWidth(title, font, 18)
    c.drawString((PAGE_W - tw) / 2, PAGE_H - 28 * mm, title)
    c.setFont(font, 10)
    y = PAGE_H - 42 * mm
    total_workers = sum(len(s.get("workers") or []) for s in team_sections) + len(direct_workers)
    for line in [
        f"평가기간: {period_title}",
        f"현장: {site_name} ({site_code})",
        f"소장: {manager_name} ({manager_login})",
        f"평가 대상: 총 {total_workers}명 (팀 {len(team_sections)}개 · 직영 {len(direct_workers)}명)",
        f"제출일시: {signed_at.strftime('%Y-%m-%d %H:%M')}",
    ]:
        c.drawString(MARGIN, y, line)
        y -= 6 * mm

    c.setFont(font, 10)
    c.drawString(MARGIN, y, "■ 첨부 목차")
    y -= 6 * mm
    for i, sec in enumerate(team_sections, start=1):
        c.drawString(MARGIN + 4 * mm, y, f"{i}. {sec.get('leader_label', '팀')} 팀원 평가표 ({len(sec.get('workers') or [])}명)")
        y -= 5 * mm
    if direct_workers:
        c.drawString(MARGIN + 4 * mm, y, f"{len(team_sections) + 1}. 소장 직영 평가표 ({len(direct_workers)}명)")
        y -= 5 * mm

    _draw_signature_image(c, signature_data, (PAGE_W - 65 * mm) / 2, PAGE_H - 105 * mm, 65 * mm, 20 * mm)

    prior = prior_signatures or []
    hq_sig = next((p for p in prior if p.get("stage") == "HQ"), None)
    ceo_sig = next((p for p in prior if p.get("stage") == "CEO"), None)
    boxes = [
        {"role": "소장", "name": manager_name, "signed": True},
        {"role": "안전보건실장", "name": (hq_sig or {}).get("signer_name", ""), "signed": bool(hq_sig)},
        {"role": "대표이사", "name": (ceo_sig or {}).get("signer_name", ""), "signed": bool(ceo_sig)},
    ]
    overlays = [{"role": "소장", "signature_data": signature_data}]
    if hq_sig and hq_sig.get("signature_data"):
        overlays.append({"role": "안전보건실장", "signature_data": hq_sig["signature_data"]})
    if ceo_sig and ceo_sig.get("signature_data"):
        overlays.append({"role": "대표이사", "signature_data": ceo_sig["signature_data"]})
    _draw_approval_boxes(c, font=font, y_bottom=20 * mm, boxes=boxes, signature_overlays=overlays)

    # --- 팀별 / 직영 본문 ---
    for sec in team_sections:
        c.showPage()
        c.setFont(font, 14)
        c.drawString(MARGIN, PAGE_H - 25 * mm, f"평가완료보고서 — {sec.get('leader_label', '팀')}")
        y = PAGE_H - 35 * mm
        y = _draw_worker_table(c, font=font, y=y, title="■ 팀원 평가 등급", workers=sec.get("workers") or [])
        if sec.get("team_leader_signed_at"):
            c.setFont(font, 8)
            c.drawString(MARGIN, y, f"팀장 서명: {sec.get('team_leader_signed_at', '')}")
        if sec.get("manager_approved_at"):
            c.drawString(MARGIN, y - 4 * mm, f"소장 승인: {sec.get('manager_approved_at', '')}")

    if direct_workers:
        c.showPage()
        c.setFont(font, 14)
        c.drawString(MARGIN, PAGE_H - 25 * mm, "평가완료보고서 — 소장 직영")
        _draw_worker_table(
            c, font=font, y=PAGE_H - 35 * mm, title="■ 직영 평가 등급", workers=direct_workers
        )

    c.save()
    return buf.getvalue()


def generate_hq_review_report_pdf(
    *,
    period_title: str,
    site_summaries: list[dict[str, Any]],
    officer_comment: str,
    director_comment: str,
    signature_data: str,
    signer_name: str,
    signed_at: datetime,
) -> bytes:
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(font, 16)
    title = "기능인인정제 본사 검토·승인서"
    tw = c.stringWidth(title, font, 16)
    c.drawString((PAGE_W - tw) / 2, PAGE_H - 28 * mm, title)
    c.setFont(font, 10)
    y = PAGE_H - 42 * mm
    c.drawString(MARGIN, y, f"평가기간: {period_title}")
    y -= 8 * mm
    c.setFont(font, 11)
    c.drawString(MARGIN, y, "■ 안전보건 담당자 검토")
    y -= 6 * mm
    c.setFont(font, 9)
    for line in _wrap_text(officer_comment or "(검토 코멘트 없음)", 70):
        c.drawString(MARGIN + 4 * mm, y, line)
        y -= 5 * mm
    y -= 4 * mm
    c.setFont(font, 11)
    c.drawString(MARGIN, y, "■ 안전보건실장 최종 코멘트")
    y -= 6 * mm
    c.setFont(font, 9)
    for line in _wrap_text(director_comment or "(최종 코멘트 없음)", 70):
        c.drawString(MARGIN + 4 * mm, y, line)
        y -= 5 * mm
    y -= 6 * mm
    c.setFont(font, 10)
    c.drawString(MARGIN, y, f"승인 현장 {len(site_summaries)}개소 · {signer_name} · {signed_at.strftime('%Y-%m-%d %H:%M')}")
    _draw_signature_image(c, signature_data, MARGIN, 35 * mm, 60 * mm, 18 * mm)
    c.save()
    return buf.getvalue()


def generate_ceo_final_report_pdf(
    *,
    period_title: str,
    site_count: int,
    hq_review_note: str,
    signature_data: str,
    signer_name: str,
    signed_at: datetime,
) -> bytes:
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(font, 16)
    title = "기능인인정제 대표이사 최종승인서"
    tw = c.stringWidth(title, font, 16)
    c.drawString((PAGE_W - tw) / 2, PAGE_H - 28 * mm, title)
    c.setFont(font, 10)
    y = PAGE_H - 45 * mm
    for line in [
        f"평가기간: {period_title}",
        f"승인 현장: {site_count}개소",
        f"본사 검토 확인 후 최종 승인합니다.",
        f"승인자: {signer_name}",
        f"일시: {signed_at.strftime('%Y-%m-%d %H:%M')}",
    ]:
        c.drawString(MARGIN, y, line)
        y -= 7 * mm
    if hq_review_note:
        c.drawString(MARGIN, y, f"본사 검토 요약: {hq_review_note[:80]}")
    _draw_signature_image(c, signature_data, (PAGE_W - 65 * mm) / 2, PAGE_H - 100 * mm, 65 * mm, 22 * mm)
    c.save()
    return buf.getvalue()


def _wrap_text(text: str, width: int) -> list[str]:
    text = (text or "").replace("\r", "").strip()
    if not text:
        return [""]
    lines: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        while len(para) > width:
            lines.append(para[:width])
            para = para[width:]
        if para:
            lines.append(para)
    return lines or [""]
