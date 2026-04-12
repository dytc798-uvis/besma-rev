from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    UniqueConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class RiskLibraryItem(Base):
    __tablename__ = "risk_library_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    owner_site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    revisions: Mapped[list["RiskLibraryItemRevision"]] = relationship(
        "RiskLibraryItemRevision",
        back_populates="item",
        cascade="all, delete-orphan",
    )


class RiskLibraryItemRevision(Base):
    __tablename__ = "risk_library_item_revisions"
    __table_args__ = (
        Index(
            "uq_risk_library_item_current_true",
            "item_id",
            unique=True,
            sqlite_where=text("is_current = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("risk_library_items.id"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    unit_work: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    work_category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    trade_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    process: Mapped[str] = mapped_column(Text, nullable=False, default="미기재")

    risk_factor: Mapped[str] = mapped_column(Text, nullable=False)
    risk_cause: Mapped[str] = mapped_column(Text, nullable=False)
    countermeasure: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_file: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    source_sheet: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_page_or_section: Mapped[str | None] = mapped_column(String(255), nullable=True)

    risk_f: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    risk_s: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    risk_r: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    revised_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    revised_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    revision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    item: Mapped[RiskLibraryItem] = relationship(
        "RiskLibraryItem",
        back_populates="revisions",
    )
    keywords: Mapped[list["RiskLibraryKeyword"]] = relationship(
        "RiskLibraryKeyword",
        back_populates="risk_revision",
        cascade="all, delete-orphan",
    )


class RiskLibraryKeyword(Base):
    __tablename__ = "risk_library_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    risk_revision_id: Mapped[int] = mapped_column(
        ForeignKey("risk_library_item_revisions.id"), nullable=False, index=True
    )
    keyword: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    risk_revision: Mapped[RiskLibraryItemRevision] = relationship(
        "RiskLibraryItemRevision",
        back_populates="keywords",
    )


class DailyWorkPlan(Base):
    __tablename__ = "daily_work_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    items: Mapped[list["DailyWorkPlanItem"]] = relationship(
        "DailyWorkPlanItem",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    confirmations: Mapped[list["DailyWorkPlanConfirmation"]] = relationship(
        "DailyWorkPlanConfirmation",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    document_links: Mapped[list["DailyWorkPlanDocumentLink"]] = relationship(
        "DailyWorkPlanDocumentLink",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    distributions: Mapped[list["DailyWorkPlanDistribution"]] = relationship(
        "DailyWorkPlanDistribution",
        back_populates="plan",
        cascade="all, delete-orphan",
    )


class DailyWorkPlanItem(Base):
    __tablename__ = "daily_work_plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plans.id"), nullable=False, index=True
    )
    work_name: Mapped[str] = mapped_column(String(255), nullable=False)
    work_description: Mapped[str] = mapped_column(Text, nullable=False)
    team_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    leader_person_id: Mapped[int | None] = mapped_column(ForeignKey("persons.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    plan: Mapped[DailyWorkPlan] = relationship("DailyWorkPlan", back_populates="items")
    risk_refs: Mapped[list["DailyWorkPlanItemRiskRef"]] = relationship(
        "DailyWorkPlanItemRiskRef",
        back_populates="plan_item",
        cascade="all, delete-orphan",
    )


class DailyWorkPlanItemRiskRef(Base):
    __tablename__ = "daily_work_plan_item_risk_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_item_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plan_items.id"), nullable=False, index=True
    )
    risk_item_id: Mapped[int] = mapped_column(
        ForeignKey("risk_library_items.id"), nullable=False, index=True
    )
    risk_revision_id: Mapped[int] = mapped_column(
        ForeignKey("risk_library_item_revisions.id"), nullable=False, index=True
    )

    link_type: Mapped[str] = mapped_column(String(20), nullable=False, default="RECOMMENDED")
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_rule: Mapped[str] = mapped_column(String(20), nullable=False, default="KEYWORD_MATCH")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    site_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    site_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    site_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hq_final_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hq_final_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    hq_final_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    plan_item: Mapped[DailyWorkPlanItem] = relationship(
        "DailyWorkPlanItem",
        back_populates="risk_refs",
    )


class DailyWorkPlanConfirmation(Base):
    __tablename__ = "daily_work_plan_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "confirmed_by_user_id",
            name="uq_daily_work_plan_confirm_user",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plans.id"), nullable=False, index=True
    )
    confirmed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    plan: Mapped[DailyWorkPlan] = relationship(
        "DailyWorkPlan",
        back_populates="confirmations",
    )


class DailyWorkPlanDocumentLink(Base):
    __tablename__ = "daily_work_plan_document_links"
    __table_args__ = (
        UniqueConstraint(
            "instance_id",
            "plan_id",
            name="uq_daily_work_plan_document_links_instance_plan",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("document_instances.id"), nullable=False, index=True
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plans.id"), nullable=False, index=True
    )
    assembled_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    assembled_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    plan: Mapped[DailyWorkPlan] = relationship(
        "DailyWorkPlan",
        back_populates="document_links",
    )


class DailyWorkPlanDistribution(Base):
    __tablename__ = "daily_work_plan_distributions"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "target_date",
            name="uq_daily_work_plan_distributions_plan_target_date",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plans.id"), nullable=False, index=True
    )
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    visible_from: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    distributed_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    distributed_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SCHEDULED")
    tbm_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    tbm_started_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    tbm_closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parent_distribution_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_work_plan_distributions.id"),
        nullable=True,
        index=True,
    )
    is_reassignment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reassignment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reassigned_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    reassigned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    plan: Mapped[DailyWorkPlan] = relationship(
        "DailyWorkPlan",
        back_populates="distributions",
    )
    workers: Mapped[list["DailyWorkPlanDistributionWorker"]] = relationship(
        "DailyWorkPlanDistributionWorker",
        back_populates="distribution",
        cascade="all, delete-orphan",
    )


class DailyWorkPlanDistributionWorker(Base):
    __tablename__ = "daily_work_plan_distribution_workers"
    __table_args__ = (
        UniqueConstraint(
            "distribution_id",
            "person_id",
            name="uq_daily_work_plan_distribution_workers_distribution_person",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    distribution_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plan_distributions.id"), nullable=False, index=True
    )
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False, index=True)
    employment_id: Mapped[int | None] = mapped_column(
        ForeignKey("employments.id"), nullable=True, index=True
    )
    access_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    ack_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    start_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_mime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    start_signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_signature_mime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    issue_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    end_signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    end_signature_mime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    end_signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    distribution: Mapped[DailyWorkPlanDistribution] = relationship(
        "DailyWorkPlanDistribution",
        back_populates="workers",
    )


class WorkerFeedback(Base):
    __tablename__ = "worker_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    distribution_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plan_distributions.id"),
        nullable=False,
        index=True,
    )
    distribution_worker_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plan_distribution_workers.id"),
        nullable=False,
        index=True,
    )
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False, index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("daily_work_plans.id"), nullable=False, index=True)
    plan_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_work_plan_items.id"),
        nullable=True,
        index=True,
    )
    feedback_type: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class RiskLibraryFeedbackCandidate(Base):
    __tablename__ = "risk_library_feedback_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feedback_id: Mapped[int] = mapped_column(
        ForeignKey("worker_feedbacks.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    inferred_unit_work: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inferred_process: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_risk_factor: Mapped[str | None] = mapped_column(Text, nullable=True)
    inferred_countermeasure: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_distribution_id: Mapped[int] = mapped_column(
        ForeignKey("daily_work_plan_distributions.id"),
        nullable=False,
        index=True,
    )
    source_plan_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_work_plan_items.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False,
    )
    approved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SiteAdminPresence(Base):
    __tablename__ = "site_admin_presences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "site_id",
            name="uq_site_admin_presences_user_site",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )
