from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SiteBase(BaseModel):
    site_code: str
    site_name: str

    start_date: date | None = None
    end_date: date | None = None
    contract_type: str | None = None
    contract_date: date | None = None
    client_name: str | None = None
    contractor_name: str | None = None
    project_amount: int | None = None
    phone_number: str | None = None
    address: str | None = None
    building_count: int | None = None
    floor_underground: int | None = None
    floor_ground: int | None = None
    household_count: int | None = None
    gross_area: int | None = None
    gross_area_unit: str | None = None
    main_usage: str | None = None
    work_types: str | None = None
    project_manager: str | None = None
    site_manager: str | None = None
    notes: str | None = None


class SiteCreateRequest(SiteBase):
    pass


class SiteUpdateRequest(BaseModel):
    site_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    contract_type: str | None = None
    contract_date: date | None = None
    client_name: str | None = None
    contractor_name: str | None = None
    project_amount: int | None = None
    phone_number: str | None = None
    address: str | None = None
    building_count: int | None = None
    floor_underground: int | None = None
    floor_ground: int | None = None
    household_count: int | None = None
    gross_area: int | None = None
    gross_area_unit: str | None = None
    main_usage: str | None = None
    work_types: str | None = None
    project_manager: str | None = None
    site_manager: str | None = None
    notes: str | None = None


class SiteResponse(SiteBase):
    id: int
    status: str | None = None
    manager_name: str | None = None
    description: str | None = None
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SiteWorkerResponse(BaseModel):
    person_id: int
    employment_id: int
    name: str
    department_name: str | None = None
    position_name: str | None = None
    site_code: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SiteSearchResponse(BaseModel):
    id: int
    name: str
    address: str | None = None


class SiteManagerResolved(BaseModel):
    manager_type: str
    source_name: str | None = None
    person_id: int | None = None
    employment_id: int | None = None
    position_code: str | None = None
    role_label: str | None = None
    resolve_status: str


class SiteManagementSummaryResponse(BaseModel):
    site_id: int
    site_code: str
    project_manager: SiteManagerResolved
    site_manager: SiteManagerResolved
    safety_manager: SiteManagerResolved


class SiteImportError(BaseModel):
    row_index: int
    error: str


class SiteImportResult(BaseModel):
    total_rows: int
    created_rows: int
    updated_rows: int
    failed_rows: int
    errors: list[SiteImportError]
    batch_id: int
    original_filename: str
    stored_path: str

