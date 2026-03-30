from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    site_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 계약/기간/거래처 정보
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contract_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contractor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # 금액
    project_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 연락처/위치
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # 건축 정보
    building_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor_underground: Mapped[int | None] = mapped_column(Integer, nullable=True)
    floor_ground: Mapped[int | None] = mapped_column(Integer, nullable=True)
    household_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_area: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross_area_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    main_usage: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 공종/담당/비고
    work_types: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_manager: Mapped[str | None] = mapped_column(String(100), nullable=True)
    site_manager: Mapped[str | None] = mapped_column(String(100), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 현장 위치 기반 서명 검증용 좌표/허용 반경
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    allowed_radius_m: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 기존 상태/설명 필드(호환용)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 메타 추적
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="site",
        foreign_keys="User.site_id",
    )


class SiteImportBatch(Base):
    __tablename__ = "site_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
