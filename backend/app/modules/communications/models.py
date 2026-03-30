from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    sender_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_user_id])
    attachments: Mapped[list["CommunicationAttachment"]] = relationship(
        "CommunicationAttachment",
        back_populates="communication",
        cascade="all, delete-orphan",
    )
    receivers: Mapped[list["CommunicationReceiver"]] = relationship(
        "CommunicationReceiver",
        back_populates="communication",
        cascade="all, delete-orphan",
    )


class CommunicationAttachment(Base):
    __tablename__ = "communication_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    communication_id: Mapped[int] = mapped_column(ForeignKey("communications.id"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False, default="image")
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    communication: Mapped["Communication"] = relationship("Communication", back_populates="attachments")


class CommunicationReceiver(Base):
    __tablename__ = "communication_receivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    communication_id: Mapped[int] = mapped_column(ForeignKey("communications.id"), nullable=False, index=True)
    receiver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    communication: Mapped["Communication"] = relationship("Communication", back_populates="receivers")
    receiver: Mapped["User"] = relationship("User", foreign_keys=[receiver_user_id])

