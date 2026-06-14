from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class FunctionalEvalPeriodOut(BaseModel):
    id: int
    title: str
    deadline_date: date
    is_active: bool
    is_closed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FunctionalEvalPeriodDeadlineUpdate(BaseModel):
    deadline_date: date


class ViolationCatalogItemOut(BaseModel):
    code: str
    category: str
    category_label: str
    label: str
    sanction_rule: str
    sort_order: int


class FunctionalEvalSanctionCreate(BaseModel):
    worker_id: int
    violation_code: str
    note: str = Field(..., min_length=1, max_length=2000)


class FunctionalEvalSanctionOut(BaseModel):
    id: int
    period_id: int
    worker_id: int
    site_code: str
    worker_name: str
    violation_code: str
    violation_label: str
    violation_category: str
    violation_category_label: str
    strike_number: int
    sanction_result: str
    sanction_result_label: str
    note: str | None
    reported_by_user_id: int | None
    reported_by_name: str | None = None
    reported_by_login_id: str | None = None
    created_at: datetime


class FunctionalEvalAssessmentSave(BaseModel):
    scores: dict[str, str] = Field(default_factory=dict)


class FunctionalEvalHqAssessmentOverride(BaseModel):
    scores: dict[str, str] = Field(default_factory=dict)
    reason: str = Field(..., min_length=1, max_length=2000)


class FunctionalEvalAssessmentRevisionOut(BaseModel):
    id: int
    worker_id: int
    eval_type: str
    before_grade_code: str | None
    after_grade_code: str
    reason: str
    source: str
    sanction_id: int | None
    edited_by_user_id: int | None
    edited_by_name: str | None = None
    edited_by_login_id: str | None = None
    created_at: datetime


class FunctionalEvalApprovalReject(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class FunctionalEvalSignatureSubmit(BaseModel):
    signature_data: str = Field(..., min_length=32)
    consent_acknowledged: bool = False


class FunctionalEvalHqApprovalSubmit(FunctionalEvalSignatureSubmit):
    officer_comment: str | None = Field(default=None, max_length=4000, description="안전보건 담당자 검토 코멘트")
    director_comment: str | None = Field(default=None, max_length=4000, description="안전보건실장 최종 코멘트")


class FunctionalEvalConsentSubmit(BaseModel):
    signature_data: str = Field(..., min_length=32)
    consent_acknowledged: bool = Field(..., description="동의서 확인 체크")


class FunctionalEvalAssessmentOut(BaseModel):
    eval_type: str
    scores: dict[str, str]
    total_score: int
    max_score: int
    grade_code: str
    grade_label: str
    is_complete: bool
    updated_at: datetime | None = None


class FunctionalEvalWorkerOut(BaseModel):
    id: int
    period_id: int
    site_code: str
    site_name: str | None
    row_no: int
    name: str
    age_label: str | None
    position_name: str | None
    job_name: str | None
    rrn_masked: str | None
    is_site_manager: bool
    sanction_status: str
    sanction_status_label: str
    sanction_count: int
    latest_sanction: FunctionalEvalSanctionOut | None = None
    functional_assessment: FunctionalEvalAssessmentOut | None = None
    safety_assessment: FunctionalEvalAssessmentOut | None = None


class FunctionalEvalHqSummaryItem(BaseModel):
    worker: FunctionalEvalWorkerOut
    sanctions: list[FunctionalEvalSanctionOut]


class FunctionalEvalHqSummaryResponse(BaseModel):
    period: FunctionalEvalPeriodOut
    items: list[FunctionalEvalHqSummaryItem]
    sort_by: str
    sort_dir: str
