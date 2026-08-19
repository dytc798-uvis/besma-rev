from datetime import date

from pydantic import BaseModel, Field, field_validator


class RiskLibraryContractorOption(BaseModel):
    contractor_key: str
    contractor_name: str
    evaluation_method: str


class RiskAssessmentDesignation(BaseModel):
    site_id: int | None = None
    site_name: str | None = None
    inspector_name: str | None = None
    verifier_name: str | None = None
    appointed_on: date | None = None
    note: str | None = None
    can_edit: bool = False


class RiskAssessmentDesignationUpdate(BaseModel):
    inspector_name: str | None = None
    verifier_name: str | None = None
    appointed_on: date | None = None
    note: str | None = None

    @field_validator("inspector_name", "verifier_name", "note")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None


class RiskLibrarySiteAssignmentUpdate(BaseModel):
    improvement_owner_name: str | None = None
    improvement_verifier_name: str | None = None

    @field_validator("improvement_owner_name", "improvement_verifier_name")
    @classmethod
    def strip_assignment_text(cls, value: str | None) -> str | None:
        text = (value or "").strip()
        return text or None


class RiskLibrarySiteAssignmentRead(BaseModel):
    site_id: int
    risk_item_id: int
    improvement_owner_name: str | None = None
    improvement_verifier_name: str | None = None


class RiskLibrarySearchResultItem(BaseModel):
    risk_revision_id: int
    risk_item_id: int
    unit_work: str | None = None
    work_category: str
    trade_type: str
    process: str
    risk_factor: str
    counterplan: str
    risk_f: int
    risk_s: int
    risk_r: int
    display_f: int | None = None
    display_s: int | None = None
    display_r: int | None = None
    risk_grade: str
    evaluation_method: str
    improvement_owner_name: str | None = None
    improvement_verifier_name: str | None = None
    note: str | None = None
    source_file: str | None = None
    source_sheet: str | None = None
    source_row: int | None = None
    source_page_or_section: str | None = None
    score: float
    matched_tokens: list[str] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)


class RiskLibrarySearchResponse(BaseModel):
    mode: str
    normalized_query: str
    tokens: list[str] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    contractor_key: str | None = None
    contractor_name: str | None = None
    evaluation_method: str
    can_print: bool = True
    contractor_options: list[RiskLibraryContractorOption] = Field(default_factory=list)
    designation: RiskAssessmentDesignation | None = None
    results: list[RiskLibrarySearchResultItem] = Field(default_factory=list)
