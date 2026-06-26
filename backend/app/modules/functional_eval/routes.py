from __future__ import annotations

import io
import uuid
from datetime import date
from pathlib import Path

from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import (
    CurrentUserDep,
    assert_fe_hq_admin,
    assert_fe_hq_read,
    assert_fe_hq_monitoring,
    assert_hq_safe_workspace,
)
from app.modules.functional_eval import approval_workflow, service, signature_ops
from app.modules.functional_eval.constants import (
    APPROVAL_STATUS_HQ_OFFICER_APPROVED,
    APPROVAL_STATUS_SITE_APPROVED,
)
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalWorker
from app.modules.functional_eval.schemas import (
    FunctionalEvalApprovalReject,
    FunctionalEvalAssessmentSave,
    FunctionalEvalConsentSubmit,
    FunctionalEvalCustomerRewardApprove,
    FunctionalEvalCustomerRewardReject,
    FunctionalEvalHqAssessmentOverride,
    FunctionalEvalHqApprovalSubmit,
    FunctionalEvalHqDirectorApprovalSubmit,
    FunctionalEvalHqOfficerApprovalSubmit,
    FunctionalEvalPeriodDeadlineUpdate,
    FunctionalEvalSanctionCreate,
    FunctionalEvalSignatureSubmit,
    FunctionalEvalTeamReportReject,
)
from app.modules.functional_eval.sanctions import DEFAULT_SANCTION_VIOLATION_CODE
from app.modules.functional_eval import customer_rewards as reward_service
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
    """?꾩옣 ???쒗뵆由??뺤떇(1.?몄썝?꾪솴 / 2-1 / 2-2) ?묒? 異쒕젰."""
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
                detail="異쒖뿭 諛섏쁺??洹쇰줈?먭? ?놁뒿?덈떎. 蹂몄궗??異쒖뿭?쇰낫 ?낅줈?쒕? ?붿껌?섏꽭??",
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _site_grade_workbook_response(content)


@router.get("/hq/export/site-grade-workbook")
def export_hq_site_grade_workbook(
    db: DbDep,
    current_user: CurrentUserDep,
    site_code: str | None = Query(default=None),
):
    """蹂몄궗 ?????꾩옣(?먮뒗 site_code 吏?? ?꾩옣蹂?湲곕뒫?몃벑湲??묒?."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        content = service.build_site_grade_workbook_bytes(db, period, site_code=site_code)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "NO_ATTENDANCE_WORKERS":
            raise HTTPException(status_code=404, detail="異쒖뿭 諛섏쁺??洹쇰줈?먭? ?놁뒿?덈떎.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _site_grade_workbook_response(content)


@router.get("/violation-catalog")
def get_violation_catalog(current_user: CurrentUserDep):
    return {
        "items": service.violation_catalog_public(),
        "default_violation_code": DEFAULT_SANCTION_VIOLATION_CODE,
    }


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
        if code in {"SITE_MISMATCH", "CANNOT_EVALUATE_SITE_MANAGER", "CANNOT_EVALUATE_SELF"}:
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
        if code == "EVAL_NOT_OPEN":
            raise HTTPException(
                status_code=403,
                detail="평가는 2026년 6월 16일 오전 6시부터 가능합니다. 오늘은 아이디/비밀번호 변경만 이용해 주세요.",
            ) from exc
        if code == "WORKER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Worker not found") from exc
        if code.startswith("INCOMPLETE:") or code.startswith("INVALID_GRADE:"):
            raise HTTPException(status_code=400, detail=code) from exc
        if code in {"SITE_MISMATCH", "CANNOT_EVALUATE_SITE_MANAGER", "CANNOT_EVALUATE_SELF", "WORKER_INACTIVE"}:
            raise HTTPException(status_code=400, detail=code) from exc
        if code == "MANAGER_CANNOT_EDIT_TEAM_SCORES":
            raise HTTPException(status_code=403, detail="소장은 팀장 담당 근로자의 점수를 수정할 수 없습니다. 반려만 가능합니다.") from exc
        if code in {"WORKER_NOT_ON_ATTENDANCE", "NO_ATTENDANCE_UPLOAD"}:
            raise HTTPException(status_code=400, detail="당일 출역 명단에 없거나 출역일보가 반영되지 않았습니다.") from exc
        if code == "SITE_APPROVAL_LOCKED":
            raise HTTPException(status_code=409, detail="승인 진행 중인 평가는 수정할 수 없습니다.") from exc
        if code == "EVALUATION_SIGNATURE_LOCKED":
            raise HTTPException(status_code=409, detail="서명 완료 후에는 평가를 수정할 수 없습니다.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return {"assessment": result}


@router.put("/hq/workers/{worker_id}/assessment/{eval_type}")
def save_hq_assessment_override(
    worker_id: int,
    eval_type: str,
    body: FunctionalEvalHqAssessmentOverride,
    db: DbDep,
    current_user: CurrentUserDep,
):
    assert_hq_safe_workspace(current_user)
    if eval_type not in {"FUNCTIONAL", "SAFETY"}:
        raise HTTPException(status_code=400, detail="eval_type must be FUNCTIONAL or SAFETY")
    try:
        result = service.save_hq_assessment_override(
            db,
            current_user,
            worker_id,
            eval_type,  # type: ignore[arg-type]
            body.scores,
            body.reason,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="마감일이 지나 수정할 수 없습니다.") from exc
        if code == "EVAL_NOT_OPEN":
            raise HTTPException(
                status_code=403,
                detail="평가는 2026년 6월 16일 오전 6시부터 가능합니다. 오늘은 아이디/비밀번호 변경만 이용해 주세요.",
            ) from exc
        if code == "WORKER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Worker not found") from exc
        if code in {"REVISION_REASON_REQUIRED"}:
            raise HTTPException(status_code=400, detail="수정 사유를 입력하세요.") from exc
        if code.startswith("INCOMPLETE:") or code.startswith("INVALID_GRADE:"):
            raise HTTPException(status_code=400, detail=code) from exc
        if code in {"CANNOT_EVALUATE_SITE_MANAGER", "HQ_ONLY"}:
            raise HTTPException(status_code=400, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return result


@router.get("/workers/{worker_id}/assessment-revisions")
def worker_assessment_revisions(worker_id: int, db: DbDep, current_user: CurrentUserDep):
    if _role_value(current_user) not in {
        Role.SITE_FUNCTIONAL_EVAL.value,
        Role.HQ_SAFE.value,
        Role.HQ_SAFE_ADMIN.value,
        Role.SUPER_ADMIN.value,
        Role.ACCIDENT_ADMIN.value,
    }:
        raise HTTPException(status_code=403, detail="Not allowed")
    try:
        items = service.list_worker_assessment_revisions(db, current_user, worker_id)
    except ValueError as exc:
        if str(exc) == "WORKER_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Worker not found") from exc
        if str(exc) == "SITE_MISMATCH":
            raise HTTPException(status_code=403, detail="Not allowed for this site") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"items": items}


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
        message = "異쒖뿭?쇰낫媛 ?꾩쭅 諛섏쁺?섏? ?딆븯?듬땲?? 蹂몄궗???낅줈?쒕? ?붿껌?섏꽭??"
    site_code = service._site_code_for_user(current_user, db)
    site_overview = service.list_site_overview_for_manager(db, current_user, period)
    approval = service.build_site_approval_payload(db, period, site_code)
    signoff = signature_ops.build_signoff_payload_for_session(db, current_user, period, site_code, approval)
    approval = {**approval, **signoff}
    team_signoff = None
    if _role_value(current_user) == Role.SITE_FUNCTIONAL_EVAL.value:
        if not service._is_primary_site_evaluator(db, current_user, site_code):
            try:
                team_signoff = signature_ops.get_team_signoff_status(db, current_user, period)
            except ValueError:
                team_signoff = None
    return {
        "period": period_payload,
        "items": items,
        "site_overview": site_overview,
        "approval": approval,
        "team_signoff": team_signoff,
        "evaluator": service.serialize_evaluator_session(db, current_user, period),
        "attendance_message": message,
        "signatures": signature_ops.list_my_signatures(db, current_user, period),
    }


def _signature_error(code: str) -> HTTPException:
    mapping = {
        "CONSENT_REQUIRED": (403, "기능인인정제 이용 전 동의서 서명이 필요합니다."),
        "CONSENT_ACK_REQUIRED": (400, "동의서 확인 체크가 필요합니다."),
        "CONSENT_SCROLL_REQUIRED": (400, "동의서 내용을 끝까지 확인해야 합니다."),
        "CONSENT_ALREADY_SIGNED": (409, "이미 동의서에 서명했습니다."),
        "PASSWORD_CHANGE_REQUIRED": (400, "동의서 서명과 함께 비밀번호 변경이 필요합니다."),
        "CURRENT_PASSWORD_INCORRECT": (400, "현재 비밀번호가 일치하지 않습니다."),
        "NEW_PASSWORD_CONFIRM_MISMATCH": (400, "새 비밀번호 확인이 일치하지 않습니다."),
        "signature_required": (400, "서명을 입력해 주세요."),
        "signature_too_small": (400, "서명이 너무 작습니다."),
        "invalid_signature_base64": (400, "서명 이미지 형식이 올바르지 않습니다."),
        "SIGNATURE_ALREADY_EXISTS": (409, "이미 서명이 완료되었습니다."),
        "EVALUATION_SIGNATURE_LOCKED": (409, "서명 완료 후에는 평가를 수정할 수 없습니다."),
        "TEAM_LEADERS_NOT_SIGNED": (400, "모든 팀장의 평가 완료 서명이 필요합니다."),
        "TEAM_REPORTS_NOT_MANAGER_APPROVED": (400, "모든 팀장 평가 완료보고서에 소장 승인이 필요합니다."),
        "TEAM_LEADER_NOT_SIGNED": (400, "팀장 평가 완료 서명이 필요합니다."),
        "NO_PENDING_APPROVALS": (400, "승인 대기 항목이 없습니다."),
        "HQ_APPROVAL_NOT_OPEN_UNTIL_DEADLINE": (403, "본사 승인은 평가 마감일부터 가능합니다."),
        "NO_SUPPLEMENTAL_BATCH": (400, "추가 평가 대상이 없습니다."),
        "MANAGER_NOT_TEAM_LEADER": (403, "팀장만 사용할 수 있습니다."),
        "MANAGER_ONLY": (403, "소장만 사용할 수 있습니다."),
        "S_GRADE_OVER_LIMIT_REASON_REQUIRED": (400, "S등급 권장 기준(20%) 초과 사유를 10자 이상 입력해 주세요."),
        "EVAL_NOT_OPEN": (403, "평가는 2026년 6월 16일 오전 6시부터 가능합니다. 오늘은 아이디/비밀번호 변경만 이용해 주세요."),
    }
    status_code, detail = mapping.get(code, (400, code))
    return HTTPException(status_code=status_code, detail=detail)


@router.get("/consent/status")
def get_consent_status(db: DbDep, current_user: CurrentUserDep):
    return signature_ops.get_consent_status(db, current_user)


@router.post("/consent/submit")
def submit_consent(body: FunctionalEvalConsentSubmit, request: Request, db: DbDep, current_user: CurrentUserDep):
    try:
        password_fields = [body.current_password, body.new_password, body.new_password_confirm]
        wants_password_change = any(v is not None for v in password_fields)
        if getattr(current_user, "must_change_password", False) and not wants_password_change:
            raise ValueError("PASSWORD_CHANGE_REQUIRED")
        if wants_password_change:
            if not body.current_password or not body.new_password or not body.new_password_confirm:
                raise ValueError("PASSWORD_CHANGE_REQUIRED")
            if not verify_password(body.current_password, current_user.password_hash):
                raise ValueError("CURRENT_PASSWORD_INCORRECT")
            if body.new_password != body.new_password_confirm:
                raise ValueError("NEW_PASSWORD_CONFIRM_MISMATCH")
            try:
                validate_password_policy(body.new_password)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            current_user.password_hash = get_password_hash(body.new_password.strip())
            current_user.must_change_password = False
            current_user.password_changed_at = utc_now()
            db.add(current_user)
        return signature_ops.submit_consent(
            db,
            current_user,
            signature_data=body.signature_data,
            consent_acknowledged=body.consent_acknowledged,
            read_to_bottom_confirmed=body.read_to_bottom_confirmed,
            read_completed_at=body.read_completed_at,
            request=request,
        )
    except ValueError as exc:
        raise _signature_error(str(exc)) from exc


@router.get("/consent/document")
def download_consent_document(db: DbDep, current_user: CurrentUserDep):
    try:
        path = signature_ops.get_consent_document_path(db, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="?숈쓽??臾몄꽌瑜?李얠쓣 ???놁뒿?덈떎.") from exc
    return FileResponse(path, media_type="application/pdf", filename="湲곕뒫?몄젣_?숈쓽??pdf")


@router.get("/signatures/mine")
def list_my_signatures(db: DbDep, current_user: CurrentUserDep):
    period = service.get_or_create_active_period(db)
    return {"items": signature_ops.list_my_signatures(db, current_user, period)}


@router.get("/signatures/{signature_id}/document")
def download_signature_document(signature_id: int, db: DbDep, current_user: CurrentUserDep):
    try:
        path = signature_ops.get_signature_document_path(db, current_user, signature_id)
    except ValueError as exc:
        code = str(exc)
        if code == "FORBIDDEN":
            raise HTTPException(status_code=403, detail="?ㅼ슫濡쒕뱶 沅뚰븳???놁뒿?덈떎.") from exc
        raise HTTPException(status_code=404, detail="?쒕챸 臾몄꽌瑜?李얠쓣 ???놁뒿?덈떎.") from exc
    return FileResponse(path, media_type="application/pdf", filename=f"湲곕뒫?몄젣_?쒕챸_{signature_id}.pdf")


@router.get("/my-team/signoff-status")
def get_team_signoff_status(db: DbDep, current_user: CurrentUserDep):
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return signature_ops.get_team_signoff_status(db, current_user, period)
    except ValueError as exc:
        raise _signature_error(str(exc)) from exc


@router.post("/my-team/signoff")
def submit_team_signoff(
    body: FunctionalEvalSignatureSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    try:
        row = signature_ops.submit_team_signoff(
            db,
            current_user,
            period,
            signature_data=body.signature_data,
            s_over_limit_reason=body.s_over_limit_reason,
            no_c_grade_reason=body.no_c_grade_reason,
            request=request,
        )
    except ValueError as exc:
        raise _signature_error(str(exc)) from exc
    return {"signature": row}


@router.post("/my-site/team-leader/{team_leader_login_id}/reject-report")
def reject_team_leader_report(
    team_leader_login_id: str,
    body: FunctionalEvalTeamReportReject,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?뚯옣 ??????됯??꾨즺蹂닿퀬??諛섎젮 (?먯닔 ?ъ옉??."""
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    try:
        result = signature_ops.reject_team_leader_report(
            db,
            current_user,
            period,
            site_code,
            team_leader_login_id,
            reject_note=body.reject_note,
        )
    except ValueError as exc:
        raise _signature_error(str(exc)) from exc
    return result


@router.post("/my-site/team-leader/{team_leader_login_id}/approve-report")
def approve_team_leader_report(
    team_leader_login_id: str,
    body: FunctionalEvalSignatureSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?뚯옣 ??????됯??꾨즺蹂닿퀬???뱀씤 ?쒕챸."""
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    try:
        row = signature_ops.submit_team_manager_approval(
            db,
            current_user,
            period,
            site_code,
            team_leader_login_id,
            signature_data=body.signature_data,
            request=request,
        )
    except ValueError as exc:
        raise _signature_error(str(exc)) from exc
    return {"signature": row}


@router.post("/my-site/approval/submit")
def submit_site_approval(
    body: FunctionalEvalSignatureSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?뚯옣 ???꾩옣 ?꾩껜 ?됯? ?뱀씤(?덉쟾蹂닿굔??寃???붿껌)."""
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    if not service._is_primary_site_evaluator(db, current_user, site_code):
        raise HTTPException(status_code=403, detail="?뚯옣留??꾩옣 ?뱀씤?????덉뒿?덈떎.")
    try:
        approval = signature_ops.submit_site_approval_with_signature(
            db,
            current_user,
            period,
            site_code,
            signature_data=body.signature_data,
            s_over_limit_reason=body.s_over_limit_reason,
            no_c_grade_reason=body.no_c_grade_reason,
            request=request,
        )
    except ValueError as exc:
        code = str(exc)
        if code in {"INCOMPLETE_EVALUATIONS", "INVALID_APPROVAL_TRANSITION"}:
            if code == "INCOMPLETE_EVALUATIONS":
                raise HTTPException(
                    status_code=400,
                    detail="?꾩썝 ?됯?(湲곕뒫+?덉쟾)媛 ?꾨즺?섏뼱???뚯옣 ?뱀씤?????덉뒿?덈떎.",
                ) from exc
            raise HTTPException(status_code=409, detail="?대? ?뱀씤 ?붿껌?섏뿀嫄곕굹 泥섎━ 以묒엯?덈떎.") from exc
        raise _signature_error(code) from exc
    return {"approval": approval}


@router.post("/my-site/approval/self-reject")
def self_reject_site_approval(
    body: FunctionalEvalTeamReportReject,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    if not service._is_primary_site_evaluator(db, current_user, site_code):
        raise HTTPException(status_code=403, detail="소장만 현장 자체반려를 할 수 있습니다.")
    try:
        approval = signature_ops.self_reject_site_approval(
            db,
            current_user,
            period,
            site_code,
            reject_note=body.reject_note,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "INVALID_APPROVAL_TRANSITION":
            raise HTTPException(status_code=409, detail="본사 승인 전 제출 완료 상태에서만 자체반려할 수 있습니다.") from exc
        raise _signature_error(code) from exc
    return {"approval": approval}


@router.post("/my-site/supplemental-signoff")
def submit_supplemental_site_signoff(
    body: FunctionalEvalSignatureSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """異붽??됯? ??蹂꾨룄 ?쒕챸 (湲곗〈 ?뱀씤 ?곹깭 ?좎?)."""
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    try:
        row = signature_ops.submit_supplemental_site_signoff(
            db,
            current_user,
            period,
            site_code,
            signature_data=body.signature_data,
            request=request,
        )
    except ValueError as exc:
        raise _signature_error(str(exc)) from exc
    return {"signature": row}


@router.get("/hq/approvals/pending")
def list_hq_pending_approvals(db: DbDep, current_user: CurrentUserDep):
    """?덉쟾蹂닿굔?????대떦/?ㅼ옣 寃???湲??꾩옣 紐⑸줉."""
    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    if current_user.role == Role.FUNCTIONAL_EVAL_VIEWER:
        return {
            "period": service.serialize_period(period, db),
            "hq_role": "viewer",
            "officer_items": [],
            "director_items": [],
            "items": [],
        }
    officer_items = approval_workflow.list_pending_hq_officer_approvals(db, period)
    director_items = approval_workflow.list_pending_hq_director_approvals(db, period)
    hq_role = approval_workflow.resolve_hq_approval_role(current_user)
    items = officer_items if hq_role in {"officer", "admin"} else director_items
    if hq_role == "admin" and not items:
        items = director_items or officer_items
    return {
        "period": service.serialize_period(period, db),
        "hq_role": hq_role,
        "officer_items": officer_items,
        "director_items": director_items,
        "items": items,
    }


@router.post("/hq/approvals/officer/approve-all")
def approve_all_hq_officer(
    body: FunctionalEvalHqOfficerApprovalSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?덉쟾蹂닿굔 ?대떦 ???湲??꾩옣 ?꾩껜 寃?졖룹듅??+ ?쒕챸."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return signature_ops.approve_hq_officer_all_with_signature(
            db,
            current_user,
            period,
            signature_data=body.signature_data,
            officer_comment=body.officer_comment,
            request=request,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "HQ_OFFICER_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="?덉쟾蹂닿굔 ?대떦(李⑥옣) 沅뚰븳???꾩슂?⑸땲??") from exc
        raise _signature_error(code) from exc


@router.post("/hq/approvals/officer/{site_code}/approve")
def approve_site_hq_officer(
    site_code: str,
    body: FunctionalEvalHqOfficerApprovalSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?덉쟾蹂닿굔 ?대떦 ???꾩옣蹂?寃?졖룹듅??+ ?쒕챸."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        approval = signature_ops.approve_hq_officer_site_with_signature(
            db,
            current_user,
            period,
            site_code.strip(),
            signature_data=body.signature_data,
            officer_comment=body.officer_comment,
            request=request,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "HQ_OFFICER_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="?덉쟾蹂닿굔 ?대떦(李⑥옣) 沅뚰븳???꾩슂?⑸땲??") from exc
        raise _signature_error(code) from exc
    return {"approval": approval}


@router.post("/hq/approvals/director/approve-all")
def approve_all_hq_director(
    body: FunctionalEvalHqDirectorApprovalSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?덉쟾蹂닿굔?ㅼ옣 ???대떦 ?뱀씤 ?꾨즺 ?꾩옣 ?꾩껜 理쒖쥌?뱀씤 + ?쒕챸."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return signature_ops.approve_hq_director_all_with_signature(
            db,
            current_user,
            period,
            signature_data=body.signature_data,
            director_comment=body.director_comment,
            request=request,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "HQ_DIRECTOR_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="?덉쟾蹂닿굔?ㅼ옣(?꾨Т) 沅뚰븳???꾩슂?⑸땲??") from exc
        raise _signature_error(code) from exc


@router.post("/hq/approvals/director/{site_code}/approve")
def approve_site_hq_director(
    site_code: str,
    body: FunctionalEvalHqDirectorApprovalSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?덉쟾蹂닿굔?ㅼ옣 ???꾩옣蹂?理쒖쥌?뱀씤 + ?쒕챸."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        approval = signature_ops.approve_hq_director_site_with_signature(
            db,
            current_user,
            period,
            site_code.strip(),
            signature_data=body.signature_data,
            director_comment=body.director_comment,
            request=request,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "HQ_DIRECTOR_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="?덉쟾蹂닿굔?ㅼ옣(?꾨Т) 沅뚰븳???꾩슂?⑸땲??") from exc
        raise _signature_error(code) from exc
    return {"approval": approval}


@router.post("/hq/approvals/approve-all")
def approve_all_hq(body: FunctionalEvalHqApprovalSubmit, request: Request, db: DbDep, current_user: CurrentUserDep):
    """?섏쐞 ?명솚 ??濡쒓렇????븷???곕씪 ?대떦/?ㅼ옣 ?쇨큵 ?뱀씤."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return signature_ops.approve_hq_all_with_signature(
            db,
            current_user,
            period,
            signature_data=body.signature_data,
            officer_comment=body.officer_comment,
            director_comment=body.director_comment,
            request=request,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "HQ_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="?덉쟾蹂닿굔??沅뚰븳???꾩슂?⑸땲??") from exc
        raise _signature_error(code) from exc


@router.post("/hq/approvals/{site_code}/approve")
def approve_site_hq(
    site_code: str,
    body: FunctionalEvalHqApprovalSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """?섏쐞 ?명솚 ??濡쒓렇????븷???곕씪 ?대떦/?ㅼ옣 ?꾩옣蹂??뱀씤."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    code = site_code.strip()
    row = approval_workflow.get_or_create_site_approval(db, period.id, code)
    try:
        if row.status == APPROVAL_STATUS_SITE_APPROVED:
            approval = signature_ops.approve_hq_officer_site_with_signature(
                db,
                current_user,
                period,
                code,
                signature_data=body.signature_data,
                officer_comment=body.officer_comment,
                request=request,
            )
        elif row.status == APPROVAL_STATUS_HQ_OFFICER_APPROVED:
            approval = signature_ops.approve_hq_director_site_with_signature(
                db,
                current_user,
                period,
                code,
                signature_data=body.signature_data,
                director_comment=body.director_comment,
                request=request,
            )
        else:
            raise ValueError("INVALID_APPROVAL_TRANSITION")
    except ValueError as exc:
        code = str(exc)
        if code == "INVALID_APPROVAL_TRANSITION":
            raise HTTPException(status_code=409, detail="?뱀씤 媛?ν븳 ?곹깭媛 ?꾨떃?덈떎.") from exc
        if code in {"HQ_OFFICER_APPROVER_ONLY", "HQ_DIRECTOR_APPROVER_ONLY"}:
            raise HTTPException(status_code=403, detail="?뱀씤 沅뚰븳???놁뒿?덈떎.") from exc
        raise _signature_error(code) from exc
    return {"approval": approval}


@router.post("/hq/approvals/{site_code}/reject")
def reject_site_hq(site_code: str, body: FunctionalEvalApprovalReject, db: DbDep, current_user: CurrentUserDep):
    """?덉쟾蹂닿굔??諛섎젮 ??濡쒓렇????븷???곕씪 ?대떦/?ㅼ옣 ?④퀎."""
    assert_hq_safe_workspace(current_user)
    try:
        approval_workflow.assert_hq_approver(current_user)
        period = service.get_or_create_active_period(db)
        role = approval_workflow.resolve_hq_approval_role(current_user)
        stage = "HQ_OFFICER" if role in {"officer", "admin"} else "HQ_DIRECTOR"
        approval = approval_workflow.reject_approval(
            db,
            period=period,
            site_code=site_code.strip(),
            user=current_user,
            stage=stage,
            note=body.note,
        )
    except ValueError as exc:
        if str(exc) == "INVALID_APPROVAL_TRANSITION":
            raise HTTPException(status_code=409, detail="諛섎젮?????녿뒗 ?곹깭?낅땲??") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval": approval}


@router.get("/hq/ceo-approvals/pending")
def list_ceo_pending_approvals(db: DbDep, current_user: CurrentUserDep):
    """??쒖씠?????덉쟾蹂닿굔???뱀씤 ?꾨즺 ?꾩옣 紐⑸줉. 鍮꾨???怨꾩젙? 鍮?紐⑸줉."""
    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    if current_user.role == Role.FUNCTIONAL_EVAL_VIEWER:
        return {
            "period": service.serialize_period(period, db),
            "items": [],
            "ceo_eligible": False,
        }
    try:
        approval_workflow.assert_ceo_approver(current_user)
    except ValueError:
        return {
            "period": service.serialize_period(period, db),
            "items": [],
            "ceo_eligible": False,
        }
    return {
        "period": service.serialize_period(period, db),
        "items": approval_workflow.list_pending_ceo_approvals(db, period),
        "ceo_eligible": True,
    }


@router.post("/hq/ceo-approvals/approve-all")
def approve_all_ceo(body: FunctionalEvalSignatureSubmit, request: Request, db: DbDep, current_user: CurrentUserDep):
    """??쒖씠?????湲??꾩옣 ?꾩껜 ?쇨큵 理쒖쥌?뱀씤 + ?쒕챸."""
    period = service.get_or_create_active_period(db)
    try:
        return signature_ops.approve_ceo_all_with_signature(
            db, current_user, period, signature_data=body.signature_data, request=request
        )
    except ValueError as exc:
        code = str(exc)
        if code == "CEO_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="??쒖씠??理쒓퀬愿由ъ옄) 沅뚰븳???꾩슂?⑸땲??") from exc
        raise _signature_error(code) from exc


@router.post("/hq/ceo-approvals/{site_code}/approve")
def approve_site_ceo(
    site_code: str,
    body: FunctionalEvalSignatureSubmit,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
):
    """??쒖씠??理쒖쥌 ?뱀씤."""
    try:
        approval_workflow.assert_ceo_approver(current_user)
        period = service.get_or_create_active_period(db)
        approval = approval_workflow.approve_ceo(db, period=period, site_code=site_code.strip(), user=current_user)
    except ValueError as exc:
        code = str(exc)
        if code == "INVALID_APPROVAL_TRANSITION":
            raise HTTPException(status_code=409, detail="?덉쟾蹂닿굔???뱀씤 ?湲??곹깭媛 ?꾨떃?덈떎.") from exc
        if code == "CEO_APPROVER_ONLY":
            raise HTTPException(status_code=403, detail="??쒖씠??理쒓퀬愿由ъ옄) 沅뚰븳???꾩슂?⑸땲??") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return {"approval": approval}


@router.post("/hq/ceo-approvals/{site_code}/reject")
def reject_site_ceo(site_code: str, body: FunctionalEvalApprovalReject, db: DbDep, current_user: CurrentUserDep):
    """??쒖씠??諛섎젮."""
    try:
        approval_workflow.assert_ceo_approver(current_user)
        period = service.get_or_create_active_period(db)
        approval = approval_workflow.reject_approval(
            db,
            period=period,
            site_code=site_code.strip(),
            user=current_user,
            stage="CEO",
            note=body.note,
        )
    except ValueError as exc:
        if str(exc) == "INVALID_APPROVAL_TRANSITION":
            raise HTTPException(status_code=409, detail="諛섎젮?????녿뒗 ?곹깭?낅땲??") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"approval": approval}


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
    """?섏쐞 ?명솚 ???쒖옱 媛먯젏쨌?ъ긽 媛???⑹궛 (`/workers/{id}/adjustments`? ?숈씪)."""
    from app.modules.functional_eval.models import FunctionalEvalWorker

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    try:
        service._assert_worker_access(db, current_user, worker)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return service.serialize_worker_adjustments(db, worker)


@router.post("/sanctions")
async def create_sanction(
    db: DbDep,
    current_user: CurrentUserDep,
    worker_id: int = Form(...),
    violation_code: str = Form(...),
    evidence_type: str = Form(default="COMMENT"),
    note: str | None = Form(default=None),
    signature_data: str = Form(...),
    photo: UploadFile | None = File(default=None),
):
    from app.modules.functional_eval import sanction_evidence as evidence_service

    if _role_value(current_user) not in {
        Role.SITE_FUNCTIONAL_EVAL.value,
        Role.HQ_SAFE.value,
        Role.HQ_SAFE_ADMIN.value,
        Role.SUPER_ADMIN.value,
        Role.ACCIDENT_ADMIN.value,
    }:
        raise HTTPException(status_code=403, detail="Not allowed")
    period = service.get_or_create_active_period(db)
    photo_path: str | None = None
    photo_original: str | None = None
    try:
        ev_type = (evidence_type or "COMMENT").strip().upper()
        if ev_type == evidence_service.EVIDENCE_PHOTO:
            if photo is None:
                raise ValueError("SANCTION_EVIDENCE_PHOTO_REQUIRED")
            photo_path, photo_original = await evidence_service.save_sanction_evidence_photo(
                period_id=period.id,
                file=photo,
            )
        row = service.record_sanction(
            db,
            period=period,
            user=current_user,
            worker_id=worker_id,
            violation_code=violation_code.strip(),
            evidence_type=ev_type,
            note=note,
            evidence_photo_path=photo_path,
            evidence_photo_original_filename=photo_original,
            signature_data=signature_data,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="留덇컧?쇱씠 吏???섏젙?????놁뒿?덈떎.") from exc
        if code == "EVAL_NOT_OPEN":
            raise HTTPException(
                status_code=403,
                detail="?됯???2026??6??16???ㅼ쟾 6?쒕???媛?ν빀?덈떎. ?ㅻ뒛? ?꾩씠?붋룸퉬諛踰덊샇 蹂寃쎈쭔 ?댁슜??二쇱꽭??",
            ) from exc
        if code in {"WORKER_NOT_FOUND", "SITE_MISMATCH", "CANNOT_SANCTION_SITE_MANAGER", "WORKER_INACTIVE"}:
            raise HTTPException(status_code=400, detail=code) from exc
        if code in {"WORKER_NOT_ON_ATTENDANCE", "NO_ATTENDANCE_UPLOAD"}:
            raise HTTPException(
                status_code=400,
                detail="?뱀씪 異쒖뿭 紐낅떒???녾굅??異쒖뿭?쇰낫媛 諛섏쁺?섏? ?딆븯?듬땲??",
            ) from exc
        if code == "UNKNOWN_VIOLATION":
            raise HTTPException(status_code=400, detail="?????녿뒗 ?꾨컲 ??ぉ?낅땲??") from exc
        mapping = {
            "SANCTION_EVIDENCE_COMMENT_REQUIRED": "?쒖옱 洹쇨굅 肄붾찘?몃? ?낅젰?섏꽭??",
            "SANCTION_EVIDENCE_PHOTO_REQUIRED": "?쒖옱 洹쇨굅 ?ъ쭊??泥⑤??섏꽭??",
            "SANCTION_SIGNATURE_REQUIRED": "?쒖옱 ?깅줉???꾪빐 ?쒕챸???꾩슂?⑸땲??",
            "INVALID_EVIDENCE_TYPE": "洹쇨굅 ?좏삎???щ컮瑜댁? ?딆뒿?덈떎.",
            "INVALID_SANCTION_PHOTO_TYPE": "jpg, png, webp ?대?吏留??낅줈?쒗븷 ???덉뒿?덈떎.",
            "EMPTY_SANCTION_PHOTO": "鍮??뚯씪?낅땲??",
            "SANCTION_PHOTO_TOO_LARGE": "8MB ?댄븯 ?대?吏留??낅줈?쒗븷 ???덉뒿?덈떎.",
        }
        if code in mapping:
            raise HTTPException(status_code=400, detail=mapping[code]) from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return row


@router.get("/sanctions/{sanction_id}/evidence-photo")
def get_sanction_evidence_photo(sanction_id: int, db: DbDep, current_user: CurrentUserDep):
    from app.modules.functional_eval import sanction_evidence as evidence_service
    from app.modules.functional_eval.models import FunctionalEvalSanction

    row = db.query(FunctionalEvalSanction).filter(FunctionalEvalSanction.id == sanction_id).first()
    if row is None or not row.evidence_photo_path:
        raise HTTPException(status_code=404, detail="EVIDENCE_NOT_FOUND")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="WORKER_NOT_FOUND")
    try:
        if _role_value(current_user) in {
            Role.HQ_SAFE.value,
            Role.HQ_SAFE_ADMIN.value,
            Role.SUPER_ADMIN.value,
            Role.ACCIDENT_ADMIN.value,
        }:
            pass
        elif _role_value(current_user) == Role.SITE_FUNCTIONAL_EVAL.value:
            service._assert_worker_view_access(db, current_user, worker)
        else:
            raise HTTPException(status_code=403, detail="Not allowed")
        path = evidence_service.get_sanction_evidence_photo_path(row.evidence_photo_path)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PHOTO_NOT_FOUND")
    return FileResponse(path)


@router.get("/sanctions/{sanction_id}/signature")
def get_sanction_signature_image(sanction_id: int, db: DbDep, current_user: CurrentUserDep):
    from app.modules.functional_eval.models import FunctionalEvalSanction
    from app.modules.functional_eval.signature_service import validate_signature_data

    row = db.query(FunctionalEvalSanction).filter(FunctionalEvalSanction.id == sanction_id).first()
    if row is None or not (row.signature_data or "").strip():
        raise HTTPException(status_code=404, detail="SIGNATURE_NOT_FOUND")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="WORKER_NOT_FOUND")
    try:
        if _role_value(current_user) in {
            Role.HQ_SAFE.value,
            Role.HQ_SAFE_ADMIN.value,
            Role.SUPER_ADMIN.value,
            Role.ACCIDENT_ADMIN.value,
        }:
            pass
        elif _role_value(current_user) == Role.SITE_FUNCTIONAL_EVAL.value:
            service._assert_worker_view_access(db, current_user, worker)
        else:
            raise HTTPException(status_code=403, detail="Not allowed")
        _, png_bytes = validate_signature_data(row.signature_data)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from fastapi.responses import Response

    return Response(content=png_bytes, media_type="image/png")


@router.get("/hq/grade-stats")
def hq_grade_stats(db: DbDep, current_user: CurrentUserDep):
    """蹂몄궗 ???꾩껜쨌?蹂꽷룻쁽?λ퀎 ?깃툒 遺꾪룷."""
    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    return service.build_hq_grade_stats(db, period)


@router.get("/hq/sites/{site_code}/grade-stats")
def hq_site_grade_stats(site_code: str, db: DbDep, current_user: CurrentUserDep):
    """蹂몄궗 ???뱀젙 ?꾩옣 ?깃툒 遺꾪룷."""
    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return service.build_site_grade_stats(db, period, site_code.strip())
    except ValueError as exc:
        if str(exc) in {"NO_ATTENDANCE_WORKERS", "NO_SITE_IN_REGISTRY"}:
            raise HTTPException(status_code=404, detail="異쒖뿭 ???洹쇰줈?먭? ?놁뒿?덈떎.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/my-site/grade-stats")
def my_site_grade_stats(db: DbDep, current_user: CurrentUserDep):
    """?꾩옣 ?????꾩옣 ?깃툒 遺꾪룷."""
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    site_code = service._site_code_for_user(current_user, db)
    try:
        return service.build_site_grade_stats(db, period, site_code)
    except ValueError as exc:
        if str(exc) in {"NO_ATTENDANCE_WORKERS", "NO_SITE_IN_REGISTRY"}:
            raise HTTPException(status_code=404, detail="異쒖뿭 ???洹쇰줈?먭? ?놁뒿?덈떎.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/hq/summary")
def hq_summary(
    db: DbDep,
    current_user: CurrentUserDep,
    sort_by: str = Query(default="site_code"),
    sort_dir: str = Query(default="asc"),
    site_code: str | None = Query(default=None),
    include_inactive: bool = Query(default=True),
):
    """?꾩옣蹂??됯? 吏꾪뻾瑜?紐⑸줉 (洹쇰줈???곸꽭 誘명룷??."""
    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    return service.build_hq_summary_response(
        db,
        period,
        sort_by=sort_by,
        sort_dir=sort_dir,
        site_code=site_code,
        include_inactive=include_inactive,
    )


@router.get("/hq/monitoring-summary")
def hq_monitoring_summary(db: DbDep, current_user: CurrentUserDep):
    """?댁쁺吏???꾩슜 紐⑤땲?곕쭅 吏묎퀎(?묒냽以??됯?以??됯??꾨즺)."""
    assert_fe_hq_monitoring(current_user)
    period = service.get_or_create_active_period(db)
    return service.get_hq_monitoring_summary(db, period)


@router.get("/hq/sites/{site_code}/evaluations")
def hq_site_evaluations(
    site_code: str,
    db: DbDep,
    current_user: CurrentUserDep,
    sort_by: str = Query(default="name"),
    sort_dir: str = Query(default="asc"),
):
    """?꾩옣蹂??됯? ?꾨즺?먮쭔 (湲곕뒫+?덉쟾 紐⑤몢 ?꾨즺)."""
    assert_fe_hq_read(current_user)
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
    """?붾퀎?꾩옣蹂꾩쭛怨?xls ???꾩옣肄붾뱶쨌蹂꾩묶(??곗껌??쨌?뚯옣 濡쒓렇??ID 留ㅽ븨."""
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
            raise HTTPException(status_code=400, detail="?뚯씪??鍮꾩뼱 ?덉뒿?덈떎.") from exc
        if code == "NO_SITE_AGGREGATE_ROWS":
            raise HTTPException(status_code=400, detail="?꾩옣 吏묎퀎 ?됱쓣 李얠쓣 ???놁뒿?덈떎.") from exc
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="留덇컧?쇱씠 吏??諛섏쁺?????놁뒿?덈떎.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return result


@router.post("/hq/attendance/apply")
async def attendance_apply(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """ERP 異쒖뿭?쇰낫 xls/xlsx ??吏묎퀎 諛섏쁺 ??1??1???낅줈??蹂꾩묶-?대쫫 怨꾩젙쨌????먮룞)."""
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
            raise HTTPException(status_code=400, detail="?뚯씪??鍮꾩뼱 ?덉뒿?덈떎.") from exc
        if code == "NO_ATTENDANCE_ROWS":
            raise HTTPException(status_code=400, detail="異쒖뿭 洹쇰줈???됱쓣 李얠쓣 ???놁뒿?덈떎.") from exc
        if code == "MULTIPLE_WORK_DATES":
            raise HTTPException(status_code=400, detail="???뚯씪??異쒖뿭?쇱씠 ?щ윭 媛쒖엯?덈떎.") from exc
        if code == "SITE_REGISTRY_REQUIRED":
            raise HTTPException(
                status_code=400,
                detail="癒쇱? ?붾퀎?꾩옣蹂꾩쭛怨??뚯씪??諛섏쁺????異쒖뿭?쇰낫瑜??낅줈?쒗븯?몄슂.",
            ) from exc
        if code == "PERIOD_CLOSED":
            raise HTTPException(status_code=409, detail="留덇컧?쇱씠 吏??諛섏쁺?????놁뒿?덈떎.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return result


@router.get("/hq/evaluator-accounts")
def list_evaluator_accounts(db: DbDep, current_user: CurrentUserDep):
    """?뚯옣쨌???以묎컙 ?됯??? 怨꾩젙 紐⑸줉 ??異쒖뿭 諛섏쁺쨌諛곗젙 ?꾪솴 (蹂몄궗 諛고룷??."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    return service.list_hq_evaluator_accounts(db, period)


@router.post("/hq/team-leaders/apply")
async def apply_team_leaders(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """10紐?珥덇낵 ?꾩옣?????怨꾩젙 諛쒓툒 諛????諛곗젙(?댄븯 ?꾩옣? ?뚯옣???꾩썝 ?됯?)."""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    tmp = await _save_upload(file, period.id)
    try:
        result = service.apply_team_leader_assignments_file(db, period, tmp)
    except ValueError as exc:
        code = str(exc)
        if code == "TEAM_ASSIGNMENT_UNSUPPORTED_FILE":
            raise HTTPException(status_code=400, detail="吏???뺤떇? .txt/.xls/.xlsx ?낅땲??") from exc
        if code == "TEAM_ASSIGNMENT_HEADER_INVALID":
            raise HTTPException(status_code=400, detail="?꾩닔 而щ읆(?꾩옣肄붾뱶/??λ챸/??μ＜誘쇰쾲????먮챸)???뺤씤?섏꽭??") from exc
        if code in {"NO_TEAM_ASSIGNMENT_ROWS", "EMPTY_FILE"}:
            raise HTTPException(status_code=400, detail="諛섏쁺 媛?ν븳 ???????됱씠 ?놁뒿?덈떎.") from exc
        raise HTTPException(status_code=400, detail=code) from exc
    return {"period": service.serialize_period(period, db), **result}


@router.post("/hq/import-roster")
async def import_roster_legacy(
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    """?쇱슜吏?紐낅? ?곸슜 (DIFF 諛섏쁺). `/hq/roster/apply` ? ?숈씪."""
    return await roster_apply(db, current_user, file)


@router.get("/hq/export/evaluations")
def export_hq_evaluations_excel(
    db: DbDep,
    current_user: CurrentUserDep,
    site_code: str | None = Query(default=None),
):
    """?됯? ?꾪솴 ?묒? ???꾩껜 ?먮뒗 ?꾩옣蹂?洹쇰줈???됯??곹깭??"""
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)

    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "?됯??꾪솴"
    ws.append(
        [
            "?꾩옣肄붾뱶",
            "현장명",
            "?됯????뚯옣)",
            "?깅챸",
            "?됯??곹깭",
            "?덉쭏?깃툒",
            "?덉쟾?깃툒",
            "?꾩껜?꾨즺",
            "鍮꾧퀬",
        ]
    )
    for row in service.list_hq_eval_export_rows(db, period, site_code=site_code):
        ws.append(
            [
                row["site_code"],
                row["site_name"],
                row["evaluator_name"],
                row["name"],
                row["eval_status"],
                row["functional_grade"],
                row["safety_grade"],
                row["fully_complete"],
                row["remark"],
            ]
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    suffix = f"_{site_code.strip()}" if site_code and site_code.strip() else ""
    filename = f"functional_eval_status_{period.id}{suffix}.xlsx"
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
        raise HTTPException(status_code=409, detail="留덇컧 ?꾩뿉留??ㅼ슫濡쒕뱶?????덉뒿?덈떎.")

    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "?쒖옱?꾪솴"
    ws.append(
        [
            "?꾩옣肄붾뱶",
            "?깅챸",
            "紐낅??곹깭",
            "?쒖옱?곹깭",
            "?꾨컲??ぉ",
            "?쒖옱寃곌낵",
            "?꾩쟻李⑥닔",
            "鍮꾧퀬",
            "?깅줉?쇱떆",
        ]
    )
    items = service.list_hq_summary(db, period, sort_by=sort_by, sort_dir=sort_dir, include_inactive=True)
    for item in items:
        worker = item["worker"]
        sanctions = item["sanctions"]
        active_label = "?ъ쭅" if worker.get("is_active") else "紐낅??쒖쇅"
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


@router.post("/workers/{worker_id}/customer-rewards")
async def submit_customer_reward(
    worker_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    photo: UploadFile = File(...),
    bonus_points: int = Query(default=5, ge=1, le=100),
):
    _assert_site_functional_eval(current_user)
    period = service.get_or_create_active_period(db)
    try:
        photo_path, original = await reward_service.save_reward_photo(period_id=period.id, file=photo)
        return reward_service.submit_customer_reward(
            db,
            period=period,
            user=current_user,
            worker_id=worker_id,
            photo_path=photo_path,
            original_filename=original,
            bonus_points=bonus_points,
        )
    except ValueError as exc:
        code = str(exc)
        mapping = {
            "WORKER_NOT_FOUND": (404, "Worker not found"),
            "SITE_ONLY": (403, "?꾩옣 怨꾩젙留??쒖텧?????덉뒿?덈떎."),
            "REWARD_ALREADY_PENDING": (409, "?뱀씤 ?湲?以묒씤 ?ъ긽 ?쒖텧???덉뒿?덈떎."),
            "REWARD_ALREADY_SUBMITTED": (409, "?대? ?쒖텧???ъ긽 ?ъ쭊? ?뚯닔쨌蹂寃쏀븷 ???놁뒿?덈떎."),
            "INVALID_REWARD_PHOTO_TYPE": (400, "jpg, png, webp ?대?吏留??낅줈?쒗븷 ???덉뒿?덈떎."),
            "EMPTY_REWARD_PHOTO": (400, "鍮??뚯씪?낅땲??"),
            "REWARD_PHOTO_TOO_LARGE": (400, "8MB ?댄븯 ?대?吏留??낅줈?쒗븷 ???덉뒿?덈떎."),
            "PERIOD_CLOSED": (409, "?됯? 留덇컧 ?꾩뿉???ъ긽쨌?쒖옱 ?대젰留??깅줉?????덉뒿?덈떎."),
        }
        if code in mapping:
            status_code, detail = mapping[code]
            raise HTTPException(status_code=status_code, detail=detail) from exc
        if code == "SITE_MISMATCH":
            raise HTTPException(status_code=403, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.get("/hq/customer-rewards/pending")
def list_pending_customer_rewards(db: DbDep, current_user: CurrentUserDep):
    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    return {"items": reward_service.list_pending_customer_rewards(db, period)}


@router.post("/hq/customer-rewards/{reward_id}/approve")
def approve_customer_reward(
    reward_id: int,
    body: FunctionalEvalCustomerRewardApprove,
    db: DbDep,
    current_user: CurrentUserDep,
):
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return reward_service.approve_customer_reward(
            db,
            period=period,
            user=current_user,
            reward_id=reward_id,
            bonus_points=body.bonus_points,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "REWARD_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        if code in {"REWARD_NOT_PENDING", "PERIOD_CLOSED"}:
            raise HTTPException(status_code=409, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.post("/hq/customer-rewards/{reward_id}/reject")
def reject_customer_reward(
    reward_id: int,
    body: FunctionalEvalCustomerRewardReject,
    db: DbDep,
    current_user: CurrentUserDep,
):
    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return reward_service.reject_customer_reward(
            db,
            period=period,
            reward_id=reward_id,
            user=current_user,
            reject_note=body.reject_note,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "REWARD_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        if code in {"REWARD_NOT_PENDING", "PERIOD_CLOSED"}:
            raise HTTPException(status_code=409, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.get("/hq/sanctions/pending")
def list_pending_sanctions(db: DbDep, current_user: CurrentUserDep):
    from app.modules.functional_eval import sanction_reviews as sanction_review_service

    assert_fe_hq_read(current_user)
    period = service.get_or_create_active_period(db)
    return {"items": sanction_review_service.list_pending_sanctions(db, period)}


@router.post("/hq/sanctions/{sanction_id}/approve")
def approve_pending_sanction(sanction_id: int, db: DbDep, current_user: CurrentUserDep):
    from app.modules.functional_eval import sanction_reviews as sanction_review_service

    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return sanction_review_service.approve_sanction(
            db,
            period=period,
            user=current_user,
            sanction_id=sanction_id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "SANCTION_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        if code == "SANCTION_NOT_PENDING":
            raise HTTPException(status_code=409, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.post("/hq/sanctions/{sanction_id}/reject")
def reject_pending_sanction(
    sanction_id: int,
    body: FunctionalEvalCustomerRewardReject,
    db: DbDep,
    current_user: CurrentUserDep,
):
    from app.modules.functional_eval import sanction_reviews as sanction_review_service

    assert_hq_safe_workspace(current_user)
    period = service.get_or_create_active_period(db)
    try:
        return sanction_review_service.reject_sanction(
            db,
            period=period,
            sanction_id=sanction_id,
            user=current_user,
            reject_note=body.reject_note,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "SANCTION_NOT_FOUND":
            raise HTTPException(status_code=404, detail=code) from exc
        if code == "SANCTION_NOT_PENDING":
            raise HTTPException(status_code=409, detail=code) from exc
        raise HTTPException(status_code=400, detail=code) from exc


@router.get("/customer-rewards/{reward_id}/photo")
def get_customer_reward_photo(reward_id: int, db: DbDep, current_user: CurrentUserDep):
    from app.modules.functional_eval.models import FunctionalEvalCustomerReward, FunctionalEvalWorker

    row = db.query(FunctionalEvalCustomerReward).filter(FunctionalEvalCustomerReward.id == reward_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="REWARD_NOT_FOUND")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="WORKER_NOT_FOUND")
    try:
        if _role_value(current_user) in {
            Role.HQ_SAFE.value,
            Role.HQ_SAFE_ADMIN.value,
            Role.SUPER_ADMIN.value,
            Role.ACCIDENT_ADMIN.value,
        }:
            pass
        elif _role_value(current_user) == Role.SITE_FUNCTIONAL_EVAL.value:
            service._assert_worker_view_access(db, current_user, worker)
        else:
            raise HTTPException(status_code=403, detail="Not allowed")
        path = reward_service.get_reward_photo_path(db, reward_id)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PHOTO_NOT_FOUND")
    return FileResponse(path)


@router.get("/workers/{worker_id}/customer-rewards")
def list_worker_customer_rewards(worker_id: int, db: DbDep, current_user: CurrentUserDep):
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise HTTPException(status_code=404, detail="WORKER_NOT_FOUND")
    try:
        if _role_value(current_user) in {
            Role.HQ_SAFE.value,
            Role.HQ_SAFE_ADMIN.value,
            Role.SUPER_ADMIN.value,
            Role.ACCIDENT_ADMIN.value,
        }:
            pass
        elif _role_value(current_user) == Role.SITE_FUNCTIONAL_EVAL.value:
            service._assert_worker_view_access(db, current_user, worker)
        else:
            raise HTTPException(status_code=403, detail="Not allowed")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"items": reward_service.list_worker_customer_rewards(db, worker_id)}


@router.get("/hq/daily-reports")
def list_hq_daily_reports(db: DbDep, current_user: CurrentUserDep, limit: int = Query(30, ge=1, le=100)):
    assert_fe_hq_read(current_user)
    from app.modules.functional_eval import daily_report_service

    period = service.get_or_create_active_period(db)
    return {"items": daily_report_service.list_daily_reports(db, period, limit=limit)}


@router.get("/hq/daily-reports/{report_id}")
def get_hq_daily_report(report_id: int, db: DbDep, current_user: CurrentUserDep):
    assert_fe_hq_read(current_user)
    from app.modules.functional_eval import daily_report_service

    row = daily_report_service.get_daily_report(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    return {
        **daily_report_service.serialize_daily_report_row(row),
        "snapshot": row.report_json_snapshot,
    }


@router.get("/hq/daily-reports/{report_id}/document")
def download_hq_daily_report_document(report_id: int, db: DbDep, current_user: CurrentUserDep):
    assert_hq_safe_workspace(current_user)
    from app.modules.functional_eval import daily_report_service

    row = daily_report_service.get_daily_report(db, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="REPORT_NOT_FOUND")
    path = daily_report_service.resolve_report_path(row.report_path)
    if path is None:
        raise HTTPException(status_code=404, detail="REPORT_FILE_MISSING")
    filename = f"湲곕뒫?몄씤?뺤젣_?쇱씪吏꾪뻾?꾪솴_{row.report_date.strftime('%Y%m%d')}.pdf"
    return FileResponse(path, media_type="application/pdf", filename=filename)


@router.post("/hq/daily-reports/generate")
def generate_hq_daily_report(
    db: DbDep,
    current_user: CurrentUserDep,
    report_date: date | None = Query(None),
    force: bool = Query(False, description="媛숈? ?좎쭨 蹂닿퀬???ъ깮??踰꾩쟾 利앷?)"),
):
    assert_hq_safe_workspace(current_user)
    from app.modules.functional_eval import daily_report_service

    try:
        daily_report_service.assert_hq_report_admin(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    period = service.get_or_create_active_period(db)
    try:
        row = daily_report_service.generate_daily_report(
            db,
            period,
            report_date=report_date,
            generated_by="manual",
            force=force,
        )
    except ValueError as exc:
        if str(exc) == "REPORT_ALREADY_EXISTS":
            raise HTTPException(status_code=409, detail="?대? ?대떦 ?좎쭨 蹂닿퀬?쒓? ?덉뒿?덈떎. force=true 濡??ъ깮?깊븯?몄슂.") from exc
        raise
    return daily_report_service.serialize_daily_report_row(row)


@router.post("/hq/viewer-accounts/dry-run")
def dry_run_hq_viewer_accounts(db: DbDep, current_user: CurrentUserDep):
    assert_fe_hq_admin(current_user)
    from app.modules.functional_eval import fe_viewer_provisioning_service

    try:
        result = fe_viewer_provisioning_service.dry_run_viewer_accounts(db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_dict()


@router.post("/hq/viewer-accounts/apply")
def apply_hq_viewer_accounts(db: DbDep, current_user: CurrentUserDep):
    assert_fe_hq_admin(current_user)
    from app.modules.functional_eval import fe_viewer_provisioning_service

    try:
        result = fe_viewer_provisioning_service.apply_viewer_accounts(db, actor=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_dict()


@router.get("/hq/viewer-accounts/logs")
def list_hq_viewer_account_logs(db: DbDep, current_user: CurrentUserDep, limit: int = Query(20, ge=1, le=100)):
    assert_fe_hq_admin(current_user)
    from app.modules.functional_eval import fe_viewer_provisioning_service

    return {"items": fe_viewer_provisioning_service.list_viewer_provision_logs(db, limit=limit)}
