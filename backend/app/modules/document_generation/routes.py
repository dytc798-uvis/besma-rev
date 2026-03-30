from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from fastapi import Query

from app.core.auth import DbDep
from app.modules.document_generation.service import orchestrate_document_generation
from app.modules.document_generation.models import DocumentInstance
from app.modules.document_settings.models import DocumentTypeMaster
from app.modules.document_settings.routes import require_cycle_admin
from app.schemas.document_cycles import GenerateSubmissionsRequest
from app.schemas.document_generation import BackfillRequest, DocumentInstanceRead


router = APIRouter(prefix="/document-submissions", tags=["document-submissions"])


@router.post("/generate")
def generate_document_submissions(
    payload: GenerateSubmissionsRequest,
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    """
    MVP 규칙:
    - policy 결정은 document_settings.service
    - slot/due 계산은 document_generation.engine
    - 실제 생성 orchestration은 document_generation.service
    """
    created = []
    skipped = []

    types = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.is_active == True).all()  # noqa: E712
    for dt in types:
        status, result = orchestrate_document_generation(
            db=db,
            site_id=payload.site_id,
            document_type_code=dt.code,
            as_of_date=payload.as_of,
            dry_run=payload.dry_run,
            retry_failed=False,
            reevaluate_skipped=False,
        )
        if status == "created":
            created.append(result)
        else:
            skipped.append(result)

    return {"dry_run": payload.dry_run, "created": created, "skipped": skipped}


@router.get("/instances", response_model=list[DocumentInstanceRead])
def list_document_instances(
    db: DbDep,
    __=Depends(require_cycle_admin),
    site_id: int | None = None,
    status: str | None = None,
    status_reason: str | None = None,
    period_basis: str | None = None,
    document_type_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 200,
):
    q = db.query(DocumentInstance)
    if site_id is not None:
        q = q.filter(DocumentInstance.site_id == site_id)
    if status is not None:
        q = q.filter(DocumentInstance.status == status)
    if status_reason is not None:
        q = q.filter(DocumentInstance.status_reason == status_reason)
    if period_basis is not None:
        q = q.filter(DocumentInstance.period_basis == period_basis)
    if document_type_code is not None:
        q = q.filter(DocumentInstance.document_type_code == document_type_code)

    # 간단 필터: period_start 기준 범위
    if from_date is not None:
        q = q.filter(DocumentInstance.period_start >= from_date)
    if to_date is not None:
        q = q.filter(DocumentInstance.period_start <= to_date)

    return q.order_by(DocumentInstance.period_start.desc(), DocumentInstance.id.desc()).limit(limit).all()


@router.post("/backfill")
def backfill_document_instances(
    payload: BackfillRequest,
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    """
    기간 범위 backfill / 재실행 엔드포인트.
    - cron은 daily run으로 유지하고, 운영 보정(정책 수정/누락 백필/실패 재시도)을 수동으로 수행한다.
    - 범위는 일 단위로 순회하며 idempotency(DocumentInstance 유니크키)로 중복을 흡수한다.
    """
    created = []
    skipped = []
    failed = []
    summary = {
        "created": 0,
        "failed": 0,
        "skipped": 0,
        "already_generated": 0,
        "already_pending": 0,
        "failed_no_retry": 0,
        "skipped_no_reeval": 0,
        "duplicate_auto_document": 0,
    }

    if payload.document_type_codes:
        types = (
            db.query(DocumentTypeMaster)
            .filter(DocumentTypeMaster.code.in_(payload.document_type_codes))
            .all()
        )
    else:
        types = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.is_active == True).all()  # noqa: E712

    d = payload.start_date
    while d <= payload.end_date:
        for dt in types:
            status, result = orchestrate_document_generation(
                db=db,
                site_id=payload.site_id,
                document_type_code=dt.code,
                as_of_date=d,
                dry_run=payload.dry_run,
                retry_failed=payload.retry_failed,
                reevaluate_skipped=payload.reevaluate_skipped,
            )
            if status == "created":
                created.append(result)
                summary["created"] += 1
            elif status == "failed":
                failed.append(result)
                summary["failed"] += 1
            else:
                skipped.append(result)
                summary["skipped"] += 1
                reason = result.get("reason")
                if reason in summary:
                    summary[reason] += 1
        d = d + timedelta(days=1)

    return {
        "dry_run": payload.dry_run,
        "summary": summary,
        "created": created,
        "failed": failed,
        "skipped": skipped,
    }
