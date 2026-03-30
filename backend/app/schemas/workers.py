from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class WorkerDiffItem(BaseModel):
    type: Literal["NEW", "UPDATED", "UNCHANGED"]
    person_id: int | None = None
    changes: dict[str, tuple[Any, Any]] | None = None
    name: str | None = None


class WorkerMissingSampleItem(BaseModel):
    person_id: int | None = None
    name: str | None = None
    phone_mobile: str | None = None
    rrn_hash: str


class WorkerIngestionFailure(BaseModel):
    stage: str
    parser: str
    message: str


class WorkerIngestionDiagnostics(BaseModel):
    detected_type: str | None = None
    selected_parser: str | None = None
    normalized_file_created: bool = False
    normalized_filename: str | None = None
    header_valid: bool = False
    row_count: int = 0
    warnings: list[str]
    failures: list[WorkerIngestionFailure]


class WorkerDiffResponse(BaseModel):
    total: int
    new_count: int
    updated_count: int
    unchanged_count: int
    items: list[WorkerDiffItem]
    missing_count: int
    missing_sample: list[WorkerMissingSampleItem]
    ingestion: WorkerIngestionDiagnostics | None = None


class WorkerImportResponse(BaseModel):
    batch_id: int
    source_type: str
    original_filename: str
    total_rows: int
    created_rows: int
    updated_rows: int
    failed_rows: int
    warning_summary: str | None = None
    # 파서/변환 진단은 엔드포인트마다 필드가 달라 dict로 통일
    ingestion: dict[str, Any] | None = None


class WorkerApplyRequest(BaseModel):
    apply_new: bool = True
    apply_updated: bool = True


class WorkerApplyResponse(BaseModel):
    total: int
    applied_new: int
    applied_updated: int
    skipped_unchanged: int
    batch_id: int | None = None

