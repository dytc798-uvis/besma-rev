# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AccidentParseCreateRequest(BaseModel):
    model_config = {"extra": "ignore"}

    input_mode: Literal["auto", "manual"] = "auto"
    message_raw: str | None = Field(default=None, description="최초보고 메시지 원문")
    template_name: str | None = None
    site_standard_name: str | None = None
    reporter_name: str | None = None
    accident_datetime_text: str | None = None
    accident_datetime: datetime | None = None
    accident_place: str | None = None
    work_content: str | None = None
    injured_person_name: str | None = None
    accident_circumstance: str | None = None
    accident_reason: str | None = None
    injured_part: str | None = None
    diagnosis_name: str | None = None
    action_taken: str | None = None
    status: str | None = None
    management_category: str | None = None
    notes: str | None = None
    parse_status_override: str | None = None
    parse_note_override: str | None = None

    @model_validator(mode="after")
    def validate_by_mode(self):
        if self.input_mode == "auto":
            if not (self.message_raw or "").strip():
                raise ValueError("자동입력 모드에서는 message_raw가 필요합니다.")
            return self

        required = {
            "현장명": self.site_standard_name,
            "보고자": self.reporter_name,
            "사고시각": self.accident_datetime_text or self.accident_datetime,
            "사고장소": self.accident_place,
            "작업내용": self.work_content,
        }
        missing = [label for label, value in required.items() if not value]
        if missing:
            raise ValueError(f"수동입력 필수값 누락: {', '.join(missing)}")
        return self


class AccidentUpdateRequest(BaseModel):
    model_config = {"extra": "ignore"}

    site_standard_name: str
    reporter_name: str | None = None
    status: str
    management_category: str
    accident_datetime_text: str | None = None
    accident_datetime: datetime | None = None
    accident_place: str | None = None
    work_content: str | None = None
    injured_person_name: str | None = None
    accident_circumstance: str | None = None
    accident_reason: str | None = None
    injured_part: str | None = None
    diagnosis_name: str | None = None
    action_taken: str | None = None
    notes: str | None = None
    initial_report_template: str | None = None


class AccidentAttachmentItem(BaseModel):
    id: int
    file_name: str
    stored_path: str
    content_type: str | None = None
    file_size: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccidentLookups(BaseModel):
    statuses: list[str]
    management_categories: list[str]
    site_names: list[str]


class AccidentListItem(BaseModel):
    id: int
    accident_id: str
    display_code: str
    parse_status: str
    site_name: str | None
    site_standard_name: str | None
    injured_person_name: str | None
    accident_datetime_text: str | None
    accident_datetime: datetime | None
    status: str
    management_category: str
    is_complete: bool
    has_attachments: bool
    nas_folder_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AccidentDetail(BaseModel):
    id: int
    accident_id: str
    display_code: str
    report_type: str
    source_type: str
    message_raw: str
    site_name: str | None
    reporter_name: str | None
    accident_datetime_text: str | None
    accident_datetime: datetime | None
    accident_place: str | None
    work_content: str | None
    injured_person_name: str | None
    accident_circumstance: str | None
    accident_reason: str | None
    injured_part: str | None
    diagnosis_name: str | None
    action_taken: str | None
    status: str
    management_category: str
    site_standard_name: str | None
    initial_report_template: str | None
    is_complete: bool
    nas_folder_path: str | None
    nas_folder_key: str | None
    notes: str | None
    parse_status: str
    parse_note: str | None
    created_by_user_id: int | None
    updated_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    attachments: list[AccidentAttachmentItem] = []

    model_config = {"from_attributes": True}


class AccidentInitialReportOutput(BaseModel):
    accident_id: int
    accident_code: str
    display_code: str
    parse_status: str
    composed_line: str
    fields: dict[str, Any]
    message_raw: str


class AccidentImportResult(BaseModel):
    imported: int
    skipped: int


class AccidentMasterExcelSyncResult(BaseModel):
    target_path: str
    backup_path: str | None
    exported_count: int
    excluded_count: int
    backup_created: bool


class AccidentParsePreviewResponse(BaseModel):
    parse_status: str
    parse_note: str | None
    composed_line: str
    fields: dict[str, Any]
    message_raw: str


class AccidentWorklistSection(BaseModel):
    count: int
    items: list[AccidentListItem]


class AccidentWorklistResponse(BaseModel):
    unverified: AccidentWorklistSection
    parse_review: AccidentWorklistSection
    missing_attachments: AccidentWorklistSection
    recent: AccidentWorklistSection
