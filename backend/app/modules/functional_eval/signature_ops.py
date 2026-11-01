"""기능인제 동의·단계별 서명 업무 로직."""

from __future__ import annotations
from app.modules.functional_eval import site_evaluator_access
from app.modules.functional_eval import additional_rounds, signature_revisions

from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.datetime_utils import format_kst_datetime_label, format_kst_datetime_short, utc_now
from app.core.enums import Role
from app.modules.functional_eval import approval_workflow
from app.modules.functional_eval.grade_inflation_guard import (
    build_grade_review_metadata,
    compute_grade_inflation_review,
    validate_grade_inflation_reasons,
)
from app.modules.functional_eval.models import (
    FunctionalEvalConsent,
    FunctionalEvalPeriod,
    FunctionalEvalSignature,
    FunctionalEvalSiteRegistry,
    FunctionalEvalSiteApproval,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.signature_service import (
    CONSENT_BODY,
    CONSENT_KIND_EVALUATOR,
    CONSENT_KIND_VIEWER,
    CONSENT_VERSION,
    EVALUATOR_CONSENT_TITLE,
    VIEWER_CONSENT_BODY,
    VIEWER_CONSENT_TITLE,
    VIEWER_CONSENT_VERSION,
    STAGE_CEO,
    STAGE_HQ,
    STAGE_HQ_OFFICER,
    STAGE_SITE,
    STAGE_TEAM_LEADER,
    STAGE_TEAM_MANAGER_APPROVE,
    batch_label,
    save_pdf_document,
    serialize_signature,
    validate_signature_data,
)
from app.modules.functional_eval.signature_report_pdf import (
    REPORT_TITLE,
    generate_ceo_final_report_pdf,
    generate_consent_pdf,
    generate_hq_review_report_pdf,
    generate_site_completion_report_pdf,
    generate_team_completion_report_pdf,
)
from app.modules.users.models import User

DOC_TITLE = "기능인인정제 평가 보고서"
SCOPE_EMPTY = ""


def _signer_meta(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:2000] or None
    return ip, ua


def _site_display_name(db: Session, site_code: str) -> str:
    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    if reg and reg.erp_site_label:
        return reg.erp_site_label[:200]
    return site_code


def _site_field_label(db: Session, site_code: str) -> str:
    """문서 부제용 — 예: 대우청라현장"""
    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    base = (reg.site_alias or "").strip() if reg else ""
    if not base:
        base = _site_display_name(db, site_code).strip()
    if base.endswith("현장"):
        return base
    return f"{base}현장"


def _build_consent_subtitle(db: Session, user: User) -> str:
    return _build_document_header(db, user)["role_line"]


def _consent_kind_for_user(user: User) -> str:
    if user.role == Role.FUNCTIONAL_EVAL_VIEWER:
        return CONSENT_KIND_VIEWER
    return CONSENT_KIND_EVALUATOR


def _consent_body_for_user(user: User) -> str:
    if _consent_kind_for_user(user) == CONSENT_KIND_VIEWER:
        return VIEWER_CONSENT_BODY
    return CONSENT_BODY


def _consent_version_for_user(user: User) -> str:
    if _consent_kind_for_user(user) == CONSENT_KIND_VIEWER:
        return VIEWER_CONSENT_VERSION
    return CONSENT_VERSION


def _consent_title_for_user(user: User) -> str:
    if _consent_kind_for_user(user) == CONSENT_KIND_VIEWER:
        return VIEWER_CONSENT_TITLE
    return EVALUATOR_CONSENT_TITLE


def _build_document_header(db: Session, user: User, *, site_code: str | None = None) -> dict[str, str]:
    from app.modules.functional_eval import service

    login_id = (user.login_id or "").strip()
    signer_name = (user.name or "").strip() or login_id
    if user.role == Role.FUNCTIONAL_EVAL_VIEWER:
        return {
            "site_full_name": "본사 기능인 인정제 조회",
            "role_line": f"본사 조회전용 - {signer_name}" + (f" ({login_id})" if login_id else ""),
        }
    if service._is_hq_safety_user(user):
        return {
            "site_full_name": "본사 기능인 인정제",
            "role_line": f"본사 - {signer_name}" + (f" ({login_id})" if login_id else ""),
        }
    site_code = site_code or service._site_code_for_user(user, db)
    site_full = _site_display_name(db, site_code)
    site_field = _site_field_label(db, site_code)
    if service._is_primary_site_evaluator(db, user, site_code):
        role_line = f"{site_field} - {signer_name} 소장"
    else:
        role_line = f"{site_field} - {signer_name}"
    return {"site_full_name": site_full, "role_line": role_line}


def _build_report_header_for_site(
    db: Session,
    site_code: str,
    person_name: str,
    *,
    is_manager: bool = False,
) -> dict[str, str]:
    name = (person_name or "").strip()
    site_full = _site_display_name(db, site_code)
    site_field = _site_field_label(db, site_code)
    suffix = " 소장" if is_manager else ""
    return {
        "site_full_name": site_full,
        "role_line": f"{site_field} - {name}{suffix}",
    }


def get_consent_status(db: Session, user: User) -> dict[str, Any]:
    from app.modules.functional_eval.eval_schedule import (
        evaluation_is_open,
        evaluation_opens_at_kst_iso,
        evaluation_opens_at_kst_label,
    )

    row = db.query(FunctionalEvalConsent).filter(FunctionalEvalConsent.user_id == user.id).first()
    team_label = _build_consent_subtitle(db, user)
    header = _build_document_header(db, user)
    consent_body = _consent_body_for_user(user)
    eval_open = evaluation_is_open()
    return {
        "required": eval_open and row is None,
        "evaluation_open": eval_open,
        "evaluation_opens_at": evaluation_opens_at_kst_iso(),
        "evaluation_opens_at_label": evaluation_opens_at_kst_label(),
        "consent_kind": _consent_kind_for_user(user),
        "consent_title": _consent_title_for_user(user),
        "consent_version": _consent_version_for_user(user),
        "consent_body": consent_body,
        "site_full_name": header["site_full_name"],
        "team_label": team_label,
        "role_line": header["role_line"],
        "signed_at": row.signed_at.isoformat() if row else None,
        "signed_at_label": format_kst_datetime_label(row.signed_at) if row else None,
    }


def submit_consent(
    db: Session,
    user: User,
    *,
    signature_data: str,
    consent_acknowledged: bool,
    read_to_bottom_confirmed: bool | None = None,
    read_completed_at: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval.eval_schedule import assert_evaluation_open

    assert_evaluation_open()
    if not consent_acknowledged:
        raise ValueError("CONSENT_ACK_REQUIRED")
    if read_to_bottom_confirmed is False:
        raise ValueError("CONSENT_SCROLL_REQUIRED")
    existing = db.query(FunctionalEvalConsent).filter(FunctionalEvalConsent.user_id == user.id).first()
    if existing is not None:
        raise ValueError("CONSENT_ALREADY_SIGNED")
    sig_hash, _ = validate_signature_data(signature_data)
    now = utc_now()
    login_id = (user.login_id or "").strip()
    signer_name = (user.name or "").strip() or login_id
    ip, ua = _signer_meta(request)
    header = _build_document_header(db, user)
    consent_body = _consent_body_for_user(user)
    consent_version = _consent_version_for_user(user)
    consent_kind = _consent_kind_for_user(user)
    pdf = generate_consent_pdf(
        signer_name=signer_name,
        signer_login_id=login_id,
        consent_body=consent_body,
        signature_data=signature_data,
        signed_at=now,
        site_full_name=header["site_full_name"],
        role_line=header["role_line"],
        document_title=_consent_title_for_user(user),
    )
    doc_path = save_pdf_document(prefix=f"consent_{login_id}", pdf_bytes=pdf)
    row = FunctionalEvalConsent(
        user_id=user.id,
        login_id=login_id,
        consent_version=consent_version,
        consent_kind=consent_kind,
        signature_data=signature_data,
        signature_hash=sig_hash,
        signed_at=now,
        signer_ip=ip,
        signer_user_agent=ua,
        signed_document_path=doc_path,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "signed_at": row.signed_at.isoformat(),
        "signed_at_label": format_kst_datetime_label(row.signed_at),
        "consent_version": row.consent_version,
    }


def assert_consent_signed(db: Session, user: User) -> None:
    row = db.query(FunctionalEvalConsent).filter(FunctionalEvalConsent.user_id == user.id).first()
    if row is None:
        raise ValueError("CONSENT_REQUIRED")


def _norm_scope(value: str | None) -> str:
    return (value or "").strip()


def _signature_exists(
    db: Session,
    *,
    period_id: int,
    batch: int,
    stage: str,
    site_code: str | None = None,
    team_leader_login_id: str | None = None,
) -> FunctionalEvalSignature | None:
    root = (
        db.query(FunctionalEvalSignature)
        .filter(
            FunctionalEvalSignature.period_id == period_id,
            FunctionalEvalSignature.evaluation_batch == batch,
            FunctionalEvalSignature.stage == stage,
            FunctionalEvalSignature.site_code == _norm_scope(site_code),
            FunctionalEvalSignature.team_leader_login_id == _norm_scope(team_leader_login_id),
        )
        .first()
    )
    return signature_revisions.active(db,root)


def _leader_display_name(db: Session, leader_login: str) -> str:
    user = db.query(User).filter(User.login_id == leader_login).first()
    if user and user.name:
        return user.name.strip()
    dash = leader_login.find("-")
    return leader_login[dash + 1 :] if dash >= 0 else leader_login


def _workers_payload_for_team_leader(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
    leader_login: str,
    batch: int,
) -> list[dict[str, Any]]:
    from app.modules.functional_eval import service

    rows = service._site_attendance_workers(db, period, site_code)
    rows = [row for row in rows if (row.evaluation_batch or 0) == batch]
    manager_login = service._manager_login_for_site(db, site_code)
    team_leader_logins = service._collect_team_leader_evaluator_logins(rows, manager_login)
    leader_login = leader_login.strip()
    members = [
        r
        for r in rows
        if (r.assigned_evaluator_login_id or "").strip() == leader_login and (r.evaluation_batch or 0) == batch
    ]
    assess_map = service._assessments_map(db, [r.id for r in members])
    return [
        service.serialize_worker(
            db,
            row,
            assessments=assess_map.get(row.id, {}),
            team_leader_logins=team_leader_logins,
        )
        for row in members
    ]


def _build_site_report_sections(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
    batch: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from app.modules.functional_eval import service

    rows = service._site_attendance_workers(db, period, site_code)
    rows = [row for row in rows if (row.evaluation_batch or 0) == batch]
    manager_login = service._manager_login_for_site(db, site_code)
    team_leader_logins = sorted(service._collect_team_leader_evaluator_logins(rows, manager_login))
    assess_map = service._assessments_map(db, [r.id for r in rows])
    sections: list[dict[str, Any]] = []
    for leader in team_leader_logins:
        members = [
            r
            for r in rows
            if (r.assigned_evaluator_login_id or "").strip() == leader and (r.evaluation_batch or 0) == batch
        ]
        team_sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_LEADER,
            site_code=site_code,
            team_leader_login_id=leader,
        )
        mgr_sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_MANAGER_APPROVE,
            site_code=site_code,
            team_leader_login_id=leader,
        )
        sections.append(
            {
                "leader_label": _leader_display_name(db, leader),
                "leader_login_id": leader,
                "workers": [
                    service.serialize_worker(
                        db,
                        row,
                        assessments=assess_map.get(row.id, {}),
                        team_leader_logins=set(team_leader_logins),
                    )
                    for row in members
                ],
                "team_leader_signed_at": format_kst_datetime_short(team_sig.signed_at) if team_sig else None,
                "manager_approved_at": format_kst_datetime_short(mgr_sig.signed_at) if mgr_sig else None,
            }
        )
    direct_workers = [
        service.serialize_worker(
            db,
            row,
            assessments=assess_map.get(row.id, {}),
            team_leader_logins=set(team_leader_logins),
        )
        for row in rows
        if (row.evaluation_batch or 0) == batch
        and service._worker_eval_assignment(db, row, team_leader_logins=set(team_leader_logins))
        in (service.EVAL_ASSIGNMENT_DIRECT, service.EVAL_ASSIGNMENT_TEAM_LEADER)
    ]
    return sections, direct_workers


def _build_signature_pdf(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    batch: int,
    stage: str,
    user: User,
    site_code: str | None,
    team_leader_login_id: str | None,
    signature_data: str,
    signed_at,
    worker_scope_json: dict | None,
) -> bytes:
    login_id = (user.login_id or "").strip()
    signer_name = (user.name or "").strip() or login_id
    site_name = _site_display_name(db, site_code) if site_code else None
    scope = worker_scope_json or {}
    report_period_title = period.title + (f" · 추가 평가 {batch}차" if batch > 0 and site_code and additional_rounds.requires_round_scope(db,period.id,site_code) else "")
    if scope.get('signature_revision_no'):report_period_title+=f" · 재서명 {scope['signature_revision_no']}차"

    if stage == STAGE_TEAM_LEADER:
        leader_login = (team_leader_login_id or login_id).strip()
        workers = _workers_payload_for_team_leader(db, period, site_code or "", leader_login, batch)
        leader_name = signer_name
        header = _build_report_header_for_site(db, site_code or "", leader_name, is_manager=False)
        return generate_team_completion_report_pdf(
            period_title=report_period_title,
            site_name=site_name or site_code or "",
            team_leader_name=leader_name,
            team_leader_login=leader_login,
            workers=workers,
            signature_data=signature_data,
            signed_at=signed_at,
            site_full_name=header["site_full_name"],
            role_line=header["role_line"],
            grade_review_metadata={
                k: scope[k]
                for k in (
                    "grade_distribution_snapshot",
                    "s_over_limit_reason",
                    "no_c_grade_reason",
                    "s_ratio",
                    "s_count",
                    "c_count",
                )
                if k in scope
            },
        )

    if stage == STAGE_TEAM_MANAGER_APPROVE:
        leader_login = (team_leader_login_id or "").strip()
        team_sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_LEADER,
            site_code=site_code,
            team_leader_login_id=leader_login,
        )
        if team_sig is None:
            raise ValueError("TEAM_LEADER_NOT_SIGNED")
        workers = _workers_payload_for_team_leader(db, period, site_code or "", leader_login, batch)
        header = _build_report_header_for_site(db, site_code or "", team_sig.signer_name, is_manager=False)
        return generate_team_completion_report_pdf(
            period_title=report_period_title,
            site_name=site_name or site_code or "",
            team_leader_name=team_sig.signer_name,
            team_leader_login=leader_login,
            workers=workers,
            signature_data=team_sig.signature_data,
            signed_at=team_sig.signed_at,
            manager_approval={
                "signer_name": signer_name,
                "signature_data": signature_data,
                "signed_at": format_kst_datetime_short(signed_at),
            },
            site_full_name=header["site_full_name"],
            role_line=header["role_line"],
        )

    if stage == STAGE_SITE:
        sections, direct_workers = _build_site_report_sections(db, period, site_code or "", batch)
        header = _build_report_header_for_site(db, site_code or "", signer_name, is_manager=True)
        return generate_site_completion_report_pdf(
            period_title=report_period_title,
            site_name=site_name or site_code or "",
            site_code=site_code or "",
            manager_name=signer_name,
            manager_login=login_id,
            team_sections=sections,
            direct_workers=direct_workers,
            signature_data=signature_data,
            signed_at=signed_at,
            site_full_name=header["site_full_name"],
            role_line=header["role_line"],
        )

    if stage == STAGE_HQ_OFFICER:
        site_codes = scope.get("site_codes") or ([site_code] if site_code else [])
        return generate_hq_review_report_pdf(
            period_title=report_period_title,
            site_summaries=[{"site_code": c} for c in site_codes],
            officer_comment=str(scope.get("officer_comment") or ""),
            director_comment="",
            signature_data=signature_data,
            signer_name=signer_name,
            signed_at=signed_at,
            report_title=REPORT_TITLE,
        )

    if stage == STAGE_HQ:
        site_codes = scope.get("site_codes") or ([site_code] if site_code else [])
        return generate_hq_review_report_pdf(
            period_title=report_period_title,
            site_summaries=[{"site_code": c} for c in site_codes],
            officer_comment=str(scope.get("officer_comment") or ""),
            director_comment=str(scope.get("director_comment") or ""),
            signature_data=signature_data,
            signer_name=signer_name,
            signed_at=signed_at,
            report_title=REPORT_TITLE,
        )

    if stage == STAGE_CEO:
        hq_note = str(scope.get("director_comment") or scope.get("officer_comment") or "")
        return generate_ceo_final_report_pdf(
            period_title=report_period_title,
            site_count=len(scope.get("site_codes") or []),
            site_label=f"{site_name} ({site_code})" if site_code else None,
            hq_review_note=hq_note,
            signature_data=signature_data,
            signer_name=signer_name,
            signed_at=signed_at,
        )

    raise ValueError(f"UNKNOWN_SIGNATURE_STAGE:{stage}")


def _persist_signature(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    batch: int,
    stage: str,
    user: User,
    signature_data: str,
    site_code: str | None,
    team_leader_login_id: str | None,
    scope_label: str,
    worker_scope_json: dict | None,
    request: Request | None,
) -> FunctionalEvalSignature:
    if _signature_exists(
        db,
        period_id=period.id,
        batch=batch,
        stage=stage,
        site_code=site_code,
        team_leader_login_id=team_leader_login_id,
    ):
        raise ValueError("SIGNATURE_ALREADY_EXISTS")
    root=db.query(FunctionalEvalSignature).filter_by(period_id=period.id,evaluation_batch=batch,stage=stage,site_code=_norm_scope(site_code),team_leader_login_id=_norm_scope(team_leader_login_id)).first()
    if root is not None and not signature_revisions.policy(db)['enabled']:raise ValueError('SIGNATURE_REVISION_DISABLED')
    if root is not None:
        from sqlalchemy import func
        version_number=(db.query(func.max(signature_revisions.Version.revision_no)).filter_by(root_signature_id=root.id).scalar()or 0)+1
        worker_scope_json={**(worker_scope_json or{}),'signature_revision_no':version_number}
    sig_hash, _ = validate_signature_data(signature_data)
    now = utc_now()
    login_id = (user.login_id or "").strip()
    signer_name = (user.name or "").strip() or login_id
    ip, ua = _signer_meta(request)
    pdf = _build_signature_pdf(
        db,
        period=period,
        batch=batch,
        stage=stage,
        user=user,
        site_code=site_code,
        team_leader_login_id=team_leader_login_id,
        signature_data=signature_data,
        signed_at=now,
        worker_scope_json=worker_scope_json,
    )
    prefix = f"fe_{stage}_{site_code or 'hq'}_{batch}_{login_id}"
    doc_path = save_pdf_document(prefix=_safe_prefix(prefix), pdf_bytes=pdf)
    values = dict(
        period_id=period.id,
        evaluation_batch=batch,
        stage=stage,
        site_code=_norm_scope(site_code),
        team_leader_login_id=_norm_scope(team_leader_login_id),
        signer_user_id=user.id,
        signer_login_id=login_id,
        signer_name=signer_name,
        scope_label=scope_label,
        worker_scope_json=worker_scope_json,
        signature_data=signature_data,
        signature_hash=sig_hash,
        signed_at=now,
        signer_ip=ip,
        signer_user_agent=ua,
        signed_document_path=doc_path,
    )
    row=signature_revisions.create_version(db,root,values)if root is not None else FunctionalEvalSignature(**values)
    db.add(row)
    db.flush()
    return row


def _safe_prefix(text: str) -> str:
    from app.modules.functional_eval.signature_service import _safe_filename_part

    return _safe_filename_part(text)


def assert_worker_not_signature_locked(
    db: Session,
    user: User,
    worker: FunctionalEvalWorker,
) -> None:
    """팀장 서명 후 해당 배치·담당 근로자 수정 차단."""
    from app.modules.functional_eval import service

    from .site_evaluator_access import is_site_evaluator
    if not is_site_evaluator(user):
        if getattr(user.role,"value",user.role)=="SITE":raise ValueError("SITE_MISMATCH")
        return
    login_id = (user.login_id or "").strip()
    site_code = worker.site_code
    batch = worker.evaluation_batch or 0
    if service._is_primary_site_evaluator(db, user, site_code):
        site_sig = _signature_exists(
            db,
            period_id=worker.period_id,
            batch=batch,
            stage=STAGE_SITE,
            site_code=site_code,
            team_leader_login_id="",
        )
        if site_sig is not None:
            raise ValueError("EVALUATION_SIGNATURE_LOCKED")
        return
    assigned = (worker.assigned_evaluator_login_id or "").strip()
    if assigned != login_id:
        return
    team_sig = _signature_exists(
        db,
        period_id=worker.period_id,
        batch=batch,
        stage=STAGE_TEAM_LEADER,
        site_code=site_code,
        team_leader_login_id=login_id,
    )
    if team_sig is not None:
        raise ValueError("EVALUATION_SIGNATURE_LOCKED")



def get_team_signoff_status(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    *, batch=None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service

    site_code = service._site_code_for_user(user, db)
    login_id = (user.login_id or "").strip()
    if service._is_primary_site_evaluator(db, user, site_code):
        raise ValueError("MANAGER_NOT_TEAM_LEADER")
    workers = service.list_workers_for_user(db, user, period,batch=batch)
    batch = max((w.get("evaluation_batch") or 0 for w in workers), default=0) if batch is None else batch
    approval = additional_rounds.get_approval(db,period.id,site_code,batch=batch)
    editable = approval_workflow.is_site_evaluation_editable(approval.status if approval else "IN_PROGRESS")
    incomplete = [w for w in workers if not service._is_fully_evaluated(w)]
    grade_review = compute_grade_inflation_review(workers)
    existing = _signature_exists(
        db,
        period_id=period.id,
        batch=batch,
        stage=STAGE_TEAM_LEADER,
        site_code=site_code,
        team_leader_login_id=login_id,
    )
    return {
        "evaluation_batch": batch,
        "evaluation_batch_label": batch_label(batch),
        "assigned_total": len(workers),
        "incomplete_count": len(incomplete),
        "can_sign": editable and len(workers) > 0 and len(incomplete) == 0 and existing is None,
        "signed": existing is not None,
        "signed_at": existing.signed_at.isoformat() if existing else None,
        "signed_at_label": format_kst_datetime_label(existing.signed_at) if existing else None,
        "signature_id": existing.id if existing else None,
        **grade_review,
    }


def submit_team_signoff(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    *,
    signature_data: str,
    s_over_limit_reason: str | None = None,
    no_c_grade_reason: str | None = None,
    expected_batch: int|None=None,
    expected_scope_sha256: str|None=None,
    request: Request | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service

    assert_consent_signed(db, user)
    site_code = service._site_code_for_user(user, db)
    selected_batch,_=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_scope_sha256,current_only=False,create=True)
    approval_workflow.assert_site_editable(db,period.id,site_code,batch=selected_batch)
    status = get_team_signoff_status(db, user, period,batch=selected_batch)
    if not status["can_sign"]:
        if status["signed"]:
            raise ValueError("SIGNATURE_ALREADY_EXISTS")
        raise ValueError("INCOMPLETE_EVALUATIONS")
    site_code = service._site_code_for_user(user, db)
    login_id = (user.login_id or "").strip()
    batch = status["evaluation_batch"]
    workers = service.list_workers_for_user(db, user, period,batch=selected_batch)
    grade_review = compute_grade_inflation_review(workers)
    validate_grade_inflation_reasons(
        grade_review,
        s_over_limit_reason=s_over_limit_reason,
        no_c_grade_reason=no_c_grade_reason,
    )
    worker_ids = [w["id"] for w in workers]
    scope = f"{batch_label(batch)} · 팀원 {len(workers)}명"
    review_meta = build_grade_review_metadata(
        grade_review,
        s_over_limit_reason=s_over_limit_reason,
        no_c_grade_reason=no_c_grade_reason,
    )
    worker_scope = {"worker_ids": worker_ids, "batch": batch, **review_meta}
    row = _persist_signature(
        db,
        period=period,
        batch=batch,
        stage=STAGE_TEAM_LEADER,
        user=user,
        signature_data=signature_data,
        site_code=site_code,
        team_leader_login_id=login_id,
        scope_label=scope,
        worker_scope_json=worker_scope,
        request=request,
    )
    db.commit()
    db.refresh(row)
    return serialize_signature(row)


def all_team_leaders_signed(db: Session, period: FunctionalEvalPeriod, site_code: str, batch: int) -> bool:
    from app.modules.functional_eval import service

    rows = service._site_attendance_workers(db, period, site_code)
    rows = [row for row in rows if (row.evaluation_batch or 0) == batch]
    manager_login = service._manager_login_for_site(db, site_code)
    team_leader_logins = service._collect_team_leader_evaluator_logins(rows, manager_login)
    if not team_leader_logins:
        return True
    for leader_login in team_leader_logins:
        sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_LEADER,
            site_code=site_code,
            team_leader_login_id=leader_login,
        )
        if sig is None:
            return False
    return True


def all_team_reports_manager_approved(db: Session, period: FunctionalEvalPeriod, site_code: str, batch: int) -> bool:
    from app.modules.functional_eval import service

    rows = service._site_attendance_workers(db, period, site_code)
    rows = [row for row in rows if (row.evaluation_batch or 0) == batch]
    manager_login = service._manager_login_for_site(db, site_code)
    team_leader_logins = service._collect_team_leader_evaluator_logins(rows, manager_login)
    if not team_leader_logins:
        return True
    for leader_login in team_leader_logins:
        sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_MANAGER_APPROVE,
            site_code=site_code,
            team_leader_login_id=leader_login,
        )
        if sig is None:
            return False
    return True


def _grade_flags_from_signature(sig: FunctionalEvalSignature | None) -> dict[str, Any]:
    if sig is None or not sig.worker_scope_json:
        return {}
    scope = sig.worker_scope_json
    snapshot = scope.get("grade_distribution_snapshot") or {}
    s_ratio = scope.get("s_ratio")
    if s_ratio is None:
        s_ratio = snapshot.get("s_ratio")
    c_count = scope.get("c_count")
    if c_count is None:
        c_count = snapshot.get("c_count")
    return {
        "grade_s_ratio": s_ratio,
        "grade_c_count": c_count,
        "grade_s_over_limit": bool(scope.get("s_over_limit_reason")),
        "grade_no_c_grade": bool(scope.get("no_c_grade_reason")),
    }


def list_team_leader_report_status(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
    batch: int,
) -> list[dict[str, Any]]:
    from app.modules.functional_eval import service

    rows = service._site_attendance_workers(db, period, site_code)
    rows = [row for row in rows if (row.evaluation_batch or 0) == batch]
    manager_login = service._manager_login_for_site(db, site_code)
    team_leader_logins = sorted(service._collect_team_leader_evaluator_logins(rows, manager_login))
    result: list[dict[str, Any]] = []
    for leader in team_leader_logins:
        member_count = sum(
            1
            for r in rows
            if (r.assigned_evaluator_login_id or "").strip() == leader and (r.evaluation_batch or 0) == batch
        )
        team_sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_LEADER,
            site_code=site_code,
            team_leader_login_id=leader,
        )
        mgr_sig = _signature_exists(
            db,
            period_id=period.id,
            batch=batch,
            stage=STAGE_TEAM_MANAGER_APPROVE,
            site_code=site_code,
            team_leader_login_id=leader,
        )
        result.append(
            {
                "team_leader_login_id": leader,
                "team_leader_name": _leader_display_name(db, leader),
                "team_worker_count": member_count,
                "team_leader_signed": team_sig is not None,
                "team_leader_signed_at": format_kst_datetime_short(team_sig.signed_at) if team_sig else None,
                "team_leader_signed_at_label": format_kst_datetime_label(team_sig.signed_at) if team_sig else None,
                "can_manager_reject": team_sig is not None and signature_revisions.policy(db)['enabled'],
                "team_leader_signature_id": team_sig.id if team_sig else None,
                "manager_approved": mgr_sig is not None,
                "manager_approved_at": format_kst_datetime_short(mgr_sig.signed_at) if mgr_sig else None,
                "manager_approved_at_label": format_kst_datetime_label(mgr_sig.signed_at) if mgr_sig else None,
                "can_manager_approve": False,
                "manager_approval_signature_id": mgr_sig.id if mgr_sig else None,
                **_grade_flags_from_signature(team_sig),
            }
        )
    return result


def _delete_signature_record(db,row):
    raise ValueError('SIGNED_ROUND_REVISION_REQUIRED')

def reject_team_leader_report(db,user,period,site_code,team_leader_login_id,*,reject_note=None,request_id=None,expected_batch=None,expected_scope_sha256=None):
    return signature_revisions.reject(db,user,period,site_code,stage='TEAM',note=reject_note,request_id=request_id,expected_batch=expected_batch,expected_sha=expected_scope_sha256,leader_login=team_leader_login_id)


def submit_team_manager_approval(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    team_leader_login_id: str,
    *,
    signature_data: str,
    expected_batch: int|None=None,
    expected_scope_sha256: str|None=None,
    request: Request | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service

    assert_consent_signed(db, user)
    if not service._is_primary_site_evaluator(db, user, site_code):
        raise ValueError("MANAGER_ONLY")
    selected_batch,_=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_scope_sha256,current_only=False,create=True)
    approval_workflow.assert_site_editable(db,period.id,site_code,batch=selected_batch)
    leader_login = team_leader_login_id.strip()
    batch = selected_batch
    team_sig = _signature_exists(
        db,
        period_id=period.id,
        batch=batch,
        stage=STAGE_TEAM_LEADER,
        site_code=site_code,
        team_leader_login_id=leader_login,
    )
    if team_sig is None:
        raise ValueError("TEAM_LEADER_NOT_SIGNED")
    leader_name = _leader_display_name(db, leader_login)
    scope = f"{batch_label(batch)} · {leader_name} 팀장 평가완료보고서 승인"
    row = _persist_signature(
        db,
        period=period,
        batch=batch,
        stage=STAGE_TEAM_MANAGER_APPROVE,
        user=user,
        signature_data=signature_data,
        site_code=site_code,
        team_leader_login_id=leader_login,
        scope_label=scope,
        worker_scope_json={"team_leader_login_id": leader_login, "batch": batch},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return serialize_signature(row)


def active_site_batches(db: Session, period: FunctionalEvalPeriod, site_code: str) -> list[int]:
    from app.modules.functional_eval import service

    rows = service._site_attendance_workers(db, period, site_code)
    current=additional_rounds.active_batch(db,period.id,site_code)
    if current:return [current]
    batches = sorted({w.evaluation_batch or 0 for w in rows})
    return batches or [0]


def _site_workers_payloads_for_batch(
    db: Session,
    period: FunctionalEvalPeriod,
    site_code: str,
    batch: int,
) -> list[dict[str, Any]]:
    from app.modules.functional_eval import service

    return service.site_worker_payloads_for_batch(db, period, site_code, batch)


def submit_site_approval_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    *,
    signature_data: str,
    expected_batch: int|None=None,
    expected_scope_sha256: str|None=None,
    s_over_limit_reason: str | None = None,
    no_c_grade_reason: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service

    assert_consent_signed(db, user)
    approval_batch,_=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_scope_sha256,current_only=False,create=True)
    summary = service.serialize_site_approval_summary(db, period, site_code,batch=approval_batch if additional_rounds.requires_round_scope(db,period.id,site_code)else None)
    batch = approval_batch if additional_rounds.requires_round_scope(db,period.id,site_code)else max(active_site_batches(db, period, site_code))
    if not all_team_leaders_signed(db, period, site_code, batch):
        raise ValueError("TEAM_LEADERS_NOT_SIGNED")
    if summary["incomplete_count"] > 0 or not summary['site_total_workers']:
        raise ValueError("INCOMPLETE_EVALUATIONS")
    workers = _site_workers_payloads_for_batch(db, period, site_code, batch)
    grade_review = compute_grade_inflation_review(workers)
    validate_grade_inflation_reasons(
        grade_review,
        s_over_limit_reason=s_over_limit_reason,
        no_c_grade_reason=no_c_grade_reason,
    )
    review_meta = build_grade_review_metadata(
        grade_review,
        s_over_limit_reason=s_over_limit_reason,
        no_c_grade_reason=no_c_grade_reason,
    )
    scope = f"{batch_label(batch)} · 현장 전체 {summary['site_total_workers']}명"
    _persist_signature(
        db,
        period=period,
        batch=batch,
        stage=STAGE_SITE,
        user=user,
        signature_data=signature_data,
        site_code=site_code,
        team_leader_login_id=SCOPE_EMPTY,
        scope_label=scope,
        worker_scope_json={
            "site_code": site_code,
            "batch": batch,
            "worker_count": summary["site_total_workers"],
            "worker_ids":[worker['id']for worker in workers],
            **review_meta,
        },
        request=request,
    )
    approval = approval_workflow.submit_site_approval(
        db,
        period=period,
        site_code=site_code,
        user=user,
        incomplete_count=summary["incomplete_count"],
        batch=approval_batch,
    )
    return approval


def self_reject_site_approval(db,user,period,site_code,*,reject_note=None,request_id=None,expected_batch=None,expected_scope_sha256=None):
    return signature_revisions.reject(db,user,period,site_code,stage='SITE',note=reject_note,request_id=request_id,expected_batch=expected_batch,expected_sha=expected_scope_sha256)


def submit_supplemental_site_signoff(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    *,
    signature_data: str,
    request: Request | None = None,
) -> dict[str, Any]:
    """추가평가 — 기존 승인 상태는 유지, 배치별 별도 서명."""
    from app.modules.functional_eval import service

    if additional_rounds.requires_round_scope(db,period.id,site_code):raise ValueError("EVALUATION_ROUND_CHANGED")
    assert_consent_signed(db, user)
    if not service._is_primary_site_evaluator(db, user, site_code):
        raise ValueError("MANAGER_ONLY")
    batches = active_site_batches(db, period, site_code)
    supplemental = [b for b in batches if b > 0]
    if not supplemental:
        raise ValueError("NO_SUPPLEMENTAL_BATCH")
    target_batch = max(supplemental)
    if _signature_exists(
        db,
        period_id=period.id,
        batch=target_batch,
        stage=STAGE_SITE,
        site_code=site_code,
        team_leader_login_id=SCOPE_EMPTY,
    ):
        raise ValueError("SIGNATURE_ALREADY_EXISTS")
    rows = [w for w in service._site_attendance_workers(db, period, site_code) if (w.evaluation_batch or 0) == target_batch]
    assess_map = service._assessments_map(db, [r.id for r in rows])
    incomplete = 0
    for row in rows:
        payload = service.serialize_worker(db, row, assessments=assess_map.get(row.id, {}))
        if not service._is_fully_evaluated(payload):
            incomplete += 1
    if incomplete > 0:
        raise ValueError("INCOMPLETE_EVALUATIONS")
    if not all_team_leaders_signed(db, period, site_code, target_batch):
        raise ValueError("TEAM_LEADERS_NOT_SIGNED")
    scope = f"{batch_label(target_batch)} · 추가평가 {len(rows)}명"
    row = _persist_signature(
        db,
        period=period,
        batch=target_batch,
        stage=STAGE_SITE,
        user=user,
        signature_data=signature_data,
        site_code=site_code,
        team_leader_login_id=SCOPE_EMPTY,
        scope_label=scope,
        worker_scope_json={"worker_ids": [r.id for r in rows], "batch": target_batch},
        request=request,
    )
    db.commit()
    db.refresh(row)
    return serialize_signature(row)


def approve_hq_officer_site_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    *,
    signature_data: str,
    expected_batch: int|None=None,
    expected_scope_sha256: str|None=None,
    defer_commit:bool=False,
    officer_comment: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    approval_workflow.assert_hq_officer_approver(user)
    assert_consent_signed(db, user)
    approval_workflow.assert_hq_approval_open(period)
    site_code = site_code.strip()
    batch,row=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_scope_sha256,current_only=False)
    if row.status!=approval_workflow.APPROVAL_STATUS_SITE_APPROVED and not(not batch and row.evaluation_completed_at is not None and row.status in {'IN_PROGRESS','REJECTED'}):raise ValueError('INVALID_APPROVAL_TRANSITION')
    scope = f"현장 {site_code} · 담당 검토"
    _persist_signature(
        db,
        period=period,
        batch=batch,
        stage=STAGE_HQ_OFFICER,
        user=user,
        signature_data=signature_data,
        site_code=site_code,
        team_leader_login_id="",
        scope_label=scope,
        worker_scope_json={
            "site_codes": [site_code],
            "officer_comment": (officer_comment or "").strip(),
        },
        request=request,
    )
    approval = approval_workflow.approve_hq_officer(
        db,
        period=period,
        site_code=site_code,
        user=user,
        officer_comment=officer_comment,
        batch=batch,
        commit=not defer_commit,
    )
    return approval


def approve_hq_officer_all_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    *,
    signature_data: str,
    expected_rounds: list[dict]|None=None,
    officer_comment: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    approval_workflow.assert_hq_officer_approver(user)
    assert_consent_signed(db, user)
    approval_workflow.assert_hq_approval_open(period)
    pending = approval_workflow.list_pending_hq_officer_approvals(db, period)
    if not pending:
        raise ValueError("NO_PENDING_APPROVALS")
    selected=_run_selected_rounds(db,period,pending,expected_rounds,lambda item:approve_hq_officer_site_with_signature(db,user,period,item['site_code'],signature_data=signature_data,officer_comment=officer_comment,expected_batch=item['evaluation_batch'],expected_scope_sha256=item['scope_sha256'],defer_commit=True,request=request))
    if selected is not None:return selected
    if _signature_exists(
        db,
        period_id=period.id,
        batch=0,
        stage=STAGE_HQ_OFFICER,
        site_code="",
        team_leader_login_id="",
    ):
        raise ValueError("SIGNATURE_ALREADY_EXISTS")
    site_codes = [item["site_code"] for item in pending]
    scope = f"전 현장 {len(site_codes)}개소 · 담당 일괄 검토"
    _persist_signature(
        db,
        period=period,
        batch=0,
        stage=STAGE_HQ_OFFICER,
        user=user,
        signature_data=signature_data,
        site_code="",
        team_leader_login_id="",
        scope_label=scope,
        worker_scope_json={
            "site_codes": site_codes,
            "officer_comment": (officer_comment or "").strip(),
        },
        request=request,
    )
    results = []
    for item in pending:
        code = item["site_code"]
        results.append(
            approval_workflow.approve_hq_officer(
                db,
                period=period,
                site_code=code,
                user=user,
                officer_comment=officer_comment,
            )
        )
    db.commit()
    return {"approved_count": len(results), "site_codes": site_codes}


def approve_hq_director_site_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    *,
    signature_data: str,
    expected_batch: int|None=None,
    expected_scope_sha256: str|None=None,
    defer_commit:bool=False,
    director_comment: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    approval_workflow.assert_hq_director_approver(user)
    assert_consent_signed(db, user)
    approval_workflow.assert_hq_approval_open(period)
    site_code = site_code.strip()
    batch,row=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_scope_sha256,current_only=False)
    if row.status!=approval_workflow.APPROVAL_STATUS_HQ_OFFICER_APPROVED:raise ValueError('INVALID_APPROVAL_TRANSITION')
    officer_comment = row.hq_officer_comment or ""
    scope = f"현장 {site_code} · 실장 최종 승인"
    _persist_signature(
        db,
        period=period,
        batch=batch,
        stage=STAGE_HQ,
        user=user,
        signature_data=signature_data,
        site_code=site_code,
        team_leader_login_id="",
        scope_label=scope,
        worker_scope_json={
            "site_codes": [site_code],
            "officer_comment": officer_comment,
            "director_comment": (director_comment or "").strip(),
        },
        request=request,
    )
    approval = approval_workflow.approve_hq_director(
        db, period=period, site_code=site_code, user=user,batch=batch,commit=not defer_commit
    )
    return approval


def approve_hq_director_all_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    *,
    signature_data: str,
    expected_rounds: list[dict]|None=None,
    director_comment: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    approval_workflow.assert_hq_director_approver(user)
    assert_consent_signed(db, user)
    approval_workflow.assert_hq_approval_open(period)
    pending = approval_workflow.list_pending_hq_director_approvals(db, period)
    if not pending:
        raise ValueError("NO_PENDING_APPROVALS")
    selected=_run_selected_rounds(db,period,pending,expected_rounds,lambda item:approve_hq_director_site_with_signature(db,user,period,item['site_code'],signature_data=signature_data,director_comment=director_comment,expected_batch=item['evaluation_batch'],expected_scope_sha256=item['scope_sha256'],defer_commit=True,request=request))
    if selected is not None:return selected
    if _signature_exists(
        db,
        period_id=period.id,
        batch=0,
        stage=STAGE_HQ,
        site_code="",
        team_leader_login_id="",
    ):
        raise ValueError("SIGNATURE_ALREADY_EXISTS")
    site_codes = [item["site_code"] for item in pending]
    scope = f"전 현장 {len(site_codes)}개소 · 실장 일괄 승인"
    _persist_signature(
        db,
        period=period,
        batch=0,
        stage=STAGE_HQ,
        user=user,
        signature_data=signature_data,
        site_code="",
        team_leader_login_id="",
        scope_label=scope,
        worker_scope_json={
            "site_codes": site_codes,
            "director_comment": (director_comment or "").strip(),
        },
        request=request,
    )
    results = []
    for item in pending:
        code = item["site_code"]
        results.append(
            approval_workflow.approve_hq_director(db, period=period, site_code=code, user=user)
        )
    db.commit()
    return {"approved_count": len(results), "site_codes": site_codes}


def approve_hq_all_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    *,
    signature_data: str,
    expected_rounds: list[dict]|None=None,
    officer_comment: str | None = None,
    director_comment: str | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    """하위 호환 — 로그인 역할에 따라 담당/실장 일괄 승인."""
    role = approval_workflow.resolve_hq_approval_role(user)
    if role in {"officer", "admin"} and approval_workflow.list_pending_hq_officer_approvals(db, period):
        return approve_hq_officer_all_with_signature(
            db,
            user,
            period,
            signature_data=signature_data,
            officer_comment=officer_comment or director_comment,
            expected_rounds=expected_rounds,
            request=request,
        )
    return approve_hq_director_all_with_signature(
        db,
        user,
        period,
        signature_data=signature_data,
        director_comment=director_comment,
        expected_rounds=expected_rounds,
        request=request,
    )



def approve_ceo_site_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    *,
    signature_data: str,
    expected_batch: int|None=None,
    expected_scope_sha256: str|None=None,
    defer_commit:bool=False,
    request: Request | None = None,
) -> dict[str, Any]:
    """Approve exactly one already HQ-approved site with its own immutable signature."""
    approval_workflow.assert_ceo_approver(user)
    assert_consent_signed(db, user)
    approval_workflow.assert_hq_approval_open(period)
    site_code = site_code.strip()
    batch,row=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_scope_sha256,current_only=False)
    if row is None or row.status != approval_workflow.APPROVAL_STATUS_HQ_APPROVED:
        raise ValueError("INVALID_APPROVAL_TRANSITION")
    # The existing base64/size policy is retained; decode before any DB/file write.
    _, image_bytes = validate_signature_data(signature_data)
    import io
    from PIL import Image, UnidentifiedImageError
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.format != "PNG":
                raise ValueError("invalid_signature_base64")
            image.convert("RGBA")
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise ValueError("invalid_signature_base64") from exc
    # Conditional no-op UPDATE acquires the existing SQLite write transaction before
    # creating the PDF. A simultaneous second approval observes rowcount 0 after
    # the first commits and cannot create another signature/PDF.
    model=type(row)
    ready = db.query(model).filter(
        model.id == row.id,
        model.status == approval_workflow.APPROVAL_STATUS_HQ_APPROVED,
    ).update({model.status: approval_workflow.APPROVAL_STATUS_HQ_APPROVED}, synchronize_session=False)
    if ready != 1:
        raise ValueError("INVALID_APPROVAL_TRANSITION")
    _persist_signature(
        db, period=period, batch=batch, stage=STAGE_CEO, user=user,
        signature_data=signature_data, site_code=site_code, team_leader_login_id="",
        scope_label=f"현장 {site_code} · 대표 최종 승인",
        worker_scope_json={"site_codes": [site_code]}, request=request,
    )
    return approval_workflow.approve_ceo(db, period=period, site_code=site_code, user=user,batch=batch,commit=not defer_commit)

def approve_ceo_all_with_signature(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    *,
    signature_data: str,
    expected_rounds: list[dict]|None=None,
    request: Request | None = None,
) -> dict[str, Any]:
    approval_workflow.assert_ceo_approver(user)
    assert_consent_signed(db, user)
    approval_workflow.assert_hq_approval_open(period)
    pending = approval_workflow.list_pending_ceo_approvals(db, period)
    if not pending:
        raise ValueError("NO_PENDING_APPROVALS")
    selected=_run_selected_rounds(db,period,pending,expected_rounds,lambda item:approve_ceo_site_with_signature(db,user,period,item['site_code'],signature_data=signature_data,expected_batch=item['evaluation_batch'],expected_scope_sha256=item['scope_sha256'],defer_commit=True,request=request))
    if selected is not None:return selected
    if _signature_exists(
        db,
        period_id=period.id,
        batch=0,
        stage=STAGE_CEO,
        site_code="",
        team_leader_login_id="",
    ):
        raise ValueError("SIGNATURE_ALREADY_EXISTS")
    site_codes = [item["site_code"] for item in pending]
    scope = f"전 현장 {len(site_codes)}개소 최종승인"
    _persist_signature(
        db,
        period=period,
        batch=0,
        stage=STAGE_CEO,
        user=user,
        signature_data=signature_data,
        site_code="",
        team_leader_login_id="",
        scope_label=scope,
        worker_scope_json={"site_codes": site_codes},
        request=request,
    )
    results = []
    for item in pending:
        code = item["site_code"]
        results.append(
            approval_workflow.approve_ceo(db, period=period, site_code=code, user=user)
        )
    db.commit()
    return {"approved_count": len(results), "site_codes": site_codes}


def _run_selected_rounds(db,period,pending,expected,approve):
    if expected is None:
        if any(item.get('round_scope_required')for item in pending):raise ValueError('EVALUATION_ROUND_CHANGED')
        return None
    offered={(item['site_code'],int(item.get('evaluation_batch')or 0)):item for item in pending};seen=set()
    if not expected:raise ValueError('EVALUATION_ROUND_CHANGED')
    for item in expected:
        key=(item['site_code'],item['evaluation_batch']);original=offered.get(key)
        if key in seen or original is None or original.get('target_sha256')!=item['scope_sha256']:raise ValueError('EVALUATION_ROUND_CHANGED')
        seen.add(key)
    try:
        results=[approve(item)for item in expected];db.commit()
        return {'approved_count':len(results),'site_codes':[item['site_code']for item in expected],'rounds':[{'site_code':item['site_code'],'evaluation_batch':item['evaluation_batch'],'approval':result}for item,result in zip(expected,results)],'atomic':True}
    except BaseException:db.rollback();raise


def list_my_signatures(db: Session, user: User, period: FunctionalEvalPeriod, *, batch=None) -> list[dict[str, Any]]:
    login_id = (user.login_id or "").strip()
    rows=signature_revisions.all_records(db,period.id,signer_id=user.id,batch=batch)
    consent = db.query(FunctionalEvalConsent).filter(FunctionalEvalConsent.user_id == user.id).first()
    items = [signature_revisions.payload(db,r) for r in rows]
    if consent:
        items.append(
            {
                "id": f"consent-{consent.id}",
                "consent": True,
                "stage_label": "최초 로그인 동의",
                "signer_login_id": consent.login_id,
                "signed_at": consent.signed_at.isoformat(),
                "signed_at_label": format_kst_datetime_label(consent.signed_at),
                "has_document": bool(consent.signed_document_path),
            }
        )
    return items


def get_signature_document_path(db: Session, user: User, signature_id: int|str) -> str:
    row = signature_revisions.resolve(db,signature_id)
    if row is None:
        raise ValueError("NOT_FOUND")
    from . import service
    from .site_evaluator_access import is_site_evaluator
    manager_for_team = (is_site_evaluator(user)
                        and row.stage in {STAGE_TEAM_LEADER,STAGE_TEAM_MANAGER_APPROVE}
                        and bool(row.site_code)
                        and service._site_code_for_user(user,db) == row.site_code
                        and service._is_primary_site_evaluator(db,user,row.site_code))
    if row.signer_user_id != user.id and not manager_for_team and user.role not in {
        Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN,
    }:
        raise ValueError('FORBIDDEN')
    if not row.signed_document_path:
        raise ValueError("NO_DOCUMENT")
    return row.signed_document_path



def get_consent_document_path(db: Session, user: User) -> str:
    row = db.query(FunctionalEvalConsent).filter(FunctionalEvalConsent.user_id == user.id).first()
    if row is None or not row.signed_document_path:
        raise ValueError("NOT_FOUND")
    return row.signed_document_path


def assign_evaluation_batch_for_new_worker(db: Session, period_id: int, site_code: str) -> int:
    """현장에 이미 서명이 있으면 다음 추가평가 배치 번호."""
    site_signed = (
        db.query(FunctionalEvalSignature)
        .filter(
            FunctionalEvalSignature.period_id == period_id,
            FunctionalEvalSignature.site_code == site_code,
            FunctionalEvalSignature.stage == STAGE_SITE,
        )
        .order_by(FunctionalEvalSignature.evaluation_batch.desc())
        .first()
    )
    if site_signed is None:
        team_signed = (
            db.query(FunctionalEvalSignature)
            .filter(
                FunctionalEvalSignature.period_id == period_id,
                FunctionalEvalSignature.site_code == site_code,
                FunctionalEvalSignature.stage == STAGE_TEAM_LEADER,
            )
            .first()
        )
        if team_signed is None:
            return 0
        return 1
    return (site_signed.evaluation_batch or 0) + 1


def build_signoff_payload_for_session(
    db: Session,
    user: User,
    period: FunctionalEvalPeriod,
    site_code: str,
    approval_summary: dict[str, Any],
    *, batch=None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service

    is_manager = service._is_primary_site_evaluator(db, user, site_code)
    batch = max(active_site_batches(db, period, site_code)) if batch is None else batch
    team_signed = all_team_leaders_signed(db, period, site_code, batch)
    payload: dict[str, Any] = {
        "team_leaders_all_signed": team_signed,
        "team_reports_all_manager_approved": True,
        "active_evaluation_batch": batch,
        "active_evaluation_batch_label": batch_label(batch),
    }
    if not is_manager:
        payload["team_signoff"] = get_team_signoff_status(db, user, period,batch=batch)
    else:
        payload["team_signoff"] = None
        payload["team_leader_reports"] = list_team_leader_report_status(db, period, site_code, batch)
        payload["can_submit_site_approval"] = bool(
            approval_summary.get("can_submit_site_approval") and team_signed
        )
    return payload
