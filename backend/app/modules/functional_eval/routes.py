from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep, assert_hq_safe_workspace
from app.modules.functional_eval import service
from app.modules.functional_eval.models import FunctionalEvalPeriod
from app.modules.functional_eval.schemas import (
    FunctionalEvalPeriodDeadlineUpdate,
    FunctionalEvalSanctionCreate,
)

router = APIRouter(prefix="/functional-eval", tags=["functional-eval"])


def _role_value(user) -> str:
    role = getattr(user, "role", "")
    return role.value if hasattr(role, "value") else str(role)


def _assert_site_functional_eval(user) -> None:
    if _role_value(user) != Role.SITE_FUNCTIONAL_EVAL.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SITE_FUNCTIONAL_EVAL only")


async def _save_upload(file: UploadFile, period_id: int) -> Path:
    suffix = Path(file.filename or "roster.xlsx").suffix or ".xlsx"
    tmp = Path("storage/functional_eval") / f"import_{period_id}_{date.today().isoformat()}_{uuid.uuid4().hex[:8]}{suffix}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    tmp.write_bytes(content)
    return tmp


@router.get("/violation-catalog")
def get_violation_catalog(current_user: CurrentUserDep):
    return {"items": service.violation_catalog_public()}


@router.get("/period/current")
def get_current_period(db: DbDep, current_user: CurrentUserDep):
    period = service.get_or_create_active_period(db)
    return service.serialize_period(period)


@router.patch("/period/{period_id}/deadline")
def update_period_deadline(
    period_id: int,
    body: FunctionalEvalPeriodDeadlineUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
):
    assert_hq_safe_workspace(current_user)
    period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.id == period_id).first()
    if period is None:
        raise HTTPException(status_code=404, detail="Period not found")
    period.deadline_date = body.deadline_date
    db.add(period)
    db.commit()
    db.refresh(period)
    return service.serialize_period(period)


@router.get("/my-site/workers")
def list_my_site_workers(db: DbDep, current_user: CurrentUserDep):
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    return {
        "period": service.serialize_period(period),
        "items": service.list_workers_for_user(db, current_user, period),
    }


@router.get("/workers/{worker_id}/history")
def worker_history(worker_id: int, db: DbDep, current_user: CurrentUserDep):
    if _role_value(current_user) not in {
        Role.SITE_FUNCTIONAL_EVAL.value,
        Role.HQ_SAFE.value,
        Role.HQ_SAFE_ADMIN.value,
        Role.SUPER_ADMIN.value,
        Role.ACCIDENT_ADMIN.value,
    }:
        raise HTTPException(status_code=403, detail="Not allowed")
    try:
        return service.get_worker_history(db, current_user, worker_id)
    except ValueError as exc:
        if str(exc) == "WORKER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Worker not found") from exc
        if str(exc) == "SITE_MISMATCH":
            raise HTTPException(status_code=403, detail="Not allowed for this site") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workers/{worker_id}/mileage")
def worker_mileage_placeholder(worker_id: int, db: DbDep, current_user: CurrentUserDep):
    """우수 의견 마일리지 — 운영 준비용 API (적립 로직 미구현)."""
    from app.modules.functional_eval.models import FunctionalEvalWorker

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    try:
        service._assert_worker_access(current_user, worker)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return service.serialize_mileage_placeholder(worker)


@router.post("/sanctions")
def create_sanction(body: FunctionalEvalSanctionCreate, db: DbDep, current_user: CurrentUserDep):
    if _role_value(current_user) not in {
        Role.SITE_FUNCTIONAL_EVAL.value,
        Role.HQ_SAFE.value,
        Role.HQ_SAFE_ADMIN.value,
        Role.SUPER_ADMIN.value,
    }:
        raise HTTPException(status_code=403, detail="Not allowed")
    period = service.get_or_create_active_period(db)
    try:
        row = service.record_sanction(
            db,
            period=period,
            user=current_user,
            worker_id=body.worker_id,
            violation_code=body.violation_code,
            note=body.note,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="마감일이 지나 수정할 수 없습니다.") from exc
        if code in {"WORKER_NOT_FOUND", "SITE_MISMATCH", "CANNOT_SANCTION_SITE_MANAGER", "WORKER_INACTIVE"}:
            raise HTTPException(status_code=400, detail=code) from exc
        if code == "UNKNOWN_VIOLATION":
            raise HTTPException(status_code=400, detail="알 수 없는 위반 항목입니다.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return row


@router.get("/hq/summary")
def hq_summary(
    db: DbDep,
    current_user: CurrentUserDep,
    sort_by: str = Query(default="site_code"),
    sort_dir: str = Query(default="asc"),
    site_code: str | None = Query(default=None),
    sanction_status: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
):
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    items = service.list_hq_summary(
        db,
        period,
        sort_by=sort_by,
        sort_dir=sort_dir,
        site_code=site_code,
        sanction_status=sanction_status,
        include_inactive=include_inactive,
    )
    return {
        "period": service.serialize_period(period),
        "items": items,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }


@router.post("/hq/roster/diff")
async def roster_diff(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    tmp = await _save_upload(file, period.id)
    try:
        result = service.diff_daily_roster_file(db, period, tmp)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"period": service.serialize_period(period), **result}


@router.post("/hq/roster/apply")
async def roster_apply(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    tmp = await _save_upload(file, period.id)
    try:
        result = service.apply_daily_roster_file(
            db, period, tmp, original_filename=file.filename or "roster.xlsx"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"period": service.serialize_period(period), **result}


@router.post("/hq/import-roster")
async def import_roster_legacy(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """일용직 명부 적용 (DIFF 반영). `/hq/roster/apply` 와 동일."""
    return await roster_apply(db, current_user, file)


@router.get("/hq/export")
def export_hq_excel(
    db: DbDep,
    current_user: CurrentUserDep,
    sort_by: str = Query(default="site_code"),
    sort_dir: str = Query(default="asc"),
):
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    if not service.period_is_closed(period):
        raise HTTPException(status_code=409, detail="마감 후에만 다운로드할 수 있습니다.")

    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "제재현황"
    ws.append(
        [
            "현장코드",
            "성명",
            "명부상태",
            "제재상태",
            "위반항목",
            "제재결과",
            "누적차수",
            "비고",
            "등록일시",
        ]
    )
    items = service.list_hq_summary(db, period, sort_by=sort_by, sort_dir=sort_dir, include_inactive=True)
    for item in items:
        worker = item["worker"]
        sanctions = item["sanctions"]
        active_label = "재직" if worker.get("is_active") else "명부제외"
        if not sanctions:
            ws.append(
                [
                    worker["site_code"],
                    worker["name"],
                    active_label,
                    worker.get("sanction_status_label") or "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        for s in sanctions:
            ws.append(
                [
                    worker["site_code"],
                    worker["name"],
                    active_label,
                    worker.get("sanction_status_label") or "",
                    s.get("violation_label") or "",
                    s.get("sanction_result_label") or "",
                    s.get("strike_number") or "",
                    s.get("note") or "",
                    str(s.get("created_at") or ""),
                ]
            )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"functional_eval_sanctions_{period.id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
