from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class DocumentInstanceRead(BaseModel):
    id: int
    site_id: int
    document_type_code: str
    period_start: date
    period_end: date
    generation_anchor_date: date | None = None
    due_date: date | None = None

    status: str
    status_reason: str
    selected_requirement_id: int | None = None

    period_basis: str

    rule_is_required: bool
    cycle_code: str | None = None
    rule_generation_rule: str | None = None
    rule_generation_value: str | None = None
    rule_due_offset_days: int | None = None

    resolved_from: str | None = None
    resolved_cycle_source: str | None = None
    master_cycle_id: int | None = None
    master_cycle_code: str | None = None
    override_cycle_id: int | None = None
    override_cycle_code: str | None = None

    document_id: int | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class BackfillRequest(BaseModel):
    site_id: int
    start_date: date
    end_date: date
    dry_run: bool = True

    retry_failed: bool = False
    reevaluate_skipped: bool = False

    document_type_codes: list[str] | None = None

