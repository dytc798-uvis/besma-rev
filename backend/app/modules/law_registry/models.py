from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class LawMaster(Base):
    __tablename__ = "law_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    law_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    law_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    law_api_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    law_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    article_items: Mapped[list["LawArticleItem"]] = relationship(
        "LawArticleItem",
        back_populates="law_master",
        cascade="all, delete-orphan",
    )
    revision_histories: Mapped[list["LawRevisionHistory"]] = relationship(
        "LawRevisionHistory",
        back_populates="law_master",
        cascade="all, delete-orphan",
    )


class LawArticleItem(Base):
    __tablename__ = "law_article_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    law_master_id: Mapped[int] = mapped_column(
        ForeignKey("law_master.id"),
        nullable=False,
        index=True,
    )
    article_display: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    summary_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    action_required: Mapped[str | None] = mapped_column(Text, nullable=True)
    countermeasure: Mapped[str | None] = mapped_column(Text, nullable=True)
    penalty: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_type_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    law_master: Mapped[LawMaster] = relationship("LawMaster", back_populates="article_items")


class LawRevisionHistory(Base):
    __tablename__ = "law_revision_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    law_master_id: Mapped[int] = mapped_column(
        ForeignKey("law_master.id"),
        nullable=False,
        index=True,
    )
    revision_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    revision_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parse_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    law_master: Mapped[LawMaster] = relationship("LawMaster", back_populates="revision_histories")
