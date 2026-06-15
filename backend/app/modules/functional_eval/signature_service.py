"""기능인제 서명 검증·PDF 문서 생성·저장."""

from __future__ import annotations

import base64
import hashlib
import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import format_kst_datetime_label, format_kst_datetime_short, utc_now

PNG_DATA_PREFIX = "data:image/png;base64,"
SIGNATURE_MIN_BYTES = 20
SIGNATURE_MAX_BYTES = 512_000
CONSENT_VERSION = "2026-06-17-evaluator-v2"
VIEWER_CONSENT_VERSION = "2026-06-17-viewer-v1"

CONSENT_KIND_EVALUATOR = "evaluator"
CONSENT_KIND_VIEWER = "viewer"

STAGE_CONSENT = "CONSENT"
STAGE_TEAM_LEADER = "TEAM_LEADER"
STAGE_TEAM_MANAGER_APPROVE = "TEAM_MANAGER_APPROVE"
STAGE_SITE = "SITE"
STAGE_HQ_OFFICER = "HQ_OFFICER"
STAGE_HQ = "HQ"
STAGE_CEO = "CEO"

STAGE_ROLE_LABELS = {
    STAGE_TEAM_LEADER: "팀장 평가완료보고서",
    STAGE_TEAM_MANAGER_APPROVE: "소장 팀장보고서 승인",
    STAGE_SITE: "소장 평가완료보고서",
    STAGE_HQ_OFFICER: "안전보건 담당 검토·승인",
    STAGE_HQ: "안전보건실장 승인",
    STAGE_CEO: "대표이사 최종승인",
}

EVALUATOR_CONSENT_TITLE = "기능인인정제 평가 수행 및 전자서명 동의서"

CONSENT_BODY = """
본인은 BESMA 기능인인정제 평가 업무를 수행함에 있어 아래 사항을 확인하고 동의합니다.

1. 본인은 부현전기 모든 근로자가 안전하게 일할 수 있는 작업환경 조성에 협조하고, 기능인인정제 평가가 안전문화 정착과 현장관리 수준 향상을 위한 제도임을 확인합니다.

2. 본인은 기능인인정제 평가 업무를 수행함에 있어 회사의 관련 규정, 평가 기준, 평가 항목, 결재 절차를 확인하였으며, 해당 기준에 따라 성실하고 공정하게 평가합니다.

3. 본인은 평가 내용을 입력, 제출, 검토 또는 승인할 때 실제 작업내용, 안전수칙 준수 여부, 교육·점검·지적사항, 현장 확인사항 등 사실에 근거하여 작성합니다.

4. 본인은 허위 사실, 확인되지 않은 내용, 개인적 감정, 친분, 불이익 목적, 보복성 사유 또는 차별적 사유에 따라 평가하지 않습니다.

5. 본인은 본인이 입력, 제출, 검토 또는 승인한 평가 내용의 사실성, 정확성 및 적정성에 대한 책임이 있음을 확인합니다.

6. 본인은 평가 대상자의 평가결과, 등급, 점수, 현장 정보, 근로자 정보, 결재 이력 등 BESMA에서 확인한 정보를 업무 목적 범위 내에서만 사용합니다.

7. 본인은 BESMA에서 확인한 평가정보를 정당한 권한 없이 복사, 촬영, 캡처, 출력, 다운로드, 전송, 게시 또는 배포하지 않습니다.

8. 본인은 부여받은 아이디와 비밀번호를 타인에게 공유하지 않으며, 다른 사람의 계정으로 평가, 제출, 승인 또는 서명하지 않습니다.

9. 본인은 BESMA 접속, 평가 입력, 수정, 제출, 승인, 반려, 조회 및 전자서명 이력이 시스템에 기록될 수 있음을 확인합니다.

10. 본인은 BESMA에서 입력하는 전자서명이 본인의 의사표시이며, 해당 평가 또는 결재 행위에 대한 확인으로 사용된다는 점을 이해하고 동의합니다.

11. 본인은 위 사항을 위반할 경우 평가의 정정, 재검토, 권한 제한, 회사 규정에 따른 조치 또는 관련 법령상 책임이 발생할 수 있음을 확인합니다.

본인은 위 내용을 확인하였으며 이에 동의합니다.
""".strip()

VIEWER_CONSENT_TITLE = "기능인인정제 평가정보 조회 및 비밀유지 동의서"

VIEWER_CONSENT_BODY = """
본인은 BESMA 기능인인정제 평가정보 조회 권한을 부여받음에 있어 아래 사항을 확인하고 동의합니다.

1. 본인은 기능인인정제 평가정보를 회사 업무 목적 범위 내에서만 조회합니다.
2. 본인은 평가결과, 평가점수, 등급, 근로자 정보, 현장 정보, 결재 이력 등 BESMA에서 조회한 정보를 무단으로 복사, 촬영, 캡처, 출력, 다운로드, 전송 또는 배포하지 않습니다.
3. 본인은 조회한 정보를 사내 업무 목적 외로 사용하거나 제3자에게 제공하지 않습니다.
4. 본인은 부여받은 아이디와 비밀번호를 타인에게 공유하지 않으며, 본인 계정으로 발생한 행위에 대한 관리 책임이 있음을 확인합니다.
5. 본인은 BESMA 접속, 조회, 다운로드, 서명 등 이용 이력이 시스템에 기록될 수 있음을 확인합니다.
6. 본인은 위 사항을 위반할 경우 회사 규정 및 관련 법령에 따른 책임이 발생할 수 있음을 확인합니다.

본인은 위 내용을 확인하였으며 이에 동의합니다.
""".strip()


def storage_dir() -> Path:
    root = settings.storage_root / "functional_eval" / "signatures"
    root.mkdir(parents=True, exist_ok=True)
    return root


def normalize_signature_data(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ValueError("signature_required")
    if text.startswith(PNG_DATA_PREFIX):
        return text
    if "," in text:
        text = text.split(",", 1)[1]
    try:
        base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValueError("invalid_signature_base64") from exc
    return f"{PNG_DATA_PREFIX}{text}"


def validate_signature_data(signature_data: str) -> tuple[str, bytes]:
    normalized = normalize_signature_data(signature_data)
    encoded = normalized[len(PNG_DATA_PREFIX) :]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("invalid_signature_base64") from exc
    size = len(raw)
    if size < SIGNATURE_MIN_BYTES:
        raise ValueError("signature_too_small")
    if size > SIGNATURE_MAX_BYTES:
        raise ValueError("signature_too_large")
    return hashlib.sha256(raw).hexdigest(), raw


def batch_label(batch_number: int) -> str:
    if batch_number <= 0:
        return "최초평가"
    return f"추가평가 {batch_number}차"


def _decode_png_bytes(signature_data: str) -> bytes:
    _, raw = validate_signature_data(signature_data)
    return raw


def _safe_filename_part(text: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]+', "_", (text or "").strip())[:60] or "doc"


def generate_signature_pdf(
    *,
    title: str,
    period_title: str,
    site_name: str | None,
    stage_label: str,
    signer_name: str,
    signer_login_id: str,
    scope_label: str,
    signature_data: str,
    signed_at: datetime,
    approval_rows: list[dict[str, Any]] | None = None,
) -> bytes:
    from PIL import Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    page_w, page_h = A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    title_w = c.stringWidth(title, "Helvetica-Bold", 16)
    c.drawString((page_w - title_w) / 2, page_h - 30 * mm, title)

    c.setFont("Helvetica", 10)
    y = page_h - 45 * mm
    for line in [
        f"평가기간: {period_title}",
        f"현장: {site_name or '—'}",
        f"단계: {stage_label}",
        f"서명자: {signer_name} ({signer_login_id})",
        f"평가대상: {scope_label}",
        f"서명일시: {format_kst_datetime_short(signed_at)}",
    ]:
        c.drawString(25 * mm, y, line)
        y -= 6 * mm

    from reportlab.lib.utils import ImageReader

    png_bytes = _decode_png_bytes(signature_data)
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    sig_w = 70 * mm
    sig_h = 25 * mm
    sig_x = (page_w - sig_w) / 2
    sig_y = page_h - 95 * mm
    c.drawImage(
        ImageReader(img),
        sig_x,
        sig_y,
        width=sig_w,
        height=sig_h,
        preserveAspectRatio=True,
        anchor="sw",
        mask="auto",
    )

    box_y = 35 * mm
    box_h = 28 * mm
    cols = approval_rows or [
        {"role": "팀장", "name": "", "signed": False},
        {"role": "소장", "name": "", "signed": False},
        {"role": "안전보건실장", "name": "", "signed": False},
        {"role": "대표이사", "name": "", "signed": False},
    ]
    col_w = (page_w - 30 * mm) / max(len(cols), 1)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15 * mm, box_y + box_h + 4 * mm, "결재")
    for idx, col in enumerate(cols):
        x = 15 * mm + idx * col_w
        c.rect(x, box_y, col_w - 2 * mm, box_h)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + 2 * mm, box_y + box_h - 5 * mm, col.get("role") or "")
        c.setFont("Helvetica", 7)
        name = (col.get("name") or "").strip()
        if name:
            c.drawString(x + 2 * mm, box_y + 4 * mm, name[:18])
        if col.get("signed"):
            c.setFont("Helvetica", 6)
            c.drawString(x + 2 * mm, box_y + 10 * mm, "서명완료")

    c.save()
    return buf.getvalue()


def save_pdf_document(*, prefix: str, pdf_bytes: bytes) -> str:
    name = f"{prefix}_{utc_now().strftime('%Y%m%d_%H%M%S')}_{hashlib.sha256(pdf_bytes).hexdigest()[:8]}.pdf"
    path = storage_dir() / name
    path.write_bytes(pdf_bytes)
    return str(path)


def build_approval_rows_for_site(db: Session, period_id: int, site_code: str, batch: int) -> list[dict[str, Any]]:
    from app.modules.functional_eval.models import FunctionalEvalSignature

    rows = (
        db.query(FunctionalEvalSignature)
        .filter(
            FunctionalEvalSignature.period_id == period_id,
            FunctionalEvalSignature.evaluation_batch == batch,
            FunctionalEvalSignature.site_code == site_code,
            FunctionalEvalSignature.stage.in_(
                [STAGE_TEAM_LEADER, STAGE_SITE, STAGE_HQ_OFFICER, STAGE_HQ, STAGE_CEO]
            ),
        )
        .all()
    )
    by_stage: dict[str, FunctionalEvalSignature] = {}
    for row in rows:
        if row.stage == STAGE_TEAM_LEADER:
            continue
        by_stage[row.stage] = row
    team_signed = any(r.stage == STAGE_TEAM_LEADER for r in rows)
    return [
        {"role": "팀장", "name": "서명완료" if team_signed else "", "signed": team_signed},
        {
            "role": "소장",
            "name": (by_stage.get(STAGE_SITE).signer_name if STAGE_SITE in by_stage else ""),
            "signed": STAGE_SITE in by_stage,
        },
        {
            "role": "안전보건 담당",
            "name": (by_stage.get(STAGE_HQ_OFFICER).signer_name if STAGE_HQ_OFFICER in by_stage else ""),
            "signed": STAGE_HQ_OFFICER in by_stage,
        },
        {
            "role": "안전보건실장",
            "name": (by_stage.get(STAGE_HQ).signer_name if STAGE_HQ in by_stage else ""),
            "signed": STAGE_HQ in by_stage,
        },
        {
            "role": "대표이사",
            "name": (by_stage.get(STAGE_CEO).signer_name if STAGE_CEO in by_stage else ""),
            "signed": STAGE_CEO in by_stage,
        },
    ]


def serialize_signature(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "period_id": row.period_id,
        "evaluation_batch": row.evaluation_batch,
        "evaluation_batch_label": batch_label(row.evaluation_batch),
        "stage": row.stage,
        "stage_label": STAGE_ROLE_LABELS.get(row.stage, row.stage),
        "site_code": row.site_code,
        "team_leader_login_id": row.team_leader_login_id,
        "signer_login_id": row.signer_login_id,
        "signer_name": row.signer_name,
        "scope_label": row.scope_label,
        "signed_at": row.signed_at.isoformat() if row.signed_at else None,
        "signed_at_label": format_kst_datetime_label(row.signed_at),
        "has_document": bool(row.signed_document_path),
    }
