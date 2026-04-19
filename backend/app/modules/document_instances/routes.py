from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, assert_hq_safe_workspace
from app.modules.document_instances.service import (
    get_instance_history_row_by_id,
    list_instance_history_rows,
    summarize_instance_history,
)
from app.schemas.document_instance_history import (
    DocumentInstanceHistoryItem,
    DocumentInstanceHistoryListResponse,
    DocumentInstanceHistorySummaryResponse,
)

router = APIRouter(prefix="/document-instances", tags=["document-instances"])


def _require_hq_safe(current_user: CurrentUserDep) -> None:
    assert_hq_safe_workspace(current_user)


@router.get("/history", response_model=DocumentInstanceHistoryListResponse)
def get_document_instance_history(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = None,
    site_code: str | None = None,
    from_date: date | None = Query(None, description="Filter: period_start >= from_date"),
    to_date: date | None = Query(None, description="Filter: period_start <= to_date"),
    document_type_code: str | None = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    """
    DocumentInstance 기준 주기 문서 히스토리 (HQ 전용).
    Document는 instance_id로 최대 1건 연결(유일 FK).
    """
    _require_hq_safe(current_user)
    items, total = list_instance_history_rows(
        db,
        site_id=site_id,
        site_code=site_code,
        from_date=from_date,
        to_date=to_date,
        document_type_code=document_type_code,
        limit=limit,
        offset=offset,
    )
    return DocumentInstanceHistoryListResponse(
        items=[DocumentInstanceHistoryItem.model_validate(r) for r in items],
        total=total,
    )


@router.get("/history/summary", response_model=DocumentInstanceHistorySummaryResponse)
def get_document_instance_history_summary(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = None,
    site_code: str | None = None,
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    document_type_code: str | None = None,
):
    _require_hq_safe(current_user)
    data = summarize_instance_history(
        db,
        site_id=site_id,
        site_code=site_code,
        from_date=from_date,
        to_date=to_date,
        document_type_code=document_type_code,
    )
    return DocumentInstanceHistorySummaryResponse.model_validate(data)


@router.get("/{instance_id}", response_model=DocumentInstanceHistoryItem)
def get_document_instance_detail(
    instance_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """단일 DocumentInstance 스냅샷 (HQ 전용, read-only)."""
    _require_hq_safe(current_user)
    row = get_instance_history_row_by_id(db, instance_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")
    return DocumentInstanceHistoryItem.model_validate(row)
