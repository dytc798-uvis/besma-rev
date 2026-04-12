from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class DocumentStatus(str):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESUBMITTED = "RESUBMITTED"


class DocumentType(str):
    LEGAL_DOC = "LEGAL_DOC"
    DAILY_DOC = "DAILY_DOC"
    INSPECTION = "INSPECTION"
    OPINION_RELATED = "OPINION_RELATED"
    BUDGET = "BUDGET"
    ACCIDENT = "ACCIDENT"
    ETC = "ETC"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    submitter_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    current_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentStatus.DRAFT
    )
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    optimized_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    # 제출 주기/자동생성 확장 필드 (MVP에서는 계산 로직은 서비스로 분리)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="MANUAL")

    # DocumentInstance(문서 자리)와 1:1 연결 (MVP)
    instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_instances.id"), unique=True, nullable=True, index=True
    )

    site: Mapped["Site"] = relationship("Site")
    submitter: Mapped["User"] = relationship("User", foreign_keys=[submitter_user_id])
    uploaded_by: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by_user_id])
    instance: Mapped["DocumentInstance"] = relationship("DocumentInstance", foreign_keys=[instance_id])


class DocumentUploadHistory(Base):
    __tablename__ = "document_upload_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("document_instances.id"), nullable=True, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False, default="UPLOAD")
    document_status: Mapped[str] = mapped_column(String(20), nullable=False, default=DocumentStatus.DRAFT)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])
    uploaded_by: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by_user_id])


class DocumentComment(Base):
    __tablename__ = "document_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("document_instances.id"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_role: Mapped[str] = mapped_column(String(10), nullable=False)
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    document: Mapped["Document"] = relationship("Document", foreign_keys=[document_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

