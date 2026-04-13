from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OpinionCreate(BaseModel):
    site_id: int | None = None
    category: str
    content: str
    reporter_type: str


class OpinionUpdate(BaseModel):
    status: str | None = None
    score_appropriateness: int | None = None
    score_actionability: int | None = None
    action_result: str | None = None
    assigned_user_id: int | None = None


class OpinionOut(BaseModel):
    """API response for opinions; always includes created_by_user_id for author delete UI."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    site_id: int
    category: str
    content: str
    reporter_type: str
    status: str
    score_appropriateness: int | None = None
    score_actionability: int | None = None
    assigned_user_id: int | None = None
    created_by_user_id: int | None = None
    action_result: str | None = None
    action_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
