from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class ApprovalAction(str):
    SUBMIT = "SUBMIT"
    START_REVIEW = "START_REVIEW"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RESUBMIT = "RESUBMIT"


class ApprovalHistory(Base):
    __tablename__ = "approval_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), nullable=False)
    action_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    document: Mapped["Document"] = relationship("Document")
    action_by: Mapped["User"] = relationship("User")

