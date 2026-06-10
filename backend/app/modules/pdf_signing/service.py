from __future__ import annotations

import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config.settings import settings
from sqlalchemy import inspect, text

from app.core.database import engine
from app.modules.pdf_signing.models import PdfSigningRequest

TEMP_SIGN_SLOTS = frozenset({"sign1", "sign2"})
TEMP_SIGN_SLOT_LABELS = {
    "sign1": "운영 (최재필 전무)",
    "sign2": "테스트",
}

# 사고보고서 1페이지 상단 결재란 — 공사팀 PM 칸 (A4, 이미지 PDF 기준 수동 보정)
ACCIDENT_REPORT_PM_SIGNATURE = {
    "page_index": 0,
    "x": 312.0,
    "y": 692.0,
    "width": 28.0,
    "height": 32.0,
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def storage_dir() -> Path:
    root = settings.storage_root / "pdf_signing"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_schema() -> None:
    inspector = inspect(engine)
    if "pdf_signing_requests" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("pdf_signing_requests")}
    if "slot" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE pdf_signing_requests ADD COLUMN slot VARCHAR(16)"))
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_pdf_signing_requests_slot "
                    "ON pdf_signing_requests (slot)"
                )
            )


def normalize_slot(slot: str | None) -> str | None:
    if slot is None:
        return None
    normalized = slot.strip().lower()
    if normalized not in TEMP_SIGN_SLOTS:
        raise ValueError("invalid_slot")
    return normalized


def build_sign_url(*, token: str, slot: str | None = None) -> str:
    if slot in TEMP_SIGN_SLOTS:
        return f"/temp/{slot}"
    return f"/sign/{token}"


def _decode_signature_png(signature_png_base64: str) -> bytes:
    raw = signature_png_base64.strip()
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("invalid_signature_image") from exc
    if len(data) < 32:
        raise ValueError("invalid_signature_image")
    return data


def overlay_signature_on_pdf(original_pdf: bytes, signature_png: bytes) -> bytes:
    from PIL import Image
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    reader = PdfReader(io.BytesIO(original_pdf))
    if not reader.pages:
        raise ValueError("empty_pdf")

    page_index = ACCIDENT_REPORT_PM_SIGNATURE["page_index"]
    if page_index >= len(reader.pages):
        raise ValueError("page_not_found")

    base_page = reader.pages[page_index]
    media = base_page.mediabox
    page_w = float(media.width)
    page_h = float(media.height)

    sig = ACCIDENT_REPORT_PM_SIGNATURE
    overlay_buf = io.BytesIO()
    overlay = canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))
    img = Image.open(io.BytesIO(signature_png)).convert("RGBA")
    overlay.drawImage(
        ImageReader(img),
        sig["x"],
        sig["y"],
        width=sig["width"],
        height=sig["height"],
        mask="auto",
        preserveAspectRatio=True,
        anchor="sw",
    )
    overlay.save()

    overlay_reader = PdfReader(io.BytesIO(overlay_buf.getvalue()))
    base_page.merge_page(overlay_reader.pages[0])

    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx == page_index:
            writer.add_page(base_page)
        else:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def create_request(
    db: Session,
    *,
    created_by_user_id: int,
    signer_name: str,
    signer_title: str,
    purpose_label: str | None,
    original_filename: str,
    original_bytes: bytes,
    expires_hours: int = 168,
    slot: str | None = None,
) -> PdfSigningRequest:
    normalized_slot = normalize_slot(slot)
    token = secrets.token_urlsafe(32)
    req_id_hint = secrets.token_hex(4)
    safe_name = Path(original_filename or "document.pdf").name
    original_path = storage_dir() / f"{req_id_hint}_{safe_name}"
    original_path.write_bytes(original_bytes)

    if normalized_slot:
        existing = get_by_slot(db, normalized_slot)
        if existing is not None:
            existing.slot = None
            db.flush()

    row = PdfSigningRequest(
        slot=normalized_slot,
        token=token,
        purpose_label=(purpose_label or "").strip() or None,
        signer_name=signer_name.strip(),
        signer_title=signer_title.strip(),
        original_filename=safe_name,
        original_path=str(original_path),
        original_sha256=sha256_bytes(original_bytes),
        status="pending",
        expires_at=_utcnow() + timedelta(hours=max(1, expires_hours)),
        created_by_user_id=created_by_user_id,
        created_at=_utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_requests(db: Session) -> list[PdfSigningRequest]:
    return (
        db.query(PdfSigningRequest)
        .order_by(PdfSigningRequest.id.desc())
        .all()
    )


def get_request(db: Session, request_id: int) -> PdfSigningRequest | None:
    return db.query(PdfSigningRequest).filter(PdfSigningRequest.id == request_id).first()


def get_by_token(db: Session, token: str) -> PdfSigningRequest | None:
    return db.query(PdfSigningRequest).filter(PdfSigningRequest.token == token).first()


def get_by_slot(db: Session, slot: str) -> PdfSigningRequest | None:
    normalized = normalize_slot(slot)
    return db.query(PdfSigningRequest).filter(PdfSigningRequest.slot == normalized).first()


def list_slot_requests(db: Session) -> dict[str, PdfSigningRequest | None]:
    rows = db.query(PdfSigningRequest).filter(PdfSigningRequest.slot.in_(TEMP_SIGN_SLOTS)).all()
    by_slot = {row.slot: row for row in rows if row.slot}
    return {slot: by_slot.get(slot) for slot in sorted(TEMP_SIGN_SLOTS)}


def _ensure_active_token(row: PdfSigningRequest) -> None:
    if row.status == "signed":
        raise ValueError("token_already_used")
    if row.expires_at < _utcnow():
        row.status = "expired"
        raise ValueError("token_expired")


def _resolve_request(db: Session, *, token: str | None = None, slot: str | None = None) -> PdfSigningRequest:
    if slot:
        row = get_by_slot(db, slot)
    elif token:
        row = get_by_token(db, token)
    else:
        raise ValueError("token_not_found")
    if row is None:
        raise ValueError("token_not_found")
    return row


def submit_signature(
    db: Session,
    *,
    token: str | None = None,
    slot: str | None = None,
    signature_png_base64: str,
    signer_ip: str | None,
    signer_user_agent: str | None,
) -> PdfSigningRequest:
    row = _resolve_request(db, token=token, slot=slot)

    try:
        _ensure_active_token(row)
    except ValueError:
        db.commit()
        raise

    signature_png = _decode_signature_png(signature_png_base64)
    original_bytes = Path(row.original_path).read_bytes()
    signed_bytes = overlay_signature_on_pdf(original_bytes, signature_png)

    signed_name = f"signed_{row.id}_{row.original_filename}"
    signed_path = storage_dir() / signed_name
    signed_path.write_bytes(signed_bytes)

    row.signed_path = str(signed_path)
    row.signed_sha256 = sha256_bytes(signed_bytes)
    row.status = "signed"
    row.signed_at = _utcnow()
    row.signer_ip = signer_ip
    row.signer_user_agent = (signer_user_agent or "")[:2000] or None
    db.commit()
    db.refresh(row)
    return row
