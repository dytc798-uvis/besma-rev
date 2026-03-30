import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from app.config.settings import settings, BASE_DIR
from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, Role, require_roles
from app.modules.users.models import User
from app.modules.workers.service import (
    WorkerIngestionError,
    WorkerDiffResult,
    apply_worker_diff,
    diff_employees_from_path,
    diff_employees_from_path_with_ingestion,
    import_employees_from_path_with_ingestion,
    import_sawon_list_from_path,
)
from app.schemas.workers import (
    WorkerApplyRequest,
    WorkerApplyResponse,
    WorkerDiffItem,
    WorkerDiffResponse,
    WorkerImportResponse,
    WorkerMissingSampleItem,
)


router = APIRouter(prefix="/workers", tags=["workers"])


def _build_diff_response(diff: WorkerDiffResult, ingestion: dict | None = None) -> WorkerDiffResponse:
    items: list[WorkerDiffItem] = []
    for dto in diff.items:
        items.append(
            WorkerDiffItem(
                type=dto.type,
                person_id=dto.person_id,
                changes=dto.changes,
                name=dto.row.get("name"),
            )
        )
    missing_items: list[WorkerMissingSampleItem] = []
    sample = diff.missing_sample or []
    for m in sample:
        missing_items.append(
            WorkerMissingSampleItem(
                person_id=m.get("person_id"),
                name=m.get("name"),
                phone_mobile=m.get("phone_mobile"),
                rrn_hash=m.get("rrn_hash", ""),
            )
        )
    return WorkerDiffResponse(
        total=len(diff.items),
        new_count=len(diff.new_items),
        updated_count=len(diff.updated_items),
        unchanged_count=len(diff.unchanged_items),
        items=items,
        missing_count=diff.missing_count,
        missing_sample=missing_items,
        ingestion=ingestion,
    )


def _failure_response(
    *,
    status_code: int,
    detail: str,
    ingestion: dict | None = None,
):
    payload = {"detail": detail}
    if ingestion is not None:
        payload["ingestion"] = ingestion
    return JSONResponse(status_code=status_code, content=payload)


@router.post("/import/employees", response_model=WorkerImportResponse, status_code=status.HTTP_201_CREATED)
def import_employees(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile | None = File(None),
):
    """
    employees_raw.xlsx 포맷 파일을 Person/Employment로 import.
    baseline 생성 및 일반 import 용으로 사용한다.
    """
    if file is not None:
        path = settings.storage_root / "workers_employees_import.xlsx"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = file.file.read()
        path.write_bytes(content)
    else:
        path = BASE_DIR / "docs" / "sample" / "site_import" / "raw" / "employees_raw.xlsx"

    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Import source file not found.",
        )

    try:
        batch, ingestion = import_employees_from_path_with_ingestion(db, path)
    except WorkerIngestionError as exc:
        return _failure_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            ingestion=exc.ingestion,
        )
    return {
        "batch_id": batch.id,
        "source_type": batch.source_type,
        "original_filename": batch.original_filename,
        "total_rows": batch.total_rows,
        "created_rows": batch.created_rows,
        "updated_rows": batch.updated_rows,
        "failed_rows": batch.failed_rows,
        "warning_summary": batch.warning_summary,
        "ingestion": ingestion,
    }


@router.post("/import/sawon-list", response_model=WorkerImportResponse, status_code=status.HTTP_201_CREATED)
def import_sawon_list(
    db: DbDep,
    _current_user: Annotated[
        User,
        Depends(require_roles(Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN)),
    ],
    file: UploadFile = File(...),
):
    """
    안전보건실(HQ) 사원리스트(.xls/.xlsx) 업로드 시 Person/Employment를 upsert.
    xls 파싱 실패 시 서버에서 변환·재파싱을 시도한다.
    """
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="파일 이름이 없습니다.")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xls", ".xlsx"}:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="사원리스트는 .xls 또는 .xlsx 파일만 업로드할 수 있습니다.",
        )
    dest_dir = settings.storage_root / "sawon_uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(file.filename).stem[:80] if Path(file.filename).stem else "sawon"
    dest = dest_dir / f"{uuid.uuid4().hex}_{stem}{suffix}"
    dest.write_bytes(file.file.read())
    try:
        batch, ingestion = import_sawon_list_from_path(db, dest)
    except WorkerIngestionError as exc:
        return _failure_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            ingestion=exc.ingestion,
        )
    return {
        "batch_id": batch.id,
        "source_type": batch.source_type,
        "original_filename": batch.original_filename,
        "total_rows": batch.total_rows,
        "created_rows": batch.created_rows,
        "updated_rows": batch.updated_rows,
        "failed_rows": batch.failed_rows,
        "warning_summary": batch.warning_summary,
        "ingestion": ingestion,
    }


@router.post("/diff/employees", response_model=WorkerDiffResponse)
def diff_employees(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile | None = File(None),
):
    """
    employees_raw.xlsx 기반 baseline(DB) 대비 업로드 파일의 diff 계산.
    """
    if file is not None:
        temp_path = settings.storage_root / "tmp_workers_diff.xlsx"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        content = file.file.read()
        temp_path.write_bytes(content)
        path = temp_path
    else:
        path = BASE_DIR / "docs" / "sample" / "site_import" / "raw" / "employees_raw_v1.xlsx"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diff source file not found.",
        )
    try:
        diff, ingestion = diff_employees_from_path_with_ingestion(db, path)
    except WorkerIngestionError as exc:
        return _failure_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            ingestion=exc.ingestion,
        )
    return _build_diff_response(diff, ingestion=ingestion)


@router.post("/apply/employees", response_model=WorkerApplyResponse)
def apply_employees(
    db: DbDep,
    current_user: CurrentUserDep,
    body: WorkerApplyRequest,
):
    """
    직전 diff 기준 NEW/UPDATED 반영.
    현재 구현에서는 샘플 v2 파일(employees_raw_v2.xlsx)을 기준으로 diff를 다시 계산한 뒤 적용한다.
    """
    path = BASE_DIR / "docs" / "sample" / "site_import" / "raw" / "employees_raw_v2.xlsx"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apply source file not found.",
        )
    diff = diff_employees_from_path(db, path)
    batch = apply_worker_diff(
        db=db,
        diff=diff,
        apply_new=body.apply_new,
        apply_updated=body.apply_updated,
        source_type="employees_diff",
        original_filename=path.name,
    )
    return WorkerApplyResponse(
        total=len(diff.items),
        applied_new=batch.created_rows,
        applied_updated=batch.updated_rows,
        skipped_unchanged=len(diff.unchanged_items),
        batch_id=batch.id,
    )

