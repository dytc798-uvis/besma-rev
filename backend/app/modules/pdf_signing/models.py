from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PdfSigningRequest(Base):
    """1회용 외부 PDF 서명 요청."""

    __tablename__ = "pdf_signing_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot: Mapped[str | None] = mapped_column(String(16), unique=True, index=True, nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    purpose_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    signer_title: Mapped[str] = mapped_column(String(80), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    signed_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signer_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signer_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
