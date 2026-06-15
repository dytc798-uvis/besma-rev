from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, JSON
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
    hq_grade_stats_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hq_grade_stats_computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grade_stats_live_from: Mapped[date | None] = mapped_column(Date, nullable=True)
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


class FunctionalEvalSiteRegistry(Base):
    """월별현장별집계 기준 현장코드·ERP 현장명·로그인 별칭(대우청라 등)."""

    __tablename__ = "functional_eval_site_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    site_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    erp_site_label: Mapped[str] = mapped_column(String(500), nullable=False)
    site_alias: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    manager_name: Mapped[str] = mapped_column(String(100), nullable=False)
    manager_login_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    erp_headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    erp_man_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    erp_work_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
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
    assigned_evaluator_login_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    is_site_manager: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_on_reference_roster: Mapped[bool] = mapped_column(default=True, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mileage_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mileage_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evaluation_batch: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
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
    assessment_revisions: Mapped[list["FunctionalEvalAssessmentRevision"]] = relationship(
        "FunctionalEvalAssessmentRevision", back_populates="worker"
    )
    customer_rewards: Mapped[list["FunctionalEvalCustomerReward"]] = relationship(
        "FunctionalEvalCustomerReward", back_populates="worker"
    )


class FunctionalEvalCustomerReward(Base):
    """현장 고객사 포상 — 사진 제출 · 본사 승인 시 가점."""

    __tablename__ = "functional_eval_customer_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_workers.id"), nullable=False, index=True)
    site_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    photo_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    bonus_points: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    worker: Mapped["FunctionalEvalWorker"] = relationship("FunctionalEvalWorker", back_populates="customer_rewards")


class FunctionalEvalSiteApproval(Base):
    """현장별 평가 승인: 소장 전체 → 안전보건실 → 대표이사."""

    __tablename__ = "functional_eval_site_approvals"
    __table_args__ = (
        UniqueConstraint("period_id", "site_code", name="uq_fe_site_approval_period_site"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False, index=True)
    site_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="IN_PROGRESS", index=True)
    site_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    site_submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_officer_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hq_officer_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    hq_officer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    hq_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    hq_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ceo_approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ceo_approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_stage: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now, nullable=False
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


class FunctionalEvalAssessmentRevision(Base):
    """본사 점수 수정·제재 연동 C등급 등 평가 변경 감사 로그."""

    __tablename__ = "functional_eval_assessment_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_workers.id"), nullable=False, index=True)
    eval_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    before_scores_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_scores_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    before_grade_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    after_grade_code: Mapped[str] = mapped_column(String(10), nullable=False, default="")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="HQ_OVERRIDE", index=True)
    sanction_id: Mapped[int | None] = mapped_column(
        ForeignKey("functional_eval_sanctions.id"), nullable=True, index=True
    )
    edited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    worker: Mapped["FunctionalEvalWorker"] = relationship("FunctionalEvalWorker", back_populates="assessment_revisions")


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
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False, default="COMMENT")
    evidence_photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    evidence_photo_original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    penalty_points: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="APPROVED", server_default="APPROVED", index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reject_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    period: Mapped[FunctionalEvalPeriod] = relationship("FunctionalEvalPeriod", back_populates="sanctions")
    worker: Mapped[FunctionalEvalWorker] = relationship("FunctionalEvalWorker", back_populates="sanctions")


class FunctionalEvalConsent(Base):
    """기능인제 최초 로그인 동의서 — 사용자당 1회."""

    __tablename__ = "functional_eval_consents"
    __table_args__ = (UniqueConstraint("user_id", name="uq_fe_consent_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    login_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    signature_data: Mapped[str] = mapped_column(Text, nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signer_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signer_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_document_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="evaluator", server_default="evaluator")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class FunctionalEvalViewerProvisionLog(Base):
    """본사 조회전용 계정 일괄 생성 이력."""

    __tablename__ = "fe_viewer_provision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # dry_run | apply
    source_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_login_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    applied_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class FunctionalEvalSignature(Base):
    """기능인제 단계별 서명 (팀장·소장·본사·대표)."""

    __tablename__ = "functional_eval_signatures"
    __table_args__ = (
        UniqueConstraint(
            "period_id",
            "evaluation_batch",
            "stage",
            "site_code",
            "team_leader_login_id",
            name="uq_fe_signature_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False, index=True)
    evaluation_batch: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    stage: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    site_code: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    team_leader_login_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    signer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    signer_login_id: Mapped[str] = mapped_column(String(50), nullable=False)
    signer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_label: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    worker_scope_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signature_data: Mapped[str] = mapped_column(Text, nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signer_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signer_user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_document_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class FunctionalEvalDailyReport(Base):
    """기능인제 일일 진행현황 보고서 (21:00 KST 기준)."""

    __tablename__ = "functional_eval_daily_reports"
    __table_args__ = (
        UniqueConstraint("period_id", "report_date", name="uq_fe_daily_report_period_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("functional_eval_periods.id"), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    criteria_at_kst: Mapped[str] = mapped_column(String(40), nullable=False)
    timezone: Mapped[str] = mapped_column(String(40), nullable=False, default="Asia/Seoul")
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    regenerated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_workers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_workers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bottleneck_site_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_format: Mapped[str] = mapped_column(String(20), nullable=False, default="pdf")
    report_json_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generated_by: Mapped[str] = mapped_column(String(20), nullable=False, default="system")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
