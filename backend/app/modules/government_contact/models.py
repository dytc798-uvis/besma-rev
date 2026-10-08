from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import utc_now


class GovernmentContactMessage(Base):
    __tablename__ = "government_contact_messages"
    __table_args__ = (Index("ix_gov_contact_site_created", "site_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sender_side: Mapped[str] = mapped_column(String(4), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
