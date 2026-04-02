from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentInstanceHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instance_id: int
    site_id: int
    site_name: str
    document_type_code: str
    document_name: str
    period_basis: str
    period_start: date
    period_end: date
    period_label: str
    instance_status: str
    workflow_status: str
    is_missing: bool
    document_id: int | None
    current_file_name: str | None = None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    review_note: str | None
    review_result: str | None
    submission_count: int = Field(ge=0)
    reupload_count: int = Field(ge=0)
    uploaded_by_name: str | None = None


class DocumentInstanceHistoryListResponse(BaseModel):
    items: list[DocumentInstanceHistoryItem]
    total: int


class DocumentInstanceHistorySummaryResponse(BaseModel):
    total_instances: int
    approved_count: int
    under_review_count: int
    rejected_count: int
    missing_count: int
    completion_rate: float
