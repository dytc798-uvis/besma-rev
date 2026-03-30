from datetime import date, datetime

from pydantic import BaseModel, Field


class DocumentContentRisk(BaseModel):
    risk_revision_id: int
    risk_item_id: int
    risk_factor: str
    counterplan: str
    frequency: int
    severity: int
    risk_level: int


class DocumentContentItem(BaseModel):
    work_name: str
    work_description: str
    team_label: str | None = None
    leader_person_id: int | None = None
    risks: list[DocumentContentRisk] = Field(default_factory=list)


class DocumentContentPlan(BaseModel):
    plan_id: int
    site_id: int
    work_date: date
    author_user_id: int
    items: list[DocumentContentItem] = Field(default_factory=list)


class DocumentContentResponse(BaseModel):
    document_id: int
    instance_id: int
    site_id: int
    work_date: date
    plans: list[DocumentContentPlan] = Field(default_factory=list)


class TbmTableRow(BaseModel):
    work_description: str | None = None
    risk_factor: str
    counterplan: str
    risk_level: int | None = None


class TbmTopRisk(BaseModel):
    risk_revision_id: int
    risk_item_id: int
    risk_factor: str
    counterplan: str
    frequency: int
    severity: int
    risk_level: int


class TbmParticipant(BaseModel):
    person_id: int
    name: str
    ack_status: str
    start_signed_at: datetime | None = None
    end_signed_at: datetime | None = None
    end_status: str | None = None
    issue_flag: bool
    start_signature_data: str | None = None
    end_signature_data: str | None = None


class TbmSummaryResponse(BaseModel):
    document_id: int
    instance_id: int
    site_id: int
    site_name: str | None = None
    work_date: date
    tbm_leader_name: str | None = None
    education_count: int
    table_rows: list[TbmTableRow] = Field(default_factory=list)
    top_risks: list[TbmTopRisk] = Field(default_factory=list)
    participants: list[TbmParticipant] = Field(default_factory=list)
