from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DailyWorkPlanCreateRequest(BaseModel):
    site_id: int
    work_date: date


class DailyWorkPlanItemCreateRequest(BaseModel):
    work_name: str
    work_description: str
    team_label: str | None = None
    leader_person_id: int | None = None


class RecommendRisksRequest(BaseModel):
    top_n: int = Field(default=10, ge=1, le=50)


class RecommendRisksResponse(BaseModel):
    plan_item_id: int
    recommended_count: int
    upserted_count: int


class AdoptRisksRequest(BaseModel):
    risk_revision_ids: list[int]


class AdoptRisksResponse(BaseModel):
    plan_item_id: int
    requested_count: int
    adopted_count: int


class DailyWorkPlanItemRiskRefResponse(BaseModel):
    id: int
    plan_item_id: int
    risk_item_id: int
    risk_revision_id: int
    link_type: str
    is_selected: bool
    source_rule: str
    score: float
    display_order: int
    created_at: datetime
    risk_factor: str | None = None
    countermeasure: str | None = None
    risk_r: int | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyWorkPlanItemResponse(BaseModel):
    id: int
    plan_id: int
    work_name: str
    work_description: str
    team_label: str | None = None
    leader_person_id: int | None = None
    created_at: datetime
    risk_refs: list[DailyWorkPlanItemRiskRefResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DailyWorkPlanConfirmationResponse(BaseModel):
    id: int
    plan_id: int
    confirmed_by_user_id: int
    confirmed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyWorkPlanConfirmResponse(BaseModel):
    plan_id: int
    confirmation_id: int
    created: bool


class DailyWorkPlanResponse(BaseModel):
    id: int
    site_id: int
    work_date: date
    author_user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[DailyWorkPlanItemResponse] = Field(default_factory=list)
    confirmations: list[DailyWorkPlanConfirmationResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AssembleDailyWorkPlanDocumentRequest(BaseModel):
    site_id: int
    work_date: date


class AssembleDailyWorkPlanDocumentResponse(BaseModel):
    site_id: int
    work_date: date
    document_type_code: str
    instance_id: int
    document_id: int
    document_status: str
    workflow_status: str
    plan_count: int
    item_count: int
    adopted_risk_revision_count: int
    links_upserted: int


class AssembledPlanSummary(BaseModel):
    plan_id: int
    item_count: int
    adopted_risk_revision_count: int


class GetAssembledDailyWorkPlanDocumentResponse(BaseModel):
    site_id: int
    work_date: date
    instance_id: int
    document_id: int
    document_type_code: str
    workflow_status: str
    plans: list[AssembledPlanSummary] = Field(default_factory=list)


class DailyWorkPlanDistributeRequest(BaseModel):
    plan_id: int
    target_date: date
    visible_from: datetime
    person_ids: list[int] = Field(default_factory=list)


class DailyWorkPlanDistributionWorkerResponse(BaseModel):
    id: int
    distribution_id: int
    person_id: int
    person_name: str | None = None
    employment_id: int | None = None
    access_token: str
    ack_status: str
    viewed_at: datetime | None = None
    start_signed_at: datetime | None = None
    end_signed_at: datetime | None = None
    end_status: str | None = None
    issue_flag: bool
    signed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyWorkPlanDistributionResponse(BaseModel):
    id: int
    plan_id: int
    site_id: int
    target_date: date
    visible_from: datetime
    distributed_by_user_id: int
    distributed_at: datetime
    status: str
    tbm_started_at: datetime | None = None
    tbm_started_by_user_id: int | None = None
    parent_distribution_id: int | None = None
    is_reassignment: bool = False
    reassignment_reason: str | None = None
    reassigned_by_user_id: int | None = None
    reassigned_at: datetime | None = None
    is_tbm_active: bool
    worker_count: int


class DailyWorkPlanDistributionDetailResponse(BaseModel):
    id: int
    plan_id: int
    site_id: int
    target_date: date
    visible_from: datetime
    distributed_by_user_id: int
    distributed_at: datetime
    status: str
    tbm_started_at: datetime | None = None
    tbm_started_by_user_id: int | None = None
    parent_distribution_id: int | None = None
    is_reassignment: bool = False
    reassignment_reason: str | None = None
    reassigned_by_user_id: int | None = None
    reassigned_at: datetime | None = None
    is_tbm_active: bool
    workers: list[DailyWorkPlanDistributionWorkerResponse] = Field(default_factory=list)


class StartTbmDistributionResponse(BaseModel):
    distribution_id: int
    tbm_started_at: datetime
    tbm_started_by_user_id: int
    is_tbm_active: bool


class WorkerMyDailyWorkPlanListItem(BaseModel):
    distribution_id: int
    plan_id: int
    site_id: int
    work_date: date
    visible_from: datetime
    parent_distribution_id: int | None = None
    is_reassignment: bool = False
    reassignment_reason: str | None = None
    ack_status: str
    viewed_at: datetime | None = None
    start_signed_at: datetime | None = None
    end_signed_at: datetime | None = None
    end_status: str | None = None
    issue_flag: bool
    signed_at: datetime | None = None


class WorkerRiskItem(BaseModel):
    risk_factor: str
    counterplan: str
    risk_level: int


class WorkerPlanItemDetail(BaseModel):
    plan_item_id: int | None = None
    work_name: str
    work_description: str
    team_label: str | None = None
    risks: list[WorkerRiskItem] = Field(default_factory=list)


class WorkerPlanDetail(BaseModel):
    id: int
    site_id: int
    work_date: date
    author_user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[WorkerPlanItemDetail] = Field(default_factory=list)


class WorkerMyDailyWorkPlanDetailResponse(BaseModel):
    distribution_worker_id: int
    distribution_id: int
    parent_distribution_id: int | None = None
    is_reassignment: bool = False
    reassignment_reason: str | None = None
    plan: WorkerPlanDetail
    ack_status: str
    viewed_at: datetime | None = None
    start_signed_at: datetime | None = None
    end_signed_at: datetime | None = None
    end_status: str | None = None
    issue_flag: bool
    signed_at: datetime | None = None
    is_completed: bool


class WorkerSignDailyWorkPlanRequest(BaseModel):
    access_token: str | None = None
    signature_data: str
    signature_mime: str
    lat: float
    lng: float


class WorkerSignDailyWorkPlanResponse(BaseModel):
    distribution_worker_id: int
    distribution_id: int
    ack_status: str
    viewed_at: datetime | None = None
    start_signed_at: datetime | None = None
    end_signed_at: datetime | None = None
    end_status: str | None = None
    issue_flag: bool
    signed_at: datetime | None = None
    signature_hash: str
    message: str | None = None


class WorkerSignEndDailyWorkPlanRequest(BaseModel):
    access_token: str | None = None
    end_status: str
    signature_data: str
    signature_mime: str
    lat: float
    lng: float


class SiteAdminPresencePingRequest(BaseModel):
    site_id: int
    lat: float | None = None
    lng: float | None = None


class SiteAdminPresencePingResponse(BaseModel):
    site_id: int
    user_id: int
    last_seen_at: datetime


class WorkerFeedbackCreateRequest(BaseModel):
    access_token: str | None = None
    feedback_type: str = Field(default="risk", min_length=1, max_length=20)
    content: str = Field(min_length=1, max_length=5000)
    plan_item_id: int | None = None


class WorkerFeedbackResponse(BaseModel):
    id: int
    distribution_id: int
    distribution_worker_id: int
    person_id: int
    person_name: str | None = None
    plan_id: int
    plan_item_id: int | None = None
    feedback_type: str
    content: str
    status: str
    created_at: datetime
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    candidate_id: int | None = None
    candidate_status: str | None = None


class FeedbackReviewRequest(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    review_note: str | None = Field(default=None, max_length=2000)


class FeedbackReviewResponse(BaseModel):
    feedback_id: int
    status: str
    reviewed_by_user_id: int
    reviewed_at: datetime
    review_note: str | None = None


class FeedbackPromoteCandidateResponse(BaseModel):
    feedback_id: int
    candidate_id: int
    status: str
    inferred_unit_work: str | None = None
    inferred_process: str | None = None
    inferred_risk_factor: str | None = None
    inferred_countermeasure: str | None = None
    created_at: datetime


class DistributionReassignWorkersRequest(BaseModel):
    person_ids: list[int] = Field(default_factory=list)
    new_work_name: str = Field(min_length=1, max_length=255)
    new_work_description: str = Field(min_length=1, max_length=5000)
    team_label: str | None = Field(default=None, max_length=100)
    selected_risk_revision_ids: list[int] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=2000)


class DistributionReassignWorkersResponse(BaseModel):
    source_distribution_id: int
    reassignment_distribution_id: int
    reassignment_plan_id: int
    worker_count: int
    is_reassignment: bool
    reassignment_reason: str


class SafetyRecordRiskItem(BaseModel):
    risk_revision_id: int
    risk_factor: str
    counterplan: str
    risk_level: int


class SafetyRecordPlanItem(BaseModel):
    plan_item_id: int
    work_name: str
    work_description: str
    team_label: str | None = None
    risks: list[SafetyRecordRiskItem] = Field(default_factory=list)


class SafetyRecordDistributionEntry(BaseModel):
    distribution_id: int
    parent_distribution_id: int | None = None
    is_reassignment: bool
    reassignment_reason: str | None = None
    target_date: date
    visible_from: datetime
    distributed_at: datetime
    ack_status: str
    viewed_at: datetime | None = None
    start_signed_at: datetime | None = None
    end_signed_at: datetime | None = None
    end_status: str | None = None
    issue_flag: bool
    items: list[SafetyRecordPlanItem] = Field(default_factory=list)


class SafetyRecordPersonSummary(BaseModel):
    person_id: int
    name: str
    phone_mobile: str | None = None
    site_id: int | None = None
    site_name: str | None = None
    employment_id: int | None = None
    department_name: str | None = None
    position_name: str | None = None


class WorkerSafetyRecordResponse(BaseModel):
    person: SafetyRecordPersonSummary
    distributions: list[SafetyRecordDistributionEntry] = Field(default_factory=list)
    feedbacks: list[WorkerFeedbackResponse] = Field(default_factory=list)
