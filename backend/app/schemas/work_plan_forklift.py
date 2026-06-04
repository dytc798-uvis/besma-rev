from __future__ import annotations

from pydantic import BaseModel, Field


class ForkliftWorkPlanInput(BaseModel):
    """지게차(일반) 작업계획서 — 웹 입력 → 엑셀 셀 매핑용."""

    site_name: str = Field(default="", description="현장명 (A1)")
    company_name: str = Field(default="(주)부현전기", description="협력사/업체명 (K8)")
    document_date_year: str = Field(default="", description="작성일자 연 (AD6)")
    document_date_month: str = Field(default="", description="작성일자 월")
    document_date_day: str = Field(default="", description="작성일자 일")
    work_name: str = Field(..., description="작업명")
    period_start_year: str = Field(default="", description="작업기간 시작 연")
    period_start_month: str = Field(default="", description="작업기간 시작 월")
    period_start_day: str = Field(default="", description="작업기간 시작 일")
    period_end_year: str = Field(default="", description="작업기간 종료 연")
    period_end_month: str = Field(default="", description="작업기간 종료 월")
    period_end_day: str = Field(default="", description="작업기간 종료 일")
    work_location: str = Field(default="", description="작업장소 (AD7)")
    safety_meeting_company: str = Field(default="", description="안전회의 협력사 라벨 보조")
    participants: str = Field(default="", description="안전회의 인원 (AD8)")
    supervisor_name: str = Field(default="", description="책임자 성명")
    supervisor_phone: str = Field(default="", description="책임자 연락처")
    supervisor_license_type: str = Field(default="", description="책임자 면허 종류")
    supervisor_license_no: str = Field(default="", description="책임자 면허 번호")
    signal_name: str = Field(default="", description="신호수 성명")
    signal_phone: str = Field(default="", description="신호수 연락처")
    signal_license_type: str = Field(default="", description="신호수 면허 종류")
    signal_license_no: str = Field(default="", description="신호수 면허 번호")
    commander_name: str = Field(default="", description="작업지휘자 성명")
    commander_role: str = Field(default="", description="작업지휘자 직책")
    equipment_type: str = Field(default="", description="장비 종류")
    equipment_model: str = Field(default="", description="모델명")
    registration_no: str = Field(default="", description="등록번호")
    manufacture_year: str = Field(default="", description="제작년도")
    rated_capacity: str = Field(default="", description="정격하중/적재능력")
    registered_company: str = Field(default="", description="등록업체명 (AI22)")
    length_mm: str | int | float | None = Field(default=None, description="길이/전장(mm)")
    width_mm: str | int | float | None = Field(default=None, description="너비/전폭(mm)")
    height_mm: str | int | float | None = Field(default=None, description="높이/전고(mm)")
    max_lifting_kg: str | int | float | None = Field(default=None, description="허용하중(kg)")
    work_location_plan: str = Field(default="", description="작업장소/계획 (일일)")
    work_content_plan: str = Field(default="", description="작업내용/계획 (일일)")


class ForkliftWorkPlanGenerateResponse(BaseModel):
    filename: str
    saved_path: str
    download_url: str
    sheet_name: str


class ForkliftEquipmentSpecResponse(BaseModel):
    model: str = ""
    equipment_type: str = ""
    rated_capacity: str = ""
    manufacture_year: str = ""
    length_mm: int | None = None
    width_mm: int | None = None
    height_mm: int | None = None
    max_lifting_kg: int | None = None
    source: str = "none"
    confidence: str = "low"
