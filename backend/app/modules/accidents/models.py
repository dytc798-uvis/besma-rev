# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class Accident(Base):
    """사고관리 운영 원장."""

    __tablename__ = "accidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    display_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    accident_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)

    report_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="initial_report", server_default="initial_report"
    )
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="naverworks_message", server_default="naverworks_message"
    )

    message_raw: Mapped[str] = mapped_column(Text, nullable=False)

    site_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reporter_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    accident_datetime_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    accident_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    accident_place: Mapped[str | None] = mapped_column(String(512), nullable=True)
    work_content: Mapped[str | None] = mapped_column(String(512), nullable=True)
    injured_person_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    accident_circumstance: Mapped[str | None] = mapped_column(String(512), nullable=True)
    accident_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    injured_part: Mapped[str | None] = mapped_column(String(256), nullable=True)
    diagnosis_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="신규", server_default="신규")
    management_category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="일반", server_default="일반"
    )
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="미검증", server_default="미검증"
    )
    site_standard_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initial_report_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    nas_folder_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    nas_folder_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    parse_status: Mapped[str] = mapped_column(String(16), nullable=False)
    parse_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    attachments: Mapped[list["AccidentAttachment"]] = relationship(
        "AccidentAttachment",
        back_populates="accident",
        cascade="all, delete-orphan",
        order_by="AccidentAttachment.id.asc()",
    )

    @property
    def has_attachments(self) -> bool:
        return bool(self.attachments)


class AccidentAttachment(Base):
    __tablename__ = "accident_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    accident_id_fk: Mapped[int] = mapped_column(ForeignKey("accidents.id"), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    accident: Mapped["Accident"] = relationship("Accident", back_populates="attachments")


class AccidentSiteStandard(Base):
    __tablename__ = "accident_site_standards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
