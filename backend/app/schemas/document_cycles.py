from datetime import date, datetime

from pydantic import BaseModel


class SubmissionCycleRead(BaseModel):
    id: int
    code: str
    name: str
    sort_order: int
    is_active: bool
    is_auto_generatable: bool

    class Config:
        from_attributes = True


class DocumentTypeMasterBase(BaseModel):
    code: str
    name: str
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True

    default_cycle_id: int
    generation_rule: str | None = None
    generation_value: str | None = None
    due_offset_days: int | None = None
    is_required_default: bool = True


class DocumentTypeMasterCreate(DocumentTypeMasterBase):
    pass


class DocumentTypeMasterUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    default_cycle_id: int | None = None
    generation_rule: str | None = None
    generation_value: str | None = None
    due_offset_days: int | None = None
    is_required_default: bool | None = None


class DocumentTypeMasterRead(DocumentTypeMasterBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DocumentRequirementRead(BaseModel):
    id: int
    site_id: int
    document_type_id: int
    is_enabled: bool
    code: str
    title: str
    frequency: str
    is_required: bool
    display_order: int
    due_rule_text: str | None = None
    note: str | None = None
    override_cycle_id: int | None = None
    override_generation_rule: str | None = None
    override_generation_value: str | None = None
    override_due_offset_days: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class DocumentRequirementUpsert(BaseModel):
    document_type_id: int
    is_enabled: bool = True
    code: str | None = None
    title: str | None = None
    frequency: str = "MONTHLY"
    is_required: bool = True
    display_order: int = 0
    due_rule_text: str | None = None
    note: str | None = None
    override_cycle_id: int | None = None
    override_generation_rule: str | None = None
    override_generation_value: str | None = None
    override_due_offset_days: int | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class ContractorBundleItemUpsert(BaseModel):
    """
    도급사그룹(삼성/일반)별 문서항목 묶음 override.

    MVP 기준: is_requiredDefault(문서유형 마스터의 is_required_default) 자체는
    site 요구사항과 동일한 방식으로 저장/표시하며, status 계산은 override 값을 그대로 사용한다.
    """

    document_type_id: int
    is_enabled: bool
    is_required: bool
    frequency: str
    display_order: int
    due_rule_text: str | None = None
    note: str | None = None


class ContractorBundleItemRead(BaseModel):
    # 대표 사이트(base) 기준 값(override가 없을 때의 기준)
    base_is_enabled: bool
    base_is_required: bool
    base_frequency: str
    base_display_order: int
    base_due_rule_text: str | None = None
    base_note: str | None = None

    # override 적용 후의 실효 값
    document_type_id: int
    code: str
    title: str
    is_enabled: bool
    is_required: bool
    frequency: str
    display_order: int
    due_rule_text: str | None = None
    note: str | None = None
    has_override: bool = False

    class Config:
        from_attributes = True


class GenerateSubmissionsRequest(BaseModel):
    site_id: int
    as_of: date
    dry_run: bool = True

