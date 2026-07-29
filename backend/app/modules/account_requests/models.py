from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import utc_now


class AccountAccessRequest(Base):
    __tablename__ = "account_access_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_no: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    request_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), index=True, nullable=False, default="REQUESTED")
    applicant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    existing_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_mobile: Mapped[str] = mapped_column(String(30), nullable=False)
    company_name: Mapped[str] = mapped_column(String(150), nullable=False)
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100))
    work_category: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), index=True)
    site_code: Mapped[str | None] = mapped_column(String(50))
    site_name: Mapped[str | None] = mapped_column(String(200))
    request_reason: Mapped[str] = mapped_column(Text, nullable=False)
    employment_evidence_note: Mapped[str | None] = mapped_column(Text)
    privacy_consent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    roster_match_status: Mapped[str] = mapped_column(String(30), nullable=False)
    duplicate_candidate_ids_json: Mapped[str | None] = mapped_column(Text)
    recommended_role: Mapped[str | None] = mapped_column(String(50))
    current_role_snapshot: Mapped[str | None] = mapped_column(String(50))
    current_site_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    approved_role: Mapped[str | None] = mapped_column(String(50))
    approved_site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime)
    handled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime)
    decision_comment: Mapped[str | None] = mapped_column(Text)
    created_account_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class AccountAccessRequestEvent(Base):
    __tablename__ = "account_access_request_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("account_access_requests.id"), index=True, nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    actor_role: Mapped[str | None] = mapped_column(String(50))
    detail_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

