from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep, assert_hq_safe_workspace
from app.modules.functional_eval import service
from app.modules.functional_eval.models import FunctionalEvalPeriod
from app.modules.functional_eval.schemas import (
    FunctionalEvalAssessmentSave,
    FunctionalEvalPeriodDeadlineUpdate,
    FunctionalEvalSanctionCreate,
)
from app.modules.functional_eval.site_grade_workbook import site_grade_export_filename

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


def _site_grade_workbook_response(content: bytes) -> StreamingResponse:
    filename = site_grade_export_filename()
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/my-site/export/site-grade-workbook")
def export_my_site_grade_workbook(db: DbDep, current_user: CurrentUserDep):
    """현장 — 템플릿 형식(1.인원현황 / 2-1 / 2-2) 엑셀 출력."""
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    try:
        content = service.build_site_grade_workbook_bytes(db, period, site_code=site_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "NO_ATTENDANCE_WORKERS":
            raise HTTPException(
                status_code=404,
                detail="출역 반영된 근로자가 없습니다. 본사에 출역일보 업로드를 요청하세요.",
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _site_grade_workbook_response(content)


@router.get("/hq/export/site-grade-workbook")
def export_hq_site_grade_workbook(
    db: DbDep,
    current_user: CurrentUserDep,
    site_code: str | None = Query(default=None),
):
    """본사 — 전 현장(또는 site_code 지정) 현장별 기능인등급 엑셀."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        content = service.build_site_grade_workbook_bytes(db, period, site_code=site_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "NO_ATTENDANCE_WORKERS":
            raise HTTPException(status_code=404, detail="출역 반영된 근로자가 없습니다.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _site_grade_workbook_response(content)


@router.get("/violation-catalog")
def get_violation_catalog(current_user: CurrentUserDep):
    return {"items": service.violation_catalog_public()}


@router.get("/eval-catalog")
def get_eval_catalog(current_user: CurrentUserDep):
    return service.eval_catalog_public()


@router.get("/workers/{worker_id}/assessment/{eval_type}")
def get_worker_assessment(
    worker_id: int,
    eval_type: str,
    db: DbDep,
    current_user: CurrentUserDep,
):
    if eval_type not in {"FUNCTIONAL", "SAFETY"}:
        raise HTTPException(status_code=400, detail="eval_type must be FUNCTIONAL or SAFETY")
    try:
        return service.get_worker_assessment(db, current_user, worker_id, eval_type)  # type: ignore[arg-type]
    except ValueError as exc:
        code = str(exc)
        if code == "WORKER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Worker not found") from exc
        if code in {"SITE_MISMATCH", "CANNOT_EVALUATE_SITE_MANAGER"}:
            raise HTTPException(status_code=403, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.put("/workers/{worker_id}/assessment/{eval_type}")
def save_worker_assessment(
    worker_id: int,
    eval_type: str,
    body: FunctionalEvalAssessmentSave,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_site_functional_eval(current_user)
    if eval_type not in {"FUNCTIONAL", "SAFETY"}:
        raise HTTPException(status_code=400, detail="eval_type must be FUNCTIONAL or SAFETY")
    try:
        result = service.save_worker_assessment(
            db, current_user, worker_id, eval_type, body.scores  # type: ignore[arg-type]
        )
    except ValueError as exc:
        code = str(exc)
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="마감일이 지나 수정할 수 없습니다.") from exc
        if code == "WORKER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Worker not found") from exc
        if code.startswith("INCOMPLETE:") or code.startswith("INVALID_GRADE:"):
            raise HTTPException(status_code=400, detail=code) from exc
        if code in {"SITE_MISMATCH", "CANNOT_EVALUATE_SITE_MANAGER", "WORKER_INACTIVE"}:
            raise HTTPException(status_code=400, detail=code) from exc
        if code in {"WORKER_NOT_ON_ATTENDANCE", "NO_ATTENDANCE_UPLOAD"}:
            raise HTTPException(status_code=400, detail="당일 출역 명단에 없거나 출역일보가 반영되지 않았습니다.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return {"assessment": result}


@router.get("/period/current")
def get_current_period(db: DbDep, current_user: CurrentUserDep):
    period = service.get_or_create_active_period(db)
    return service.serialize_period(period, db)


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
    return service.serialize_period(period, db)


@router.get("/my-site/workers")
def list_my_site_workers(db: DbDep, current_user: CurrentUserDep):
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    items = service.list_workers_for_user(db, current_user, period)
    period_payload = service.serialize_period(period, db)
    message = None
    if not period_payload.get("last_attendance_date"):
        message = "출역일보가 아직 반영되지 않았습니다. 본사에 업로드를 요청하세요."
    return {
        "period": period_payload,
        "items": items,
        "attendance_message": message,
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
        if code in {"WORKER_NOT_ON_ATTENDANCE", "NO_ATTENDANCE_UPLOAD"}:
            raise HTTPException(
                status_code=400,
                detail="당일 출역 명단에 없거나 출역일보가 반영되지 않았습니다.",
            ) from exc
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
):
    """현장별 평가 진행률 목록 (근로자 상세 미포함)."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    return service.build_hq_summary_response(
        db,
        period,
        sort_by=sort_by,
        sort_dir=sort_dir,
        site_code=site_code,
    )


@router.get("/hq/sites/{site_code}/evaluations")
def hq_site_evaluations(
    site_code: str,
    db: DbDep,
    current_user: CurrentUserDep,
    sort_by: str = Query(default="name"),
    sort_dir: str = Query(default="asc"),
):
    """현장별 평가 완료자만 (기능+안전 모두 완료)."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    return service.list_hq_site_completed_evaluations(
        db,
        period,
        site_code.strip(),
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


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
    return {"period": service.serialize_period(period, db), **result}


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
    return {"period": service.serialize_period(period, db), **result}


@router.post("/hq/site-aggregate/apply")
async def site_aggregate_apply(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """월별현장별집계 xls — 현장코드·별칭(대우청라)·소장 로그인 ID 매핑."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    tmp = await _save_upload(file, period.id)
    try:
        result = service.apply_monthly_site_aggregate_file(
            db, period, tmp, original_filename=file.filename or "site_aggregate.xls"
        )
    except ValueError as exc:
        code = str(exc)
        if code == "EMPTY_FILE":
            raise HTTPException(status_code=400, detail="파일이 비어 있습니다.") from exc
        if code == "NO_SITE_AGGREGATE_ROWS":
            raise HTTPException(status_code=400, detail="현장 집계 행을 찾을 수 없습니다.") from exc
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="마감일이 지나 반영할 수 없습니다.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return result


@router.post("/hq/attendance/apply")
async def attendance_apply(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """ERP 출역일보 xls/xlsx — 집계 반영 후 1일 1회 업로드(별칭-이름 계정·팀장 자동)."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    tmp = await _save_upload(file, period.id)
    try:
        result = service.apply_attendance_report_file(
            db, period, tmp, original_filename=file.filename or "attendance.xlsx"
        )
    except ValueError as exc:
        code = str(exc)
        if code == "EMPTY_FILE":
            raise HTTPException(status_code=400, detail="파일이 비어 있습니다.") from exc
        if code == "NO_ATTENDANCE_ROWS":
            raise HTTPException(status_code=400, detail="출역 근로자 행을 찾을 수 없습니다.") from exc
        if code == "MULTIPLE_WORK_DATES":
            raise HTTPException(status_code=400, detail="한 파일에 출역일이 여러 개입니다.") from exc
        if code == "SITE_REGISTRY_REQUIRED":
            raise HTTPException(
                status_code=400,
                detail="먼저 월별현장별집계 파일을 반영한 뒤 출역일보를 업로드하세요.",
            ) from exc
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="마감일이 지나 반영할 수 없습니다.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return result


@router.post("/hq/team-leaders/apply")
async def apply_team_leaders(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """20명 초과 현장에 팀장 계정 발급 및 팀원 배정(이하 현장은 소장이 전원 평가)."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    tmp = await _save_upload(file, period.id)
    try:
        result = service.apply_team_leader_assignments_file(db, period, tmp)
    except ValueError as exc:
        code = str(exc)
        if code == "TEAM_ASSIGNMENT_UNSUPPORTED_FILE":
            raise HTTPException(status_code=400, detail="지원 형식은 .txt/.xls/.xlsx 입니다.") from exc
        if code == "TEAM_ASSIGNMENT_HEADER_INVALID":
            raise HTTPException(status_code=400, detail="필수 컬럼(현장코드/팀장명/팀장주민번호/팀원명)을 확인하세요.") from exc
        if code in {"NO_TEAM_ASSIGNMENT_ROWS", "EMPTY_FILE"}:
            raise HTTPException(status_code=400, detail="반영 가능한 팀장/팀원 행이 없습니다.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return {"period": service.serialize_period(period, db), **result}


@router.post("/hq/import-roster")
async def import_roster_legacy(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """일용직 명부 적용 (DIFF 반영). `/hq/roster/apply` 와 동일."""
    return await roster_apply(db, current_user, file)


@router.get("/hq/export/evaluations")
def export_hq_evaluations_excel(
    db: DbDep,
    current_user: CurrentUserDep,
):
    """전체 평가 현황 엑셀 (미평가 포함, 본사 일괄 조회용)."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)

    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "평가현황"
    ws.append(
        [
            "현장코드",
            "현장명",
            "평가자(소장)",
            "성명",
            "품질등급",
            "안전등급",
            "전체완료",
            "비고",
        ]
    )
    for row in service.list_hq_eval_export_rows(db, period):
        ws.append(
            [
                row["site_code"],
                row["site_name"],
                row["evaluator_name"],
                row["name"],
                row["functional_grade"],
                row["safety_grade"],
                row["fully_complete"],
                row["remark"],
            ]
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"functional_eval_grades_{period.id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
