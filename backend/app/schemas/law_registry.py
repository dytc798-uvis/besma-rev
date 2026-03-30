from __future__ import annotations

from pydantic import BaseModel, Field


class LawSearchResultItem(BaseModel):
    law_master_id: int
    law_name: str
    law_type: str
    article_item_id: int
    article_display: str | None = None
    summary_title: str | None = None
    action_required: str | None = None
    countermeasure: str | None = None
    penalty: str | None = None
    department: str | None = None
    risk_tags: list[str] = Field(default_factory=list)
    work_type_tags: list[str] = Field(default_factory=list)
    document_tags: list[str] = Field(default_factory=list)
    relevance: float = 0.0


class LawSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[LawSearchResultItem] = Field(default_factory=list)
