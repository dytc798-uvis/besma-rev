from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import utc_now


class SafetyEducationMaterial(Base):
    __tablename__ = "safety_education_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class SafetyInspectionComment(Base):
    __tablename__ = "safety_inspection_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class NonconformityLedger(Base):
    __tablename__ = "nonconformity_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="IMPORT")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class NonconformityItem(Base):
    __tablename__ = "nonconformity_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("nonconformity_ledgers.id"), nullable=False, index=True)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    action_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    improvement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    improvement_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    improvement_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    after_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    site_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    site_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    site_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    site_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    site_reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    site_rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hq_checked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reward_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_candidate_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reward_candidate_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    receipt_decision: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    site_action_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_db_request_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    risk_db_hq_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    risk_db_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_db_requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    risk_db_hq_decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_db_hq_decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class WorkerVoiceLedger(Base):
    __tablename__ = "worker_voice_ledgers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="IMPORT")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class WorkerVoiceItem(Base):
    __tablename__ = "worker_voice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("worker_voice_ledgers.id"), nullable=False, index=True)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    worker_birth_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    worker_phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    opinion_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    opinion_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    action_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    before_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    after_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    site_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    site_reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    site_rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    site_rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    site_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    site_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    site_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hq_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hq_checked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reward_candidate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reward_candidate_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reward_candidate_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    receipt_decision: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    site_action_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_db_request_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    risk_db_hq_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    risk_db_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_db_requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    risk_db_hq_decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_db_hq_decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class WorkerVoiceComment(Base):
    __tablename__ = "worker_voice_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("worker_voice_items.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
