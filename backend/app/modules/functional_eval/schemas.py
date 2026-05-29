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
    note: str | None = Field(default=None, max_length=2000)


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
    created_at: datetime


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


class FunctionalEvalHqSummaryItem(BaseModel):
    worker: FunctionalEvalWorkerOut
    sanctions: list[FunctionalEvalSanctionOut]


class FunctionalEvalHqSummaryResponse(BaseModel):
    period: FunctionalEvalPeriodOut
    items: list[FunctionalEvalHqSummaryItem]
    sort_by: str
    sort_dir: str
