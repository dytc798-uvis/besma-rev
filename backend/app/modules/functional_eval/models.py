from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class FunctionalEvalPeriod(Base):
    __tablename__ = "functional_eval_periods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    deadline_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_attendance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    workers: Mapped[list["FunctionalEvalWorker"]] = relationship(
        "FunctionalEvalWorker", back_populates="period"
    )
    sanctions: Mapped[list["FunctionalEvalSanction"]] = relationship(
        "FunctionalEvalSanction", back_populates="period"
    )
    import_batches: Mapped[list["FunctionalEvalRosterImportBatch"]] = relationship(
        "FunctionalEvalRosterImportBatch", back_populates="period"
    )
    attendance_batches: Mapped[list["FunctionalEvalAttendanceImportBatch"]] = relationship(
        "FunctionalEvalAttendanceImportBatch", back_populates="period"
    )
    attendance_entries: Mapped[list["FunctionalEvalAttendanceEntry"]] = relationship(
        "FunctionalEvalAttendanceEntry", back_populates="period"
    )


class FunctionalEvalRosterImportBatch(Base):
    __tablename__ = "functional_eval_roster_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    period: Mapped[FunctionalEvalPeriod] = relationship(
        "FunctionalEvalPeriod", back_populates="import_batches"
    )


class FunctionalEvalAttendanceImportBatch(Base):
    __tablename__ = "functional_eval_attendance_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    linked_workers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_no_roster: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    period: Mapped[FunctionalEvalPeriod] = relationship(
        "FunctionalEvalPeriod", back_populates="attendance_batches"
    )


class FunctionalEvalAttendanceEntry(Base):
    __tablename__ = "functional_eval_attendance_entries"
    __table_args__ = (
        UniqueConstraint("period_id", "work_date", "rrn_hash", name="uq_fe_attendance_period_date_rrn"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    worker_id: Mapped[int | None] = mapped_column(
        ForeignKey("functional_eval_workers.id"), nullable=True, index=True
    )
    site_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    rrn_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rep_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    erp_site_label: Mapped[str | None] = mapped_column(String(500), nullable=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("functional_eval_attendance_import_batches.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    period: Mapped[FunctionalEvalPeriod] = relationship(
        "FunctionalEvalPeriod", back_populates="attendance_entries"
    )


class FunctionalEvalWorker(Base):
    __tablename__ = "functional_eval_workers"
    __table_args__ = (
        UniqueConstraint("period_id", "rrn_hash", name="uq_fe_worker_period_rrn"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False)
    site_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    site_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    row_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    position_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    job_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rrn_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rrn_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    job_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_site_manager: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_on_reference_roster: Mapped[bool] = mapped_column(default=True, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mileage_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mileage_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    period: Mapped[FunctionalEvalPeriod] = relationship("FunctionalEvalPeriod", back_populates="workers")
    sanctions: Mapped[list["FunctionalEvalSanction"]] = relationship(
        "FunctionalEvalSanction", back_populates="worker"
    )
    assessments: Mapped[list["FunctionalEvalAssessment"]] = relationship(
        "FunctionalEvalAssessment", back_populates="worker"
    )


class FunctionalEvalAssessment(Base):
    """2-1(기능) / 2-2(안전) 인사고과 점수 — 근로자·유형당 1건."""

    __tablename__ = "functional_eval_assessments"
    __table_args__ = (
        UniqueConstraint("worker_id", "eval_type", name="uq_fe_assessment_worker_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_workers.id"), nullable=False, index=True)
    eval_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scores_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grade_code: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    grade_label: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    worker: Mapped["FunctionalEvalWorker"] = relationship("FunctionalEvalWorker", back_populates="assessments")


class FunctionalEvalSanction(Base):
    __tablename__ = "functional_eval_sanctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_workers.id"), nullable=False, index=True)
    site_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    violation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    violation_category: Mapped[str] = mapped_column(String(50), nullable=False)
    strike_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sanction_result: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    period: Mapped[FunctionalEvalPeriod] = relationship("FunctionalEvalPeriod", back_populates="sanctions")
    worker: Mapped[FunctionalEvalWorker] = relationship("FunctionalEvalWorker", back_populates="sanctions")
