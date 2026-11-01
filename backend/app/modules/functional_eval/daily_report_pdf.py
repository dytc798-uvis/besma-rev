"""기능인인정제 일일 진행현황 보고서 PDF."""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.modules.functional_eval.signature_report_pdf import MARGIN, PAGE_H, PAGE_W, ensure_korean_font

FOOTER = "본 보고서는 기능인인정제 시스템의 평가·서명·승인 데이터를 기준으로 자동 생성되었습니다."


def _draw_footer(c: canvas.Canvas, font: str, page_no: int) -> None:
    c.setFont(font, 8)
    c.drawString(MARGIN, 12 * mm, FOOTER)
    c.drawRightString(PAGE_W - MARGIN, 12 * mm, f"- {page_no} -")


def _new_page_if_needed(c: canvas.Canvas, font: str, y: float, *, page_no: int, min_y: float = 30 * mm) -> tuple[float, int]:
    if y >= min_y:
        return y, page_no
    _draw_footer(c, font, page_no)
    c.showPage()
    return PAGE_H - 25 * mm, page_no + 1


def _section(c: canvas.Canvas, font: str, y: float, title: str, *, size: float = 14) -> float:
    c.setFont(font, size)
    c.drawString(MARGIN, y, title)
    return y - 8 * mm


def _lines(c: canvas.Canvas, font: str, y: float, lines: list[str], *, size: float = 10, line_h: float = 5 * mm) -> float:
    c.setFont(font, size)
    for line in lines:
        c.drawString(MARGIN, y, line[:110])
        y -= line_h
    return y


def _table(
    c: canvas.Canvas,
    font: str,
    y: float,
    headers: list[str],
    rows: list[list[str]],
    col_x: list[float],
    *,
    page_no: int,
    body_size: float = 8,
) -> tuple[float, int]:
    c.setFont(font, body_size + 1)
    for i, h in enumerate(headers):
        c.drawString(col_x[i], y, h[:18])
    y -= 4 * mm
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 3 * mm
    c.setFont(font, body_size)
    for row in rows:
        y, page_no = _new_page_if_needed(c, font, y, page_no=page_no)
        for i, cell in enumerate(row):
            c.drawString(col_x[i], y, str(cell)[:22])
        y -= 4.5 * mm
    return y - 4 * mm, page_no


def generate_daily_report_pdf(snapshot: dict[str, Any]) -> bytes:
    font = ensure_korean_font()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_no = 1
    y = PAGE_H - 28 * mm

    title = str(snapshot.get("title") or "기능인인정제 일일 진행현황 보고서")
    c.setFont(font, 22)
    tw = c.stringWidth(title, font, 22)
    c.drawString((PAGE_W - tw) / 2, y, title)
    y -= 12 * mm
    c.setFont(font, 11)
    c.drawString(MARGIN, y, f"기준시각: {snapshot.get('criteria_at_kst', '')}")
    y -= 6 * mm
    period = snapshot.get("period") or {}
    c.drawString(MARGIN, y, f"평가기간: {period.get('title', '—')}")
    y -= 14 * mm

    summary = snapshot.get("summary") or {}
    y = _section(c, font, y, "1. 전체 요약")
    y = _lines(
        c,
        font,
        y,
        [
            f"전체 평가대상: {summary.get('total_workers', 0)}명",
            f"평가완료: {summary.get('completed_workers', 0)}명 · 미평가: {summary.get('incomplete_workers', 0)}명",
            f"평가완료율: {summary.get('completion_rate_pct', 0)}%",
            f"팀장 평가완료 서명: {summary.get('team_signoff_signature_count', 0)}건",
            f"소장 제출 완료 현장: {summary.get('site_submitted_count', 0)}개",
            f"본사 담당 승인 완료: {summary.get('hq_officer_approved_count', 0)}개",
            f"안전보건실장 승인 완료: {summary.get('hq_director_approved_count', 0)}개",
            f"대표이사 최종 승인 완료: {summary.get('ceo_approved_count', 0)}개",
        ],
    )

    y = _section(c, font, y - 4 * mm, "2. 현장별 진행현황")
    site_rows = snapshot.get("sites") or []
    headers = ["현장", "대상", "완료", "완료율", "팀장서명", "단계"]
    col_x = [MARGIN, MARGIN + 38 * mm, MARGIN + 58 * mm, MARGIN + 74 * mm, MARGIN + 94 * mm, MARGIN + 118 * mm]
    rows = [
        [
            f"{r.get('site_code', '')}",
            str(r.get("total_workers", 0)),
            str(r.get("completed_workers", 0)),
            f"{r.get('completion_rate_pct', 0)}%",
            f"{r.get('team_leader_signed', 0)}/{r.get('team_leader_required', 0)}",
            str(r.get("current_stage", ""))[:12],
        ]
        for r in site_rows[:40]
    ]
    y, page_no = _table(c, font, y, headers, rows, col_x, page_no=page_no)

    y = _section(c, font, y, "3. 평가자별 진행현황")
    eval_rows = snapshot.get("evaluators") or []
    headers = ["현장", "평가자", "역할", "배정", "완료", "완료율", "서명"]
    col_x = [MARGIN, MARGIN + 28 * mm, MARGIN + 68 * mm, MARGIN + 88 * mm, MARGIN + 104 * mm, MARGIN + 120 * mm, MARGIN + 140 * mm]
    rows = [
        [
            str(r.get("site_code", "")),
            str(r.get("name", ""))[:8],
            str(r.get("role", "")),
            str(r.get("assigned", 0)),
            str(r.get("completed", 0)),
            f"{r.get('completion_rate_pct', 0)}%",
            "완료" if r.get("signoff_complete") else "미완료",
        ]
        for r in eval_rows[:35]
    ]
    y, page_no = _table(c, font, y, headers, rows, col_x, page_no=page_no)

    y, page_no = _new_page_if_needed(c, font, y, page_no=page_no, min_y=80 * mm)
    y = _section(c, font, y, "4. 등급 분포")
    grade = snapshot.get("grade_distribution") or {}
    overall = grade.get("overall") or {}
    func = overall.get("functional") or {}
    safety = overall.get("safety") or {}
    y = _lines(
        c,
        font,
        y,
        [
            "【전체 · 기능/품질 2-1】 "
            + " ".join(f"{k}:{func.get('grades', {}).get(k, {}).get('count', 0)}" for k in ("S", "A", "B", "C")),
            f"S 비율 초과(20%): {'예' if overall.get('functional', {}).get('s_over_20pct') else '아니오'}",
            "【전체 · 안전 2-2】 "
            + " ".join(f"{k}:{safety.get('grades', {}).get(k, {}).get('count', 0)}" for k in ("S", "A", "B", "C")),
            str(safety.get("note") or "안전(2-2)은 S 20% 제한 없음"),
        ],
    )

    y = _section(c, font, y - 2 * mm, "5. 포상/제재 현황 (당일 등록)")
    rs = snapshot.get("reward_sanction") or {}
    y = _lines(
        c,
        font,
        y,
        [
            f"포상 등록: {rs.get('reward_count', 0)}건 · 제재 등록: {rs.get('sanction_count', 0)}건",
            f"감점 반영 제재: {rs.get('penalty_applied_count', 0)}건 · 반복 제재 대상: {rs.get('repeat_sanction_worker_count', 0)}명",
        ],
    )

    y = _section(c, font, y - 2 * mm, "6. 병목 현황")
    bottlenecks = snapshot.get("bottlenecks") or {}
    labels = {
        "low_completion_sites": "완료율 50% 미만",
        "high_incomplete_sites": "미평가 5명 이상",
        "team_signoff_pending_sites": "팀장 서명 미완료",
        "site_submit_pending_sites": "소장 제출 대기",
        "hq_officer_pending_sites": "본사 담당 승인 대기",
        "hq_director_pending_sites": "실장 승인 대기",
        "ceo_pending_sites": "대표 승인 대기",
        "functional_s_over_sites": "기능 S 20% 초과",
    }
    for key, label in labels.items():
        items = bottlenecks.get(key) or []
        if not items:
            continue
        codes = ", ".join(f"{i.get('site_code', '')}" for i in items[:12])
        y, page_no = _new_page_if_needed(c, font, y, page_no=page_no)
        y = _lines(c, font, y, [f"· {label}: {codes}"], size=9)

    y = _section(c, font, y - 2 * mm, "7. 추가평가 현황")
    sup = snapshot.get("supplemental_eval") or {}
    if not sup.get("has_supplemental_batch"):
        y = _lines(c, font, y, [str(sup.get("ui_followup_note") or "추가평가 배치 없음")])
    else:
        for s in (sup.get("sites") or [])[:15]:
            y, page_no = _new_page_if_needed(c, font, y, page_no=page_no)
            y = _lines(
                c,
                font,
                y,
                [
                    f"· {s.get('site_code')}: {s.get('batch_label')} 대상 {s.get('target_count')}명 / 완료 {s.get('completed_count')}명",
                ],
                size=9,
            )

    y = _section(c, font, y - 4 * mm, "8. 생성 정보")
    meta = snapshot.get("meta") or {}
    y = _lines(
        c,
        font,
        y,
        [
            f"생성: {meta.get('generated_at_label') or meta.get('generated_at') or '—'}",
            f"생성 주체: {meta.get('generated_by', 'system')} · 버전: {meta.get('version', 1)}",
        ],
        size=9,
    )

    _draw_footer(c, font, page_no)
    c.save()
    return buf.getvalue()
