from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class OpinionStatus(str):
    RECEIVED = "RECEIVED"
    REVIEWING = "REVIEWING"
    ACTIONED = "ACTIONED"
    HOLD = "HOLD"


class Opinion(Base):
    __tablename__ = "opinions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reporter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=OpinionStatus.RECEIVED)
    score_appropriateness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_actionability: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    site: Mapped["Site"] = relationship("Site")
    assigned_user: Mapped["User"] = relationship("User")

