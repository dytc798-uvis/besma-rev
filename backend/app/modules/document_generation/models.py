from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class DocumentInstanceStatus:
    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowStatus:
    NOT_SUBMITTED = "NOT_SUBMITTED"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class PeriodBasis:
    CYCLE = "CYCLE"
    AS_OF_FALLBACK = "AS_OF_FALLBACK"


class DocumentInstance(Base):
    """
    문서 자동생성/스케줄링 결과를 period 단위로 추적하는 테이블.
    - rule layer 결과(status_reason 등)를 스냅샷으로 저장해 운영 추적 가능하게 한다.
    - (site_id, document_type_code, period_basis, period_start, period_end)는 idempotency 키로 유니크 고정.
    """

    __tablename__ = "document_instances"
    __table_args__ = (
        UniqueConstraint(
            "site_id",
            "document_type_code",
            "period_basis",
            "period_start",
            "period_end",
            name="uq_document_instances_site_type_basis_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    document_type_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    generation_anchor_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    selected_requirement_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 업무 워크플로우 상태 (오케스트레이션 상태와 분리)
    workflow_status: Mapped[str] = mapped_column(String(20), nullable=False, index=True, default=WorkflowStatus.NOT_SUBMITTED)

    # cycle=None, period 미해석 등의 경로를 주기 기반 인스턴스와 구분하기 위한 필드
    period_basis: Mapped[str] = mapped_column(String(30), nullable=False)

    rule_is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cycle_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rule_generation_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_generation_value: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rule_due_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 사후 감사/재현력 강화를 위한 최소 스냅샷
    resolved_from: Mapped[str | None] = mapped_column(String(20), nullable=True)  # MASTER_DEFAULT / SITE_OVERRIDE
    resolved_cycle_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # master / override / none

    master_cycle_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    master_cycle_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    override_cycle_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    override_cycle_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    site: Mapped["Site"] = relationship("Site")

