from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.datetime_utils import utc_now


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    birth_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    rrn_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    rrn_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone_mobile: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_foreigner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nationality: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    employments: Mapped[list["Employment"]] = relationship(
        "Employment", back_populates="person"
    )


class Employment(Base):
    __tablename__ = "employments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    employee_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hire_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    termination_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    site_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    daily_wage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

    person: Mapped[Person] = relationship("Person", back_populates="employments")


class WorkerImportBatch(Base):
    __tablename__ = "worker_import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    diff_new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diff_updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    diff_unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )


class WorkerInactiveCandidate(Base):
    __tablename__ = "worker_inactive_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), nullable=False)
    employment_id: Mapped[int | None] = mapped_column(
        ForeignKey("employments.id"), nullable=True
    )
    rrn_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="employee")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CANDIDATE")
    resolution: Mapped[str | None] = mapped_column(String(50), nullable=True)
    missing_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    detected_in_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("worker_import_batches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
    )

