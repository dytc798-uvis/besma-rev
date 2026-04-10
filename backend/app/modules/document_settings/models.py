from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class SubmissionCycle(Base):
    """
    주기 분류 마스터 (복수형 테이블명은 기존 관례와 통일: users, sites, documents, opinions...).
    - 실제 생성 규칙의 기본값은 DocumentTypeMaster에서 관리한다.
    """

    __tablename__ = "submission_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_auto_generatable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class DocumentTypeMaster(Base):
    """
    전사 공통 문서 유형 마스터 + 기본 제출 정책.
    - 기존 Document.document_type(문자열)과 code를 동일하게 맞춰 연결 기준으로 사용한다.
    - default_cycle_id는 NULL 대신 ADHOC cycle을 사용하므로 nullable=False.
    """

    __tablename__ = "document_type_masters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    default_cycle_id: Mapped[int] = mapped_column(
        ForeignKey("submission_cycles.id"), nullable=False
    )
    default_cycle: Mapped[SubmissionCycle] = relationship("SubmissionCycle")

    # 생성 규칙 (date 기준)
    generation_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    generation_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 기본적으로 자동 생성 대상인지
    is_required_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )


class DocumentRequirement(Base):
    """
    현장별 문서 제출 정책 override.
    - is_enabled=True  : override 규칙 활성. override_* 값이 비어있으면 DocumentTypeMaster 기본값 fallback.
    - is_enabled=False : 이 현장에서는 해당 문서유형 자동 생성하지 않음(미생성 규칙).
    - effective_from/to가 모두 NULL이면 상시 규칙(기간 제한 없음).
    """

    __tablename__ = "document_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True, index=True)
    document_type_id: Mapped[int] = mapped_column(
        ForeignKey("document_type_masters.id"), nullable=False, index=True
    )

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="MONTHLY")
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_rule_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    override_cycle_id: Mapped[int | None] = mapped_column(
        ForeignKey("submission_cycles.id"), nullable=True
    )
    override_generation_rule: Mapped[str | None] = mapped_column(String(50), nullable=True)
    override_generation_value: Mapped[str | None] = mapped_column(String(100), nullable=True)
    override_due_offset_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    site: Mapped["Site"] = relationship("Site")
    document_type: Mapped[DocumentTypeMaster] = relationship("DocumentTypeMaster")
    override_cycle: Mapped[SubmissionCycle] = relationship("SubmissionCycle")


class ContractorDocumentBundleItem(Base):
    """
    도급사(도급사업/하도급사업 포함)별 문서항목 묶음 override.

    MVP에서는 삼성 전용 그룹 1개 + 일반 그룹을 전제로,
    사이트별 문서 조회/상태 계산은 site_id로 하되,
    문서 요구사항 필드(is_enabled/is_required/frequency/due_rule_text/note/display_order)는
    이 override를 적용해 계산한다.
    """

    __tablename__ = "contractor_document_bundle_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # 예: "SAMSUNG", "GENERAL"
    group_key: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    document_type_id: Mapped[int] = mapped_column(
        ForeignKey("document_type_masters.id"), nullable=False, index=True
    )

    # DocumentRequirement과 동일한 의미의 필드(상태 계산에 사용)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="MONTHLY")
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    due_rule_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    document_type: Mapped[DocumentTypeMaster] = relationship("DocumentTypeMaster")

    __table_args__ = (
        # group_key + document_type_id는 문서항목 1개에 대해 단일 override만 허용
        sa.UniqueConstraint("group_key", "document_type_id", name="uq_contractor_bundle_item_group_doc"),
    )


class DynamicMenuConfig(Base):
    __tablename__ = "dynamic_menu_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    menu_type: Mapped[str] = mapped_column(String(20), nullable=False)  # BOARD | TABLE
    target_ui_type: Mapped[str] = mapped_column(String(20), nullable=False, default="SITE")  # SITE | HQ_SAFE | BOTH
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_config: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class DynamicMenuBoardPost(Base):
    __tablename__ = "dynamic_menu_board_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("dynamic_menu_configs.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class DynamicMenuBoardComment(Base):
    __tablename__ = "dynamic_menu_board_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("dynamic_menu_board_posts.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class DynamicMenuTableRow(Base):
    __tablename__ = "dynamic_menu_table_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    menu_id: Mapped[int] = mapped_column(ForeignKey("dynamic_menu_configs.id"), nullable=False, index=True)
    row_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

