from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class InspectionJournal(Base):
    __tablename__ = "inspection_journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    inspected_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_text: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(300))
    attendees: Mapped[str | None] = mapped_column(Text)
    instructor_name: Mapped[str | None] = mapped_column(String(100))
    instructor_affiliation: Mapped[str | None] = mapped_column(String(200))
    training_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    training_label: Mapped[str] = mapped_column(String(150), nullable=False)
    legal_content: Mapped[str] = mapped_column(Text, nullable=False)
    additional_content: Mapped[str | None] = mapped_column(Text)
    special_notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_by_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    photos: Mapped[list["InspectionJournalPhoto"]] = relationship(
        back_populates="journal",
        cascade="all, delete-orphan",
        order_by="InspectionJournalPhoto.sort_order",
    )


class InspectionJournalPhoto(Base):
    __tablename__ = "inspection_journal_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    journal_id: Mapped[int] = mapped_column(ForeignKey("inspection_journals.id"), nullable=False, index=True)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    caption: Mapped[str | None] = mapped_column(String(500))
    rotation_degrees: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    crop_left: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    crop_top: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    crop_right: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    crop_bottom: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    journal: Mapped[InspectionJournal] = relationship(back_populates="photos")
