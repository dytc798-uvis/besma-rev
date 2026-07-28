from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class SafetyVehicle(Base):
    __tablename__ = "safety_vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_name: Mapped[str] = mapped_column(String(100), nullable=False)
    plate_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    department: Mapped[str] = mapped_column(String(100), nullable=False, default="안전보건실")
    ownership_type: Mapped[str] = mapped_column(String(30), nullable=False, default="0.회사")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    drivers: Mapped[list["SafetyVehicleDriver"]] = relationship(
        back_populates="vehicle",
        cascade="all, delete-orphan",
        order_by="SafetyVehicleDriver.sort_order",
    )


class SafetyVehicleDriver(Base):
    __tablename__ = "safety_vehicle_drivers"
    __table_args__ = (UniqueConstraint("vehicle_id", "driver_name", name="uq_safety_vehicle_driver"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("safety_vehicles.id"), nullable=False, index=True)
    driver_name: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    vehicle: Mapped[SafetyVehicle] = relationship(back_populates="drivers")


class SafetyVehicleLog(Base):
    __tablename__ = "safety_vehicle_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("safety_vehicles.id"), nullable=False, index=True)
    driven_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    driver_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    use_type: Mapped[str] = mapped_column(String(50), nullable=False, default="6.업무용(왕복)")
    odometer_km: Mapped[int | None] = mapped_column(Integer)
    trip_km: Mapped[float | None] = mapped_column(Float)
    purpose: Mapped[str | None] = mapped_column(String(500))
    dashboard_image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    dashboard_original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NEEDS_REVIEW")
    extraction_confidence: Mapped[int | None] = mapped_column(Integer)
    extraction_raw_json: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    vehicle: Mapped[SafetyVehicle] = relationship()


class SafetyCardExpense(Base):
    __tablename__ = "safety_card_expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    site_name: Mapped[str | None] = mapped_column(String(200))
    merchant: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(500))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    note: Mapped[str | None] = mapped_column(String(500))
    receipt_image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    receipt_original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="NEEDS_REVIEW")
    extraction_confidence: Mapped[int | None] = mapped_column(Integer)
    extraction_raw_json: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
