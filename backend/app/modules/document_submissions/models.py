from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class ReviewAction:
    UPLOAD = "UPLOAD"
    START_REVIEW = "START_REVIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ATTACH_APPEND = "ATTACH_APPEND"
    REPLACE_UPLOAD = "REPLACE_UPLOAD"


class DocumentReviewHistory(Base):
    __tablename__ = "document_review_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("document_instances.id"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    action_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    from_workflow_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_workflow_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    action_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    instance: Mapped["DocumentInstance"] = relationship("DocumentInstance")
    document: Mapped["Document"] = relationship("Document")
    action_by: Mapped["User"] = relationship("User")

