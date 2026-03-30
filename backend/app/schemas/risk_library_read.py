from pydantic import BaseModel, Field


class RiskLibraryReadItem(BaseModel):
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


class RiskLibraryReadResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[RiskLibraryReadItem] = Field(default_factory=list)
