"""아이디 자가 발급 이력·시도 제한."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import utc_now


class AccountIssuanceLog(Base):
    __tablename__ = "account_issuance_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # site | hq
    site_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_department: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    recipient_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_account_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issued_accounts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
