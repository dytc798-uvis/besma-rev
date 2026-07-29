from __future__ import annotations

import csv
import json
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm import load_only

from app.config.security import get_password_hash
from app.core.auth import _ERP_LOGIN_ALIAS_FILE
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.modules.functional_eval.fe_viewer_provisioning_service import (
    load_viewer_rows_from_path,
)
from app.modules.functional_eval.models import FunctionalEvalViewerProvisionLog
from app.modules.users.models import User
from app.modules.workers.models import Person


DEPARTMENT_LABELS: dict[str, str] = {
    "02": "외주구매팀",
    "03": "재무회계팀",
    "04": "안전보건실",
    "05": "공사관리1팀",
    "06": "공사관리2팀",
    "08": "공사관리3팀",
    "09": "공사관리4팀",
    "10": "공사관리5팀",
    "12": "경영지원실",
    "13": "PM",
    "14": "업무팀",
    "16": "법무팀",
    "17": "공사관리6팀",
    "18": "원가관리팀",
    "19": "예산견적팀",
    "21": "공사관리팀",
}
CONSTRUCTION_DEPARTMENT_CODES = frozenset({"05", "06", "08", "09", "10", "17", "21"})
PRIVILEGED_HQ_ROLES = frozenset(
    {Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN, Role.ACCIDENT_ADMIN}
)
SITE_ROLES = frozenset({Role.SITE, Role.SITE_FUNCTIONAL_EVAL, Role.WORKER})


def _account_columns():
    # 운영 DB의 과거 비정상 birth_date 값이 계정 동기화를 막지 않도록
    # 필요한 사용자 열만 로드한다.
    return load_only(
        User.id,
        User.name,
        User.login_id,
        User.password_hash,
        User.department,
        User.role,
        User.ui_type,
        User.site_id,
        User.person_id,
        User.is_active,
        User.password_changed_at,
        User.must_change_password,
        User.initial_password_issued,
        User.account_issued_by,
        User.account_issued_at,
    )


@dataclass
class AccountPlan:
    row: dict[str, Any]
    department: str
    role: Role
    action: str
    target: User | None


def _normalized_code(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.isdigit():
        return raw.zfill(2)
    return raw


def _target_role(department_code: str) -> Role:
    if department_code == "04":
        return Role.HQ_SAFE
    if department_code == "19":
        return Role.HQ_BUDGET_ESTIMATE
    if department_code == "02" or department_code in CONSTRUCTION_DEPARTMENT_CODES:
        return Role.HQ_OUTSOURCING_PURCHASE
    return Role.FUNCTIONAL_EVAL_VIEWER


def _active_hq_named_users(db: Session, name: str) -> list[User]:
    return [
        user
        for user in db.query(User)
        .options(_account_columns())
        .filter(User.name == name, User.is_active.is_(True))
        .order_by(User.id.asc())
        .all()
        if user.role not in SITE_ROLES and user.ui_type == UIType.HQ_SAFE
    ]


def _choose_existing_user(
    db: Session,
    *,
    name: str,
    erp_login_id: str,
    department: str,
    role: Role,
) -> tuple[User | None, str | None]:
    exact = (
        db.query(User)
        .options(_account_columns())
        .filter(User.login_id.ilike(erp_login_id))
        .order_by(User.id.asc())
        .first()
    )
    if exact is not None:
        if exact.name.strip() != name:
            return None, "ERP_LOGIN_COLLISION"
        return exact, None

    candidates = _active_hq_named_users(db, name)
    if not candidates:
        return None, None
    if len(candidates) == 1:
        return candidates[0], None

    if role == Role.HQ_SAFE:
        dedicated = [
            user for user in candidates if (user.login_id or "").startswith("안전보건-")
        ]
        if len(dedicated) == 1:
            return dedicated[0], None

    privileged = [user for user in candidates if user.role in PRIVILEGED_HQ_ROLES]
    if len(privileged) == 1:
        return privileged[0], None

    exact_department = [
        user
        for user in candidates
        if department and department in (user.department or "")
    ]
    if len(exact_department) == 1:
        return exact_department[0], None

    matching_role = [user for user in candidates if user.role == role]
    if len(matching_role) == 1:
        return matching_role[0], None
    named_hq = [
        user
        for user in candidates
        if (user.login_id or "").startswith(("부현본사-", "안전보건-"))
    ]
    if len(named_hq) == 1:
        return named_hq[0], None
    return None, "AMBIGUOUS_EXISTING_HQ_ACCOUNT"


def build_account_plan(
    db: Session, source_path: Path
) -> tuple[list[AccountPlan], list[dict[str, str]], list[dict[str, Any]], str]:
    rows, source_label = load_viewer_rows_from_path(source_path)
    plans: list[AccountPlan] = []
    excluded: list[dict[str, str]] = []
    seen_erp_ids: set[str] = set()

    for row in rows:
        department_code = _normalized_code(row.get("department_code"))
        if department_code not in DEPARTMENT_LABELS:
            continue
        name = str(row.get("name") or "").strip()
        birth6 = re.sub(r"\D", "", str(row.get("birth6") or ""))[:6]
        erp_login_id = str(row.get("erp_login_id") or "").strip().lower()
        if row.get("termination_date"):
            excluded.append({"name": name, "reason": "TERMINATED"})
            continue
        if not name or len(birth6) != 6 or not erp_login_id:
            excluded.append({"name": name, "reason": "MISSING_IDENTITY"})
            continue
        if erp_login_id in seen_erp_ids:
            excluded.append({"name": name, "reason": "DUPLICATE_ERP_LOGIN"})
            continue
        seen_erp_ids.add(erp_login_id)

        department = DEPARTMENT_LABELS[department_code]
        role = _target_role(department_code)
        target, error = _choose_existing_user(
            db,
            name=name,
            erp_login_id=erp_login_id,
            department=department,
            role=role,
        )
        if error:
            excluded.append({"name": name, "reason": error})
            continue
        action = "CREATE" if target is None else (
            "UPDATE_ERP_ACCOUNT"
            if (target.login_id or "").casefold() == erp_login_id.casefold()
            else "LINK_LEGACY_ACCOUNT"
        )
        plans.append(
            AccountPlan(
                row=row,
                department=department,
                role=role,
                action=action,
                target=target,
            )
        )
    return plans, excluded, rows, source_label


def summarize_plan(
    plans: list[AccountPlan], excluded: list[dict[str, str]], source_label: str
) -> dict[str, Any]:
    def counts(values: list[str]) -> dict[str, int]:
        result: dict[str, int] = {}
        for value in values:
            result[value] = result.get(value, 0) + 1
        return dict(sorted(result.items()))

    return {
        "mode": "dry_run",
        "source_label": source_label,
        "planned_count": len(plans),
        "excluded_count": len(excluded),
        "action_counts": counts([plan.action for plan in plans]),
        "department_counts": counts([plan.department for plan in plans]),
        "role_counts": counts([plan.role.value for plan in plans]),
        "exclusion_reasons": counts([item["reason"] for item in excluded]),
        "password_reset_count": sum(
            plan.target is None or plan.target.password_changed_at is None
            for plan in plans
        ),
        "password_preserved_count": sum(
            plan.target is not None and plan.target.password_changed_at is not None
            for plan in plans
        ),
    }


def _alias_rows(rows: list[dict[str, Any]], source_label: str) -> list[dict[str, str]]:
    aliases: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        login_id = str(row.get("erp_login_id") or "").strip().lower()
        name = str(row.get("name") or "").strip()
        birth6 = re.sub(r"\D", "", str(row.get("birth6") or ""))[:6]
        if (
            not login_id
            or not name
            or len(birth6) != 6
            or login_id in seen
            or row.get("termination_date")
        ):
            continue
        seen.add(login_id)
        aliases.append(
            {
                "name": name,
                "birth6": birth6,
                "employee_code": str(row.get("employee_code") or "").strip(),
                "department": str(row.get("department") or "").strip(),
                "position": str(row.get("position") or "").strip(),
                "email": str(row.get("email") or "").strip(),
                "erp_login_id": login_id,
                "source_file": source_label,
            }
        )
    return aliases


def _write_alias_file(rows: list[dict[str, str]]) -> None:
    target = _ERP_LOGIN_ALIAS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    fields = (
        "name",
        "birth6",
        "employee_code",
        "department",
        "position",
        "email",
        "erp_login_id",
        "source_file",
    )
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(target)


def apply_account_plan(
    db: Session,
    source_path: Path,
    *,
    actor: User | None = None,
) -> dict[str, Any]:
    plans, excluded, source_rows, source_label = build_account_plan(db, source_path)
    summary = summarize_plan(plans, excluded, source_label)
    now = utc_now()
    created = 0
    updated = 0
    aliases = _alias_rows(source_rows, source_label)
    temporary_credentials: list[dict[str, str]] = []

    for plan in plans:
        row = plan.row
        erp_login_id = str(row["erp_login_id"]).strip().lower()
        rrn_hash = row.get("rrn_hash")
        person = (
            db.query(Person).filter(Person.rrn_hash == rrn_hash).first()
            if rrn_hash
            else None
        )
        user = plan.target
        if user is None:
            temporary_password = secrets.token_urlsafe(12)
            expires_at = now + timedelta(hours=24)
            user = User(
                name=str(row["name"]).strip(),
                login_id=erp_login_id,
                password_hash=get_password_hash(temporary_password),
                birth_date=row.get("birth_date"),
                department=plan.department,
                role=plan.role,
                ui_type=UIType.HQ_SAFE,
                person_id=person.id if person else None,
                is_active=True,
                must_change_password=True,
                initial_password_issued=True,
                account_issued_by="hq_erp_bulk",
                account_issued_at=now,
                temporary_password_expires_at=expires_at,
            )
            db.add(user)
            temporary_credentials.append(
                {
                    "login_id": erp_login_id,
                    "temporary_password": temporary_password,
                    "expires_at": expires_at.isoformat(),
                }
            )
            created += 1
        else:
            user.name = str(row["name"]).strip()
            if row.get("birth_date") is not None:
                user.birth_date = row["birth_date"]
            user.department = plan.department
            if user.role not in PRIVILEGED_HQ_ROLES:
                user.role = plan.role
            user.ui_type = UIType.HQ_SAFE
            user.person_id = person.id if person else user.person_id
            user.site_id = None
            user.is_active = True
            if user.password_changed_at is None:
                temporary_password = secrets.token_urlsafe(12)
                expires_at = now + timedelta(hours=24)
                user.password_hash = get_password_hash(temporary_password)
                user.must_change_password = True
                user.initial_password_issued = True
                user.account_issued_by = "hq_erp_bulk"
                user.account_issued_at = now
                user.temporary_password_expires_at = expires_at
                temporary_credentials.append(
                    {
                        "login_id": user.login_id,
                        "temporary_password": temporary_password,
                        "expires_at": expires_at.isoformat(),
                    }
                )
            db.add(user)
            updated += 1

    log_payload = {
        **summary,
        "mode": "apply",
        "created_count": created,
        "updated_count": updated,
        "alias_count": len(aliases),
    }
    db.add(
        FunctionalEvalViewerProvisionLog(
            mode="apply",
            source_label=source_label,
            created_by_user_id=actor.id if actor else None,
            created_by_login_id=actor.login_id if actor else None,
            planned_count=len(plans),
            excluded_count=len(excluded),
            applied_count=created + updated,
            result_json=json.dumps(log_payload, ensure_ascii=False),
        )
    )
    _write_alias_file(aliases)
    db.commit()
    return {**log_payload, "temporary_credentials": temporary_credentials}
