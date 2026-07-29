from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PublicAccountRequestCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone_mobile: str = Field(min_length=8, max_length=30)
    company_name: str = Field(min_length=2, max_length=150)
    scope: str
    department: str | None = Field(default=None, max_length=100)
    work_category: str
    site_code: str | None = Field(default=None, max_length=50)
    site_name: str | None = Field(default=None, max_length=200)
    request_reason: str = Field(min_length=5, max_length=2000)
    employment_evidence_note: str | None = Field(default=None, max_length=2000)
    privacy_consent: bool


class ExistingAccessRequestCreate(PublicAccountRequestCreate):
    request_type: str = "ACCESS_CHANGE"


class AccountRequestDecision(BaseModel):
    action: str
    comment: str | None = Field(default=None, max_length=2000)
    approved_role: str | None = None
    approved_site_id: int | None = None
    valid_until: datetime | None = None
    replace_existing_role: bool = False


class AccountRequestItem(BaseModel):
    id: int
    request_no: str
    request_type: str
    status: str
    applicant_user_id: int | None
    existing_user_id: int | None
    name: str
    phone_mobile_masked: str
    company_name: str
    scope: str
    department: str | None
    work_category: str
    site_id: int | None
    site_code: str | None
    site_name: str | None
    request_reason: str
    employment_evidence_note: str | None
    roster_match_status: str
    duplicate_candidate_ids: list[int]
    recommended_role: str | None
    current_role_snapshot: str | None
    current_site_id_snapshot: int | None
    approved_role: str | None
    approved_site_id: int | None
    valid_until: datetime | None
    handled_by_user_id: int | None
    handled_at: datetime | None
    decision_comment: str | None
    created_account_user_id: int | None
    created_at: datetime
    updated_at: datetime


class AccountRequestCreateResponse(BaseModel):
    request_no: str
    status: str
    message: str


class AccountRequestDecisionResponse(BaseModel):
    item: AccountRequestItem
    temporary_login_id: str | None = None
    temporary_password: str | None = None
    temporary_password_expires_at: datetime | None = None

