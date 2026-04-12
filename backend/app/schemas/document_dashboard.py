from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class RequirementStatusItem(BaseModel):
    requirement_id: int
    document_type_code: str
    title: str
    frequency: str
    is_required: bool
    status: str
    latest_document_id: int | None = None
    latest_instance_id: int | None = None
    latest_uploaded_at: datetime | None = None
    review_note: str | None = None
    due_rule_text: str | None = None
    category: str | None = None
    section: str | None = None
    completion_upload_enabled: bool = False
    current_cycle_status: str | None = None
    current_cycle_document_id: int | None = None
    current_cycle_instance_id: int | None = None
    current_cycle_uploaded_at: datetime | None = None
    current_cycle_review_note: str | None = None
    current_cycle_file_name: str | None = None
    current_cycle_file_download_url: str | None = None
    current_cycle_start: date | None = None
    current_cycle_end: date | None = None
    current_cycle_target: bool = False
    current_period_label: str | None = None
    site_display_bucket: str | None = None
    current_cycle_needs_reupload: bool = False
    current_cycle_last_submission_status: str | None = None
    unresolved_rejected_document_id: int | None = None
    unresolved_rejected_instance_id: int | None = None
    unresolved_rejected_uploaded_at: datetime | None = None
    unresolved_rejected_reviewed_at: datetime | None = None
    unresolved_rejected_review_note: str | None = None
    unresolved_rejected_file_name: str | None = None
    unresolved_rejected_file_download_url: str | None = None
    unresolved_rejected_cycle_start: date | None = None
    unresolved_rejected_cycle_end: date | None = None
    rejected_backlog_count: int = 0
    rejected_backlog_items: list[dict] = Field(default_factory=list)


class RequirementStatusResponse(BaseModel):
    site_id: int
    period: str
    date: date
    summary: dict[str, int]
    completion_upload_enabled: bool = False
    completion_window_start: date | None = None
    completion_window_end: date | None = None
    items: list[RequirementStatusItem]


class HQDashboardSiteSummary(BaseModel):
    site_id: int
    site_name: str
    total_required: int
    submitted_count: int
    approved_count: int
    in_review_count: int
    rejected_count: int
    not_submitted_count: int
    incomplete_count: int
    submission_rate: float


class HQDashboardResponse(BaseModel):
    period: str
    date: date
    total_sites: int
    pending_review_count: int
    rejected_count: int
    not_submitted_count: int
    approved_count: int
    site_summaries: list[HQDashboardSiteSummary]
    items: list[dict]
    signal_status: str
    pending_documents: list[dict]
    approval_history: list[dict]
