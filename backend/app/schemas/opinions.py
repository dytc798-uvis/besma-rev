from pydantic import BaseModel


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

