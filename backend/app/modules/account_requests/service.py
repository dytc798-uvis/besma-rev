from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.modules.account_requests.models import AccountAccessRequest, AccountAccessRequestEvent
from app.modules.account_requests.schemas import AccountRequestItem
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Person

REQUEST_TYPES = {"NEW_ACCOUNT", "ACCESS_CHANGE", "REACTIVATE"}
REQUEST_STATUSES = {
    "REQUESTED",
    "IN_REVIEW",
    "NEEDS_INFO",
    "APPROVED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
}
WORK_CATEGORIES = {
    "SAFETY",
    "CONSTRUCTION",
    "PUBLIC_WORKS",
    "BUDGET_ESTIMATE",
    "OUTSOURCING_PURCHASE",
    "SITE",
    "FUNCTIONAL_EVAL_VIEW",
    "OTHER",
}
APPROVER_ROLES = {Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN}
ROLE_MAPPING: dict[str, Role | None] = {
    "SAFETY": Role.HQ_SAFE,
    "CONSTRUCTION": None,
    "PUBLIC_WORKS": None,
    "BUDGET_ESTIMATE": Role.HQ_BUDGET_ESTIMATE,
    "OUTSOURCING_PURCHASE": Role.HQ_OUTSOURCING_PURCHASE,
    "SITE": Role.SITE,
    "FUNCTIONAL_EVAL_VIEW": Role.FUNCTIONAL_EVAL_VIEWER,
    "OTHER": None,
}
ROLE_UI_TYPE = {
    Role.SITE: UIType.SITE,
    Role.SITE_FUNCTIONAL_EVAL: UIType.SITE,
    Role.HQ_OTHER: UIType.HQ_OTHER,
}
OPEN_STATUSES = {"REQUESTED", "IN_REVIEW", "NEEDS_INFO"}
DEPARTMENT_OPTIONS: dict[str, list[str]] = {
    "HQ": [
        "안전보건실",
        "공사관리팀",
        "공사관리1팀",
        "공사관리2팀",
        "공사관리3팀",
        "공사관리4팀",
        "공사관리6팀",
        "업무팀",
        "예산견적팀",
        "외주구매팀",
        "재무회계팀",
        "원가관리팀",
        "경영지원실",
        "PM",
        "기타",
    ],
    "SITE": ["현장소장", "공사", "공무", "안전", "관리", "기타"],
}
HQ_DEPARTMENT_CATEGORY = {
    "안전보건실": "SAFETY",
    "공사관리팀": "CONSTRUCTION",
    "공사관리1팀": "CONSTRUCTION",
    "공사관리2팀": "CONSTRUCTION",
    "공사관리3팀": "CONSTRUCTION",
    "공사관리4팀": "CONSTRUCTION",
    "공사관리6팀": "CONSTRUCTION",
    "업무팀": "PUBLIC_WORKS",
    "예산견적팀": "BUDGET_ESTIMATE",
    "외주구매팀": "OUTSOURCING_PURCHASE",
}


def request_options(db: Session) -> dict:
    active_counts = {
        int(site_id): int(count)
        for site_id, count in (
            db.query(User.site_id, func.count(User.id))
            .filter(User.is_active.is_(True), User.site_id.isnot(None))
            .group_by(User.site_id)
            .all()
        )
        if site_id is not None
    }
    preferred_by_name: dict[str, tuple[tuple[int, int, int, int], Site]] = {}
    for site in db.query(Site).all():
        name = (site.site_name or "").strip()
        if not name:
            continue
        score = (
            active_counts.get(int(site.id), 0),
            1 if (site.status or "").strip().upper() == "ACTIVE" else 0,
            0 if (site.site_code or "").strip().upper().startswith("SITE") else 1,
            int(site.id),
        )
        previous = preferred_by_name.get(name)
        if previous is None or score > previous[0]:
            preferred_by_name[name] = (score, site)
    sites = [
        {"id": int(site.id), "name": name}
        for name, (_, site) in sorted(preferred_by_name.items(), key=lambda item: item[0])
    ]
    return {"departments": DEPARTMENT_OPTIONS, "sites": sites}


def _category_for_department(scope: str, department: str) -> str:
    if department not in DEPARTMENT_OPTIONS[scope]:
        raise HTTPException(status_code=400, detail="INVALID_DEPARTMENT")
    if scope == "SITE":
        return "SITE"
    return HQ_DEPARTMENT_CATEGORY.get(department, "OTHER")


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) < 9 or len(digits) > 12:
        raise HTTPException(status_code=400, detail="INVALID_PHONE")
    return digits


def mask_phone(value: str) -> str:
    digits = normalize_phone(value)
    return f"{digits[:3]}-****-{digits[-4:]}"


def _request_no() -> str:
    return f"AR-{utc_now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def _role_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _candidate_users(db: Session, *, name: str, phone: str) -> list[User]:
    name = name.strip()
    candidates = db.query(User).filter(User.name == name).all()
    phone_matches: list[User] = []
    for user in candidates:
        if user.person_id is None:
            continue
        person = db.query(Person).filter(Person.id == user.person_id).first()
        if person and person.phone_mobile:
            try:
                if normalize_phone(person.phone_mobile) == phone:
                    phone_matches.append(user)
            except HTTPException:
                continue
    return phone_matches or candidates


def _duplicate_json(ids: list[int]) -> str:
    return json.dumps(sorted(set(ids)))


def _audit(
    db: Session,
    *,
    req: AccountAccessRequest,
    action: str,
    from_status: str | None,
    actor: User | None,
    detail: dict | None = None,
) -> None:
    db.add(
        AccountAccessRequestEvent(
            request_id=req.id,
            action=action,
            from_status=from_status,
            to_status=req.status,
            actor_user_id=actor.id if actor else None,
            actor_role=_role_value(actor.role) if actor else None,
            detail_json=json.dumps(detail or {}, ensure_ascii=False),
        )
    )


def item_from_model(req: AccountAccessRequest) -> AccountRequestItem:
    try:
        duplicate_ids = [int(value) for value in json.loads(req.duplicate_candidate_ids_json or "[]")]
    except (TypeError, ValueError, json.JSONDecodeError):
        duplicate_ids = []
    return AccountRequestItem(
        id=req.id,
        request_no=req.request_no,
        request_type=req.request_type,
        status=req.status,
        applicant_user_id=req.applicant_user_id,
        existing_user_id=req.existing_user_id,
        name=req.name,
        phone_mobile_masked=mask_phone(req.phone_mobile),
        company_name=req.company_name,
        scope=req.scope,
        department=req.department,
        work_category=req.work_category,
        site_id=req.site_id,
        site_code=req.site_code,
        site_name=req.site_name,
        request_reason=req.request_reason,
        employment_evidence_note=req.employment_evidence_note,
        roster_match_status=req.roster_match_status,
        duplicate_candidate_ids=duplicate_ids,
        recommended_role=req.recommended_role,
        current_role_snapshot=req.current_role_snapshot,
        current_site_id_snapshot=req.current_site_id_snapshot,
        approved_role=req.approved_role,
        approved_site_id=req.approved_site_id,
        valid_until=req.valid_until,
        handled_by_user_id=req.handled_by_user_id,
        handled_at=req.handled_at,
        decision_comment=req.decision_comment,
        created_account_user_id=req.created_account_user_id,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def create_request(
    db: Session,
    *,
    payload,
    applicant: User | None,
    request_type: str,
) -> AccountAccessRequest:
    request_type = request_type.strip().upper()
    scope = payload.scope.strip().upper()
    if request_type not in REQUEST_TYPES:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST_TYPE")
    if scope not in {"HQ", "SITE"}:
        raise HTTPException(status_code=400, detail="INVALID_REQUEST_SCOPE")
    department = (payload.department or "").strip()
    if not department:
        raise HTTPException(status_code=400, detail="DEPARTMENT_REQUIRED")
    category = _category_for_department(scope, department)
    if not payload.privacy_consent:
        raise HTTPException(status_code=400, detail="PRIVACY_CONSENT_REQUIRED")
    phone = normalize_phone(payload.phone_mobile)
    candidates = _candidate_users(db, name=payload.name.strip(), phone=phone)
    if applicant is not None:
        candidates = [applicant]
    existing_user = candidates[0] if len(candidates) == 1 else None
    if request_type == "NEW_ACCOUNT" and existing_user is not None:
        request_type = "ACCESS_CHANGE" if existing_user.is_active else "REACTIVATE"
    duplicate_ids = [u.id for u in candidates]
    roster_status = "MATCHED" if len(candidates) == 1 else ("AMBIGUOUS" if candidates else "NOT_FOUND")

    duplicate_open = (
        db.query(AccountAccessRequest)
        .filter(
            AccountAccessRequest.phone_mobile == phone,
            AccountAccessRequest.name == payload.name.strip(),
            AccountAccessRequest.work_category == category,
            AccountAccessRequest.status.in_(OPEN_STATUSES),
        )
        .first()
    )
    if duplicate_open is not None:
        raise HTTPException(status_code=409, detail="OPEN_REQUEST_ALREADY_EXISTS")

    site = None
    if scope == "SITE" and payload.site_id is not None:
        site = db.query(Site).filter(Site.id == payload.site_id).first()
    elif scope == "SITE" and payload.site_code:
        site = db.query(Site).filter(Site.site_code == payload.site_code.strip()).first()
    if scope == "SITE" and site is None:
        raise HTTPException(status_code=400, detail="SITE_REQUIRED")
    recommended = ROLE_MAPPING[category]
    req = AccountAccessRequest(
        request_no=_request_no(),
        request_type=request_type,
        status="REQUESTED",
        applicant_user_id=applicant.id if applicant else None,
        existing_user_id=existing_user.id if existing_user else None,
        name=payload.name.strip(),
        phone_mobile=phone,
        company_name=payload.company_name.strip(),
        scope=scope,
        department=department,
        work_category=category,
        site_id=site.id if site else None,
        site_code=site.site_code if site else None,
        site_name=site.site_name if site else None,
        request_reason=payload.request_reason.strip(),
        employment_evidence_note=(payload.employment_evidence_note or "").strip() or None,
        privacy_consent_at=utc_now(),
        roster_match_status=roster_status,
        duplicate_candidate_ids_json=_duplicate_json(duplicate_ids),
        recommended_role=_role_value(recommended),
        current_role_snapshot=_role_value(existing_user.role) if existing_user else None,
        current_site_id_snapshot=existing_user.site_id if existing_user else None,
    )
    db.add(req)
    db.flush()
    _audit(db, req=req, action="SUBMIT", from_status=None, actor=applicant)
    db.commit()
    db.refresh(req)
    return req


def _new_login_id(db: Session, request_id: int) -> str:
    base = f"besma-{request_id:06d}"
    candidate = base
    suffix = 1
    while db.query(User).filter(User.login_id == candidate).first() is not None:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def decide_request(db: Session, *, req: AccountAccessRequest, payload, actor: User):
    if actor.role not in APPROVER_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="APPROVER_REQUIRED")
    if req.applicant_user_id == actor.id:
        raise HTTPException(status_code=409, detail="SELF_APPROVAL_NOT_ALLOWED")
    if req.status not in OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="REQUEST_ALREADY_CLOSED")

    action = payload.action.strip().upper()
    next_status = {
        "START_REVIEW": "IN_REVIEW",
        "REQUEST_INFO": "NEEDS_INFO",
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "CANCEL": "CANCELLED",
    }.get(action)
    if next_status is None:
        raise HTTPException(status_code=400, detail="INVALID_ACTION")
    old_status = req.status
    temporary_password = None
    temporary_expires = None

    if action == "APPROVE":
        role_text = (payload.approved_role or req.recommended_role or "").strip()
        if not role_text:
            raise HTTPException(status_code=409, detail="ROLE_MAPPING_NOT_CONFIRMED")
        try:
            approved_role = Role(role_text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="INVALID_APPROVED_ROLE") from exc
        recommended = ROLE_MAPPING.get(req.work_category)
        if recommended is not None and approved_role != recommended and actor.role != Role.SUPER_ADMIN:
            raise HTTPException(status_code=403, detail="ROLE_OVERRIDE_REQUIRES_SUPER_ADMIN")
        approved_site_id = payload.approved_site_id or req.site_id
        if approved_role in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL} and approved_site_id is None:
            raise HTTPException(status_code=400, detail="APPROVED_SITE_REQUIRED")

        target = db.query(User).filter(User.id == req.existing_user_id).first() if req.existing_user_id else None
        if target is None:
            if req.roster_match_status == "AMBIGUOUS":
                raise HTTPException(status_code=409, detail="DUPLICATE_REVIEW_REQUIRED")
            temporary_password = secrets.token_urlsafe(12)
            temporary_expires = utc_now() + timedelta(hours=24)
            target = User(
                name=req.name,
                login_id=_new_login_id(db, req.id),
                password_hash=get_password_hash(temporary_password),
                department=req.department,
                role=approved_role,
                ui_type=ROLE_UI_TYPE.get(approved_role, UIType.HQ_SAFE),
                site_id=approved_site_id,
                is_active=True,
                must_change_password=True,
                temporary_password_expires_at=temporary_expires,
                initial_password_issued=True,
                account_issued_by=f"account_request:{req.id}",
                account_issued_at=utc_now(),
            )
            db.add(target)
            db.flush()
            req.created_account_user_id = target.id
            req.existing_user_id = target.id
        else:
            if not target.is_active and req.request_type == "REACTIVATE":
                target.is_active = True
            role_changed = _role_value(target.role) != approved_role.value
            if role_changed and not payload.replace_existing_role:
                raise HTTPException(status_code=409, detail="ROLE_REPLACEMENT_CONFIRMATION_REQUIRED")
            target.role = approved_role
            target.ui_type = ROLE_UI_TYPE.get(approved_role, UIType.HQ_SAFE)
            if approved_site_id is not None:
                target.site_id = approved_site_id
            db.add(target)
        req.approved_role = approved_role.value
        req.approved_site_id = approved_site_id
        req.valid_until = payload.valid_until

    req.status = next_status
    req.handled_by_user_id = actor.id
    req.handled_at = utc_now()
    req.decision_comment = (payload.comment or "").strip() or None
    _audit(
        db,
        req=req,
        action=action,
        from_status=old_status,
        actor=actor,
        detail={
            "approved_role": req.approved_role,
            "approved_site_id": req.approved_site_id,
            "valid_until": req.valid_until.isoformat() if req.valid_until else None,
        },
    )
    db.commit()
    db.refresh(req)
    return req, temporary_password, temporary_expires


def find_existing_account(
    db: Session,
    *,
    scope: str,
    site_code: str | None,
    department: str | None,
    name: str,
    birth6_raw: str,
    request_ip: str | None,
) -> dict:
    """Find one existing account without creating/resetting credentials."""
    from app.modules.auth.account_issuance_service import (
        AccountIssuanceError,
        GENERIC_FAILURE,
        _check_rate_limits,
        _find_hq_user,
        _find_worker_rrn_front,
        _fingerprint,
        _latest_period,
        _log_attempt,
        _normalize_birth6,
    )

    scope = (scope or "").strip().lower()
    name = (name or "").strip()
    site_code = (site_code or "").strip() or None
    department = (department or "").strip() or None
    birth6 = _normalize_birth6(birth6_raw)
    if scope == "hq" and not department:
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="department_required")
    if scope == "site" and not site_code:
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="site_code_required")
    fingerprint = _fingerprint(
        scope, site_code=site_code, name=name, birth6=birth6, department=department
    )
    _check_rate_limits(db, fingerprint=fingerprint, request_ip=request_ip)

    matched: list[User] = []
    if scope == "site":
        site = db.query(Site).filter(Site.site_code == site_code).first()
        period = _latest_period(db)
        identity_verified = bool(
            site
            and period
            and _find_worker_rrn_front(
                db,
                period_id=period.id,
                site_code=site_code,
                person_name=name,
            )
            == birth6
        )
        if identity_verified:
            matched = (
                db.query(User)
                .filter(
                    User.name == name,
                    User.site_id == site.id,
                    User.is_active.is_(True),
                )
                .all()
            )
    elif scope == "hq":
        user = _find_hq_user(db, name=name, birth6=birth6, department=department)
        matched = [user] if user is not None else []
    else:
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="invalid_scope")

    success = len(matched) == 1
    _log_attempt(
        db,
        scope=scope,
        site_code=site_code,
        department=department,
        name=name,
        fingerprint=fingerprint,
        request_ip=request_ip,
        success=success,
        recipient_name=matched[0].name if success else None,
        accounts=(
            [{"login_id": matched[0].login_id, "name": matched[0].name, "role_label": _role_value(matched[0].role)}]
            if success
            else None
        ),
        failure_reason=None if success else ("ambiguous" if matched else "not_found"),
    )
    db.commit()
    if not success:
        raise AccountIssuanceError(
            GENERIC_FAILURE,
            internal_reason="ambiguous" if matched else "not_found",
        )
    user = matched[0]
    return {
        "scope": scope,
        "recipient_name": user.name,
        "role_label": user.department or _role_value(user.role),
        "accounts": [
            {
                "role_label": user.department or _role_value(user.role),
                "name": user.name,
                "login_id": user.login_id,
                "initial_password": None,
            }
        ],
        "message": "기존 계정을 확인했습니다. 현재 비밀번호 또는 비밀번호 재설정 절차를 이용해 주세요.",
    }
