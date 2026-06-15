"""기능인제 서명·평가완료보고서 PDF (맑은 고딕)."""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.core.datetime_utils import format_kst_datetime_label, format_kst_datetime_short
from app.modules.functional_eval.eval_catalog import normalize_grade_code

KOREAN_FONT = "MalgunGothic"
KOREAN_FONT_FALLBACK = "HYGothic-Medium"
REPORT_TITLE = "기능인인정제 평가 보고서"
REPORT_TITLE_COVER = "기능인인정제 평가 보고서 (갑지)"
REPORT_TITLE_DETAIL = "기능인인정제 평가 보고서 (상세)"
_FONT_REGISTERED = False

_MALGUN_CANDIDATES = (
    Path(r"C:\Windows\Fonts\malgun.ttf"),
    Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
)

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def ensure_korean_font() -> str:
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        from reportlab.pdfbase.ttfonts import TTFont

        for path in _MALGUN_CANDIDATES:
            if path.is_file():
                pdfmetrics.registerFont(TTFont(KOREAN_FONT, str(path)))
                _FONT_REGISTERED = True
                return KOREAN_FONT
        pdfmetrics.registerFont(UnicodeCIDFont(KOREAN_FONT_FALLBACK))
        _FONT_REGISTERED = True
        return KOREAN_FONT_FALLBACK
    registered = pdfmetrics.getRegisteredFontNames()
    return KOREAN_FONT if KOREAN_FONT in registered else KOREAN_FONT_FALLBACK


def _grade_cell(assessment: dict[str, Any] | None) -> str:
    if not assessment or not assessment.get("is_complete"):
        return "미평가"
    code = normalize_grade_code(str(assessment.get("grade_code") or "")) or ""
    if code:
        return code
    label = str(assessment.get("grade_label") or "").strip()
    return label.replace("등급", "") if label else "—"


def _workers_for_table(workers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """이름·등급 모두 없는 빈 행은 표에서 제외."""
    out: list[dict[str, Any]] = []
    for w in workers:
        name = str(w.get("name") or "").strip()
        has_grade = bool(w.get("functional_assessment") or w.get("safety_assessment"))
        if name or has_grade:
            out.append(w)
    return out


def _draw_file_image(c: canvas.Canvas, path: str | Path, x: float, y: float, w: float, h: float) -> None:
    from PIL import Image
    from reportlab.lib.utils import ImageReader

    p = Path(path)
    if not p.is_file():
        return
    img = Image.open(p).convert("RGB")
    c.drawImage(ImageReader(img), x, y, width=w, height=h, preserveAspectRatio=True, anchor="sw")


def _draw_worker_table(
    c: canvas.Canvas,
    *,
    font: str,
    y: float,
    title: str,
    workers: list[dict[str, Any]],
    title_size: float = 12,
    body_size: float = 10,
) -> float:
    display = _workers_for_table(workers)
    show_notes = any(str(w.get("note") or "").strip() for w in display)
    show_photos = any(w.get("reward_photo_path") for w in display)
    thumb = 10 * mm if show_photos else 0

    c.setFont(font, title_size)
    c.drawString(MARGIN, y, title)
    y -= 8 * mm

    if show_notes:
        col_x = [MARGIN, MARGIN + 12 * mm, MARGIN + 52 * mm, MARGIN + 82 * mm, MARGIN + 112 * mm]
        headers = ["No", "성명", "기능(2-1)", "안전(2-2)", "비고"]
    else:
        col_x = [MARGIN, MARGIN + 14 * mm, MARGIN + 70 * mm, MARGIN + 126 * mm]
        headers = ["No", "성명", "기능(2-1)", "안전(2-2)"]

    c.setFont(font, body_size)
    for i, h in enumerate(headers):
        c.drawString(col_x[i], y, h)
    y -= 5 * mm
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 4 * mm
    c.setFont(font, body_size)
    for idx, w in enumerate(display, start=1):
        if y < 25 * mm:
            c.showPage()
            c.setFont(font, body_size)
            y = PAGE_H - 25 * mm
        c.drawString(col_x[0], y, str(idx))
        c.drawString(col_x[1], y, str(w.get("name") or "—")[:10])
        c.drawString(col_x[2], y, _grade_cell(w.get("functional_assessment")))
        c.drawString(col_x[3], y, _grade_cell(w.get("safety_assessment")))
        if show_notes:
            note = str(w.get("note") or "")[:12]
            if show_photos:
                note = note[:10]
            c.drawString(col_x[4], y, note)
        if show_photos and w.get("reward_photo_path"):
            _draw_file_image(c, w["reward_photo_path"], PAGE_W - MARGIN - thumb, y - 1 * mm, thumb, thumb)
        row_h = 5 * mm
        if show_photos and w.get("reward_photo_path"):
            row_h = max(row_h, thumb + 2 * mm)
        y -= row_h
    return y - 6 * mm


def _draw_signature_image(c: canvas.Canvas, signature_data: str, x: float, y: float, w: float, h: float) -> None:
    from PIL import Image
    from reportlab.lib.utils import ImageReader

    from app.modules.functional_eval.signature_service import _decode_png_bytes

    png_bytes = _decode_png_bytes(signature_data)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    c.drawImage(ImageReader(img), x, y, width=w, height=h, preserveAspectRatio=True, anchor="sw", mask="auto")


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


def _format_korean_date(dt: datetime) -> str:
    return format_kst_datetime_label(dt)


def _wrap_lines_to_width(c: canvas.Canvas, text: str, font: str, size: float, max_width: float) -> list[str]:
    """공백을 유지하면서 줄바꿈 (단어 우선, 불가 시 글자 단위)."""
    text = (text or "").replace("\r", "").strip()
    if not text:
        return []
    if c.stringWidth(text, font, size) <= max_width:
        return [text]

    lines: list[str] = []
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        parts = re.split(r"(\s+)", para)
        current = ""
        for part in parts:
            if not part:
                continue
            trial = current + part
            if not current or c.stringWidth(trial, font, size) <= max_width:
                current = trial
                continue
            if current.strip():
                lines.append(current)
            if part.isspace():
                current = ""
                continue
            if c.stringWidth(part, font, size) > max_width:
                chunk = ""
                for ch in part:
                    trial_ch = chunk + ch
                    if not chunk or c.stringWidth(trial_ch, font, size) <= max_width:
                        chunk = trial_ch
                    else:
                        lines.append(chunk)
                        chunk = ch
                current = chunk
            else:
                current = part
        if current.strip():
            lines.append(current)
    return lines


def _wrap_paragraph_natural(
    c: canvas.Canvas,
    paragraph: str,
    font: str,
    size: float,
    max_width: float,
) -> list[str]:
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    return _wrap_lines_to_width(c, paragraph, font, size, max_width)


def _consent_body_paragraphs(consent_body: str) -> list[str]:
    text = (consent_body or "").strip()
    if not text:
        return []
    if "\n\n" in text:
        return [p.strip() for p in text.split("\n\n") if p.strip()]
    merged = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return [merged] if merged else []


def _layout_paragraph_lines(
    c: canvas.Canvas,
    paragraph: str,
    font: str,
    body_size: float,
    max_body_w: float,
) -> list[str]:
    """문단 내 수동 줄바꿈(\\n)을 우선 반영."""
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    if "\n" not in paragraph:
        return _wrap_paragraph_natural(c, paragraph, font, body_size, max_body_w)
    lines: list[str] = []
    for segment in paragraph.split("\n"):
        segment = segment.strip()
        if not segment:
            continue
        if c.stringWidth(segment, font, body_size) <= max_body_w:
            lines.append(segment)
        else:
            lines.extend(_wrap_paragraph_natural(c, segment, font, body_size, max_body_w))
    return lines


def _layout_consent_body_lines(
    c: canvas.Canvas,
    consent_body: str,
    font: str,
    body_size: float,
    max_body_w: float,
    body_line_h: float,
) -> tuple[list[str], float]:
    """Returns (line markers with '' for paragraph gaps, total block height)."""
    c.setFont(font, body_size)
    laid_out: list[str] = []
    para_gap = body_line_h * 0.55
    total_h = 0.0
    paragraphs = _consent_body_paragraphs(consent_body)
    for idx, para in enumerate(paragraphs):
        if idx > 0:
            laid_out.append("")
            total_h += para_gap
        para_lines = _layout_paragraph_lines(c, para, font, body_size, max_body_w)
        laid_out.extend(para_lines)
        total_h += len(para_lines) * body_line_h
    return laid_out, total_h


def _draw_centered_lines(
    c: canvas.Canvas,
    *,
    lines: list[str],
    y: float,
    font: str,
    size: float,
    line_height: float,
    paragraph_gap: float | None = None,
    max_width: float | None = None,
) -> float:
    gap = paragraph_gap if paragraph_gap is not None else line_height * 0.55
    limit = max_width or (PAGE_W - 2 * MARGIN)
    c.setFont(font, size)
    for line in lines:
        if not line:
            y -= gap
            continue
        draw_lines = [line]
        if c.stringWidth(line, font, size) > limit:
            draw_lines = _wrap_lines_to_width(c, line, font, size, limit)
        for part in draw_lines:
            tw = c.stringWidth(part, font, size)
            c.drawString((PAGE_W - tw) / 2, y, part)
            y -= line_height
    return y


def _fit_font_size(
    c: canvas.Canvas,
    text: str,
    font: str,
    *,
    max_width: float,
    start_size: float,
    min_size: float = 9,
) -> float:
    size = start_size
    while size >= min_size:
        if c.stringWidth(text, font, size) <= max_width:
            return size
        size -= 0.5
    return min_size


def _draw_document_header_block(
    c: canvas.Canvas,
    *,
    font: str,
    title: str,
    site_full_name: str | None = None,
    role_line: str | None = None,
    title_size: float = 40,
    site_name_max_size: float = 20,
    role_line_size: float = 18,
    max_width: float | None = None,
) -> float:
    """제목 + 현장 풀네임(한 줄) + 현장-역할 줄. Returns y below header block."""
    limit = max_width or (PAGE_W - 24 * mm)
    title_y = PAGE_H - 28 * mm
    c.setFont(font, title_size)
    tw = c.stringWidth(title, font, title_size)
    c.drawString((PAGE_W - tw) / 2, title_y, title)

    y = title_y - 14 * mm
    if site_full_name:
        fitted = _fit_font_size(
            c, site_full_name, font, max_width=limit, start_size=site_name_max_size, min_size=10
        )
        c.setFont(font, fitted)
        sw = c.stringWidth(site_full_name, font, fitted)
        c.drawString((PAGE_W - sw) / 2, y, site_full_name)
        y -= max(8 * mm, fitted * 0.45)

    if role_line:
        c.setFont(font, role_line_size)
        rw = c.stringWidth(role_line, font, role_line_size)
        c.drawString((PAGE_W - rw) / 2, y, role_line)
        y -= 10 * mm

    return y - 12 * mm


def _draw_title_with_subtitle(
    c: canvas.Canvas,
    *,
    font: str,
    title: str,
    subtitle: str | None = None,
    site_full_name: str | None = None,
    role_line: str | None = None,
    title_size: float = 16,
    subtitle_size: float = 12,
) -> float:
    """보고서 제목·현장 헤더."""
    if site_full_name or role_line:
        return _draw_document_header_block(
            c,
            font=font,
            title=title,
            site_full_name=site_full_name,
            role_line=role_line or subtitle,
            title_size=title_size,
            site_name_max_size=min(title_size + 2, 20),
            role_line_size=subtitle_size,
        )
    title_y = PAGE_H - 28 * mm
    c.setFont(font, title_size)
    tw = c.stringWidth(title, font, title_size)
    c.drawString((PAGE_W - tw) / 2, title_y, title)
    if subtitle:
        c.setFont(font, subtitle_size)
        stw = c.stringWidth(subtitle, font, subtitle_size)
        subtitle_y = title_y - 10 * mm
        c.drawString((PAGE_W - stw) / 2, subtitle_y, subtitle)
        return subtitle_y - 10 * mm
    return title_y - 12 * mm


def generate_consent_pdf(
    *,
    signer_name: str,
    signer_login_id: str,
    consent_body: str,
    signature_data: str,
    signed_at: datetime,
    site_full_name: str | None = None,
    role_line: str | None = None,
    team_label: str | None = None,
    document_title: str | None = None,
) -> bytes:
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    title = (document_title or "").strip() or "기능인인정제 평가 수행 및 전자서명 동의서"
    body_size = 18
    body_line_h = 9 * mm
    date_size = 18
    sign_label_size = 17

    title_block_bottom = _draw_document_header_block(
        c,
        font=font,
        title=title,
        site_full_name=site_full_name,
        role_line=role_line or team_label,
        title_size=40,
        site_name_max_size=20,
        role_line_size=18,
        max_width=PAGE_W - 24 * mm,
    )

    bottom_padding = 16 * mm
    sig_w, sig_h = 36 * mm, 12 * mm
    sign_text_y = bottom_padding + 3 * mm
    date_y = sign_text_y + 16 * mm
    sign_block_top = date_y + 10 * mm

    max_body_w = PAGE_W - 30 * mm
    body_lines, body_block_h = _layout_consent_body_lines(
        c, consent_body, font, body_size, max_body_w, body_line_h
    )

    if body_lines:
        middle_center = (title_block_bottom + sign_block_top) / 2
        first_line_y = middle_center + body_block_h / 2 - body_line_h * 0.25
        _draw_centered_lines(
            c,
            lines=body_lines,
            y=first_line_y,
            font=font,
            size=body_size,
            line_height=body_line_h,
            paragraph_gap=body_line_h * 0.55,
            max_width=max_body_w,
        )

    date_text = _format_korean_date(signed_at)
    c.setFont(font, date_size)
    dtw = c.stringWidth(date_text, font, date_size)
    c.drawString((PAGE_W - dtw) / 2, date_y, date_text)

    c.setFont(font, sign_label_size)
    login_id = (signer_login_id or "").strip()
    name = (signer_name or "").strip() or login_id
    prefix = f"{login_id} / {name} / 서명 : "
    prefix_w = c.stringWidth(prefix, font, sign_label_size)
    block_w = prefix_w + sig_w + 2 * mm
    block_x = (PAGE_W - block_w) / 2
    c.drawString(block_x, sign_text_y, prefix)
    _draw_signature_image(c, signature_data, block_x + prefix_w + 1 * mm, sign_text_y - 2 * mm, sig_w, sig_h)

    c.save()
    return buf.getvalue()


def _draw_meta_lines(
    c: canvas.Canvas,
    *,
    font: str,
    lines: list[str],
    y: float,
    size: float = 12,
    line_height: float | None = None,
    centered: bool = False,
) -> float:
    lh = line_height or 6.5 * mm
    c.setFont(font, size)
    for line in lines:
        if centered:
            tw = c.stringWidth(line, font, size)
            c.drawString((PAGE_W - tw) / 2, y, line)
        else:
            c.drawString(MARGIN, y, line)
        y -= lh
    return y


def _draw_grade_review_block(
    c: canvas.Canvas,
    *,
    font: str,
    y: float,
    metadata: dict[str, Any],
    size: float = 11,
) -> float:
    snap = metadata.get("grade_distribution_snapshot") or {}
    grades = snap.get("grades") or {}
    lines = ["■ 등급 분포 검토 (기능/품질 2-1)"]
    lines.append("기능/품질: 기본 B · S 20% 권장 | 안전 2-2: 감점형(지적 이력 기반, S/C 비율 제한 없음)")
    total = snap.get("evaluated_total") or 0
    lines.append(f"총 평가대상: {snap.get('workers_total', total)}명 · 평가완료 {total}명")
    for code in ("S", "A", "B", "C"):
        bucket = grades.get(code) or {}
        lines.append(f"{code}등급: {bucket.get('count', 0)}명, {bucket.get('pct', 0)}%")
    if metadata.get("s_over_limit_reason"):
        lines.append(f"기능/품질 S등급 권장 기준 초과 사유: {metadata['s_over_limit_reason']}")
    return _draw_meta_lines(c, font=font, lines=lines, y=y, size=size)


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
    report_subtitle: str | None = None,
    site_full_name: str | None = None,
    role_line: str | None = None,
    grade_review_metadata: dict[str, Any] | None = None,
) -> bytes:
    """팀장 평가완료보고서 — 팀원 등급표 + 결재(팀장 작성 · 소장 최종)."""
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    meta_size = 12
    table_title_size = 12
    table_body_size = 10

    y = _draw_document_header_block(
        c,
        font=font,
        title=REPORT_TITLE,
        site_full_name=site_full_name,
        role_line=role_line or report_subtitle,
        title_size=28,
        site_name_max_size=18,
        role_line_size=16,
        max_width=PAGE_W - 24 * mm,
    )
    y -= 2 * mm
    signed_label = _format_korean_date(signed_at)
    display_workers = _workers_for_table(workers)
    y = _draw_meta_lines(
        c,
        font=font,
        lines=[
            f"평가기간: {period_title}",
            f"현장: {site_name}",
            f"작성: 팀장 {team_leader_name} ({team_leader_login})",
            f"팀원 {len(display_workers)}명 · 서명일시: {signed_label}",
        ],
        y=y,
        size=meta_size,
    )

    y = _draw_worker_table(
        c,
        font=font,
        y=y - 4 * mm,
        title="■ 팀원 평가 등급",
        workers=workers,
        title_size=table_title_size,
        body_size=table_body_size,
    )

    grade_review = (grade_review_metadata or {}) if grade_review_metadata else {}
    if grade_review.get("grade_distribution_snapshot"):
        y = _draw_grade_review_block(
            c,
            font=font,
            y=y - 2 * mm,
            metadata=grade_review,
            size=meta_size,
        )

    manager_name = (manager_approval or {}).get("signer_name", "")
    manager_signed = bool(manager_approval and manager_approval.get("signature_data"))
    boxes = [
        {"role": "팀장", "name": team_leader_name, "signed": True},
        {"role": "소장(최종)", "name": manager_name, "signed": manager_signed},
    ]
    overlays = [{"role": "팀장", "signature_data": signature_data}]
    if manager_signed:
        overlays.append({"role": "소장(최종)", "signature_data": manager_approval["signature_data"]})
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
    report_subtitle: str | None = None,
    site_full_name: str | None = None,
    role_line: str | None = None,
) -> bytes:
    """소장 평가완료보고서 — 갑지(서명) + 팀장별·직영 등급표."""
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    meta_size = 12
    table_title_size = 12
    table_body_size = 10

    # --- 갑지 ---
    y = _draw_document_header_block(
        c,
        font=font,
        title=REPORT_TITLE_COVER,
        site_full_name=site_full_name,
        role_line=role_line or report_subtitle,
        title_size=28,
        site_name_max_size=18,
        role_line_size=16,
        max_width=PAGE_W - 24 * mm,
    )
    y -= 2 * mm
    total_workers = sum(len(_workers_for_table(s.get("workers") or [])) for s in team_sections) + len(
        _workers_for_table(direct_workers)
    )
    y = _draw_meta_lines(
        c,
        font=font,
        lines=[
            f"평가기간: {period_title}",
            f"현장: {site_name} ({site_code})",
            f"소장: {manager_name} ({manager_login})",
            f"평가 대상: 총 {total_workers}명 (팀 {len(team_sections)}개 · 직영 {len(_workers_for_table(direct_workers))}명)",
            f"제출일시: {_format_korean_date(signed_at)}",
        ],
        y=y,
        size=meta_size,
    )

    c.setFont(font, meta_size)
    c.drawString(MARGIN, y - 2 * mm, "■ 첨부 목차")
    y -= 8 * mm
    for i, sec in enumerate(team_sections, start=1):
        cnt = len(_workers_for_table(sec.get("workers") or []))
        c.drawString(MARGIN + 4 * mm, y, f"{i}. {sec.get('leader_label', '팀')} 팀원 평가표 ({cnt}명)")
        y -= 5 * mm
    direct_cnt = len(_workers_for_table(direct_workers))
    if direct_cnt:
        c.drawString(MARGIN + 4 * mm, y, f"{len(team_sections) + 1}. 소장 직영 평가표 ({direct_cnt}명)")
        y -= 5 * mm

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
        c.setFont(font, 16)
        sec_title = f"{REPORT_TITLE_DETAIL} — {sec.get('leader_label', '팀')}"
        tw = c.stringWidth(sec_title, font, 16)
        c.drawString((PAGE_W - tw) / 2, PAGE_H - 25 * mm, sec_title)
        y = PAGE_H - 35 * mm
        y = _draw_worker_table(
            c,
            font=font,
            y=y,
            title="■ 팀원 평가 등급",
            workers=sec.get("workers") or [],
            title_size=table_title_size,
            body_size=table_body_size,
        )
        if sec.get("team_leader_signed_at"):
            c.setFont(font, 9)
            c.drawString(MARGIN, y, f"팀장 서명: {sec.get('team_leader_signed_at', '')}")
        if sec.get("manager_approved_at"):
            c.drawString(MARGIN, y - 4 * mm, f"소장 승인: {sec.get('manager_approved_at', '')}")

    if direct_workers:
        c.showPage()
        c.setFont(font, 16)
        direct_title = f"{REPORT_TITLE_DETAIL} — 소장 직영"
        tw = c.stringWidth(direct_title, font, 16)
        c.drawString((PAGE_W - tw) / 2, PAGE_H - 25 * mm, direct_title)
        _draw_worker_table(
            c,
            font=font,
            y=PAGE_H - 35 * mm,
            title="■ 직영 평가 등급",
            workers=direct_workers,
            title_size=table_title_size,
            body_size=table_body_size,
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
    report_title: str = REPORT_TITLE,
) -> bytes:
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont(font, 16)
    title = report_title
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
    c.drawString(MARGIN, y, f"승인 현장 {len(site_summaries)}개소 · {signer_name} · {format_kst_datetime_short(signed_at)}")
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
    title = REPORT_TITLE
    tw = c.stringWidth(title, font, 16)
    c.drawString((PAGE_W - tw) / 2, PAGE_H - 28 * mm, title)
    c.setFont(font, 10)
    y = PAGE_H - 45 * mm
    for line in [
        f"평가기간: {period_title}",
        f"승인 현장: {site_count}개소",
        f"본사 검토 확인 후 최종 승인합니다.",
        f"승인자: {signer_name}",
        f"일시: {format_kst_datetime_short(signed_at)}",
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
