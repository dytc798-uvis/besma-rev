from pydantic import BaseModel, Field


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
    results: list[RiskLibrarySearchResultItem] = Field(default_factory=list)
