from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.datetime_utils import utc_now


class HeatStressRecord(Base):
    __tablename__ = "heat_stress_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    work_location: Mapped[str] = mapped_column(String(200), nullable=False)
    work_process: Mapped[str | None] = mapped_column(String(200), nullable=True)
    measurement_source: Mapped[str] = mapped_column(String(20), nullable=False)
    air_temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    relative_humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    apparent_temperature_c: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    legal_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    company_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    actual_actions_json: Mapped[str] = mapped_column(Text, nullable=False)
    action_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_compliance: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    recorder_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    recorder_name: Mapped[str] = mapped_column(String(100), nullable=False)
    recorder_signature_data: Mapped[str] = mapped_column(Text, nullable=False)
    recorder_signature_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    recorder_signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    confirmer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    confirmer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmer_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confirmer_signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmer_signature_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmer_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CONFIRM_PENDING", index=True)
    template_code: Mapped[str] = mapped_column(String(40), nullable=False, default="HQ_DEFAULT_V1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class HeatStressAuditLog(Base):
    __tablename__ = "heat_stress_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("heat_stress_records.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
