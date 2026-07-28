from __future__ import annotations

from pydantic import BaseModel


class DocumentExplorerFileItem(BaseModel):
    id: str
    name: str
    relative_path: str
    modified_at: str
    size_bytes: int
    extension: str
    category: str
    relevance: float = 0.0
    snippet: str | None = None
    match_source: str | None = None
    index_status: str | None = None


class DocumentExplorerListResponse(BaseModel):
    items: list[DocumentExplorerFileItem]

