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


class DocumentExplorerListResponse(BaseModel):
    items: list[DocumentExplorerFileItem]

