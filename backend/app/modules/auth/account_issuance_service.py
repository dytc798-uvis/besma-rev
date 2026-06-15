"""로그인 화면 아이디 자가 발급."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.core.permissions import HQ_SAFE_WORKSPACE_ROLES
from app.modules.auth.account_issuance_models import AccountIssuanceLog
from app.modules.functional_eval import service as fe_service
from app.modules.functional_eval.eval_provisioning import _rrn_front_password
from app.modules.functional_eval.models import (
    FunctionalEvalPeriod,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.site_alias import build_eval_login_id
from app.modules.sites.models import Site
from app.modules.users.hq_safe_accounts import HQ_SAFE_ACCOUNT_SPECS
from app.modules.users.models import User

GENERIC_FAILURE = (
    "입력한 정보와 일치하는 계정을 찾을 수 없습니다. 정보를 확인 후 다시 시도해 주세요."
)
RATE_LIMIT_MESSAGE = "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요."

MAX_FAILS_PER_FINGERPRINT = 5
FAIL_WINDOW_MINUTES = 10
MAX_REQUESTS_PER_IP = 40
IP_WINDOW_MINUTES = 10


class AccountIssuanceError(Exception):
    def __init__(self, message: str, *, internal_reason: str = "") -> None:
        super().__init__(message)
        self.internal_reason = internal_reason


def user_participates_in_fe_consent(user: User) -> bool:
    if user.role == Role.SITE_FUNCTIONAL_EVAL:
        return True
    return user.role in HQ_SAFE_WORKSPACE_ROLES


def fe_consent_required(db: Session, user: User) -> bool:
    if not user_participates_in_fe_consent(user):
        return False
    from app.modules.functional_eval.signature_ops import get_consent_status

    return bool(get_consent_status(db, user).get("required"))


def _normalize_birth6(value: str) -> str:
    digits = re.sub(r"\D", "", (value or "").strip())
    if len(digits) != 6:
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="invalid_birth6")
    return digits


def _fingerprint(scope: str, *, site_code: str | None, name: str, birth6: str, department: str | None) -> str:
    raw = "|".join(
        [
            scope.strip().lower(),
            (site_code or "").strip(),
            fe_service._normalize_role_identifier(name),
            birth6,
            (department or "").strip(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _check_rate_limits(db: Session, *, fingerprint: str, request_ip: str | None) -> None:
    now = utc_now()
    fail_since = now - timedelta(minutes=FAIL_WINDOW_MINUTES)
    fail_count = (
        db.query(AccountIssuanceLog)
        .filter(
            AccountIssuanceLog.input_fingerprint == fingerprint,
            AccountIssuanceLog.success.is_(False),
            AccountIssuanceLog.issued_at >= fail_since,
        )
        .count()
    )
    if fail_count >= MAX_FAILS_PER_FINGERPRINT:
        raise AccountIssuanceError(RATE_LIMIT_MESSAGE, internal_reason="fingerprint_locked")

    if request_ip:
        ip_since = now - timedelta(minutes=IP_WINDOW_MINUTES)
        ip_count = (
            db.query(AccountIssuanceLog)
            .filter(
                AccountIssuanceLog.request_ip == request_ip,
                AccountIssuanceLog.issued_at >= ip_since,
            )
            .count()
        )
        if ip_count >= MAX_REQUESTS_PER_IP:
            raise AccountIssuanceError(RATE_LIMIT_MESSAGE, internal_reason="ip_locked")


def _log_attempt(
    db: Session,
    *,
    scope: str,
    site_code: str | None,
    department: str | None,
    name: str,
    fingerprint: str,
    request_ip: str | None,
    success: bool,
    recipient_name: str | None,
    accounts: list[dict[str, Any]] | None,
    failure_reason: str | None,
) -> None:
    row = AccountIssuanceLog(
        scope=scope,
        site_code=site_code,
        input_department=department,
        input_name=name.strip(),
        input_fingerprint=fingerprint,
        recipient_name=recipient_name,
        issued_account_count=len(accounts or []),
        issued_accounts_json=json.dumps(accounts or [], ensure_ascii=False),
        request_ip=request_ip,
        success=success,
        failure_reason=failure_reason,
    )
    db.add(row)
    db.flush()


def _latest_period(db: Session) -> FunctionalEvalPeriod | None:
    return db.query(FunctionalEvalPeriod).order_by(FunctionalEvalPeriod.id.desc()).first()


def _rrn_front_from_worker(worker: FunctionalEvalWorker) -> str | None:
    return _rrn_front_password(worker.rrn_masked or "")


def _find_worker_rrn_front(
    db: Session,
    *,
    period_id: int,
    site_code: str,
    person_name: str,
) -> str | None:
    target = fe_service._normalize_role_identifier(person_name)
    workers = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.period_id == period_id,
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.is_active.is_(True),
        )
        .all()
    )
    for worker in workers:
        if fe_service._normalize_role_identifier(worker.name) == target:
            front = _rrn_front_from_worker(worker)
            if front:
                return front
    return None


def _issue_eval_account(
    db: Session,
    *,
    login_id: str,
    name: str,
    password_plain: str,
    site: Site,
    issued_by: str,
) -> User:
    login_id = login_id.strip()
    user = db.query(User).filter(User.login_id == login_id).first()
    now = utc_now()
    if user is None:
        user = User(
            name=name.strip(),
            login_id=login_id,
            password_hash=get_password_hash(password_plain),
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
            must_change_password=True,
            initial_password_issued=True,
            account_issued_by=issued_by,
            account_issued_at=now,
            is_active=True,
        )
        db.add(user)
    else:
        user.name = name.strip()
        user.role = Role.SITE_FUNCTIONAL_EVAL
        user.ui_type = UIType.SITE
        user.site_id = site.id
        user.password_hash = get_password_hash(password_plain)
        user.must_change_password = True
        user.initial_password_issued = True
        user.account_issued_by = issued_by
        user.account_issued_at = now
        user.is_active = True
        db.add(user)
    return user


def _issue_hq_account(db: Session, user: User, *, password_plain: str, issued_by: str) -> User:
    now = utc_now()
    user.password_hash = get_password_hash(password_plain)
    user.must_change_password = True
    user.initial_password_issued = True
    user.account_issued_by = issued_by
    user.account_issued_at = now
    user.is_active = True
    db.add(user)
    return user


def _hq_user_matches_birth(user: User, birth6: str) -> bool:
    if user.birth_date is not None and user.birth_date.strftime("%y%m%d") == birth6:
        return True
    spec = next((s for s in HQ_SAFE_ACCOUNT_SPECS if s.login_id == user.login_id), None)
    if spec and spec.password == birth6:
        return True
    from app.modules.functional_eval.constants import CEO_EVAL_LOGIN_IDS

    if user.login_id in CEO_EVAL_LOGIN_IDS and birth6 == "611001":
        return True
    return False


def _find_hq_user(db: Session, *, name: str, birth6: str, department: str | None) -> User | None:
    matched: list[User] = []
    target = fe_service._normalize_role_identifier(name)
    for spec in HQ_SAFE_ACCOUNT_SPECS:
        if fe_service._normalize_role_identifier(spec.name) != target:
            continue
        if spec.password != birth6:
            continue
        user = db.query(User).filter(User.login_id == spec.login_id, User.is_active.is_(True)).first()
        if user is not None:
            matched.append(user)
    from app.modules.functional_eval.constants import CEO_EVAL_LOGIN_IDS

    for ceo_login in CEO_EVAL_LOGIN_IDS:
        user = db.query(User).filter(User.login_id == ceo_login, User.is_active.is_(True)).first()
        if user is None:
            continue
        if fe_service._normalize_role_identifier(user.name) != target:
            continue
        if birth6 == "611001":
            matched.append(user)

    for user in db.query(User).filter(User.is_active.is_(True), User.role.in_(tuple(HQ_SAFE_WORKSPACE_ROLES))).all():
        if user in matched:
            continue
        if fe_service._normalize_role_identifier(user.name) != target:
            continue
        if department and (user.department or "").strip() and department not in (user.department or ""):
            continue
        if _hq_user_matches_birth(user, birth6):
            matched.append(user)

    unique = {u.id: u for u in matched}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def issue_site_accounts(
    db: Session,
    *,
    site_code: str,
    name: str,
    birth6_raw: str,
    request_ip: str | None,
) -> dict[str, Any]:
    site_code = (site_code or "").strip()
    name = (name or "").strip()
    birth6 = _normalize_birth6(birth6_raw)
    fingerprint = _fingerprint("site", site_code=site_code, name=name, birth6=birth6, department=None)
    _check_rate_limits(db, fingerprint=fingerprint, request_ip=request_ip)

    reg = (
        db.query(FunctionalEvalSiteRegistry)
        .filter(FunctionalEvalSiteRegistry.site_code == site_code)
        .first()
    )
    if reg is None:
        _log_attempt(
            db,
            scope="site",
            site_code=site_code,
            department=None,
            name=name,
            fingerprint=fingerprint,
            request_ip=request_ip,
            success=False,
            recipient_name=None,
            accounts=None,
            failure_reason="site_not_found",
        )
        db.commit()
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="site_not_found")

    if fe_service._normalize_role_identifier(reg.manager_name) != fe_service._normalize_role_identifier(name):
        _log_attempt(
            db,
            scope="site",
            site_code=site_code,
            department=None,
            name=name,
            fingerprint=fingerprint,
            request_ip=request_ip,
            success=False,
            recipient_name=None,
            accounts=None,
            failure_reason="manager_name_mismatch",
        )
        db.commit()
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="manager_name_mismatch")

    period = _latest_period(db)
    if period is None:
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="no_period")

    manager_rrn = _find_worker_rrn_front(
        db,
        period_id=period.id,
        site_code=site_code,
        person_name=reg.manager_name,
    )
    if manager_rrn != birth6:
        _log_attempt(
            db,
            scope="site",
            site_code=site_code,
            department=None,
            name=name,
            fingerprint=fingerprint,
            request_ip=request_ip,
            success=False,
            recipient_name=reg.manager_name,
            accounts=None,
            failure_reason="birth_mismatch",
        )
        db.commit()
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="birth_mismatch")

    site = db.query(Site).filter(Site.site_code == site_code).first()
    if site is None:
        site = Site(site_code=site_code, site_name=reg.erp_site_label or site_code, manager_name=reg.manager_name)
        db.add(site)
        db.flush()

    manager_login = (reg.manager_login_id or "").strip() or build_eval_login_id(reg.site_alias, reg.manager_name)
    reg.manager_login_id = manager_login

    issued_rows: list[dict[str, Any]] = []
    _issue_eval_account(
        db,
        login_id=manager_login,
        name=reg.manager_name,
        password_plain=birth6,
        site=site,
        issued_by="self_service_site",
    )
    issued_rows.append(
        {
            "role_label": "소장",
            "name": reg.manager_name,
            "login_id": manager_login,
            "initial_password": birth6,
        }
    )

    workers = fe_service._site_attendance_workers(db, period, site_code)
    manager_login_norm = manager_login
    team_logins = sorted(fe_service._collect_team_leader_evaluator_logins(workers, manager_login_norm))
    for tl_login in team_logins:
        tl_name = fe_service._normalize_login_to_name(tl_login)
        if not tl_name:
            continue
        tl_birth = _find_worker_rrn_front(
            db,
            period_id=period.id,
            site_code=site_code,
            person_name=tl_name,
        )
        if not tl_birth:
            tl_birth = birth6
        display_name = next(
            (w.name for w in workers if fe_service._normalize_role_identifier(w.name) == fe_service._normalize_role_identifier(tl_name)),
            tl_name,
        )
        _issue_eval_account(
            db,
            login_id=tl_login,
            name=display_name,
            password_plain=tl_birth,
            site=site,
            issued_by="self_service_site",
        )
        issued_rows.append(
            {
                "role_label": "팀장",
                "name": display_name,
                "login_id": tl_login,
                "initial_password": tl_birth,
            }
        )

    _log_attempt(
        db,
        scope="site",
        site_code=site_code,
        department=None,
        name=name,
        fingerprint=fingerprint,
        request_ip=request_ip,
        success=True,
        recipient_name=reg.manager_name,
        accounts=[{"login_id": r["login_id"], "name": r["name"], "role_label": r["role_label"]} for r in issued_rows],
        failure_reason=None,
    )
    db.commit()

    site_label = (reg.erp_site_label or reg.site_alias or site_code).strip()
    return {
        "scope": "site",
        "site_code": site_code,
        "site_label": site_label,
        "recipient_name": reg.manager_name,
        "accounts": issued_rows,
        "message": "아이디 발급이 완료되었습니다.",
    }


def issue_hq_account(
    db: Session,
    *,
    name: str,
    birth6_raw: str,
    department: str | None,
    request_ip: str | None,
) -> dict[str, Any]:
    name = (name or "").strip()
    department = (department or "").strip() or None
    birth6 = _normalize_birth6(birth6_raw)
    fingerprint = _fingerprint("hq", site_code=None, name=name, birth6=birth6, department=department)
    _check_rate_limits(db, fingerprint=fingerprint, request_ip=request_ip)

    candidates = _find_hq_user(db, name=name, birth6=birth6, department=department)
    if candidates is None:
        _log_attempt(
            db,
            scope="hq",
            site_code=None,
            department=department,
            name=name,
            fingerprint=fingerprint,
            request_ip=request_ip,
            success=False,
            recipient_name=None,
            accounts=None,
            failure_reason="hq_not_found",
        )
        db.commit()
        raise AccountIssuanceError(GENERIC_FAILURE, internal_reason="hq_not_found")

    user = candidates
    _issue_hq_account(db, user, password_plain=birth6, issued_by="self_service_hq")
    role_label = (user.department or "본사").strip()
    issued_rows = [
        {
            "role_label": role_label,
            "name": user.name,
            "login_id": user.login_id,
            "initial_password": birth6,
        }
    ]
    _log_attempt(
        db,
        scope="hq",
        site_code=None,
        department=department,
        name=name,
        fingerprint=fingerprint,
        request_ip=request_ip,
        success=True,
        recipient_name=user.name,
        accounts=[{"login_id": user.login_id, "name": user.name, "role_label": role_label}],
        failure_reason=None,
    )
    db.commit()
    return {
        "scope": "hq",
        "recipient_name": user.name,
        "role_label": role_label,
        "accounts": issued_rows,
        "message": "아이디 발급이 완료되었습니다.",
    }
