from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, load_only

from app.config.security import get_password_hash
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.modules.functional_eval.fe_viewer_provisioning_service import (
    load_viewer_rows_from_path,
)
from app.modules.functional_eval.site_alias import build_eval_login_id
from app.modules.new_site_deployment.deployment_alias import (
    derive_deployment_site_alias,
)
from app.modules.new_site_deployment.models import (
    NewSiteDeployment,
    NewSiteDeploymentAdministrator,
)
from app.modules.sites.latest_sync import is_current_site
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Person
from app.utils.file_ingestion import parse_excel_with_fallback


SOURCE_ROLE_COLUMNS = (
    ("SITE_MANAGER", "소장"),
    ("GONGMU", "공무"),
    ("OTHER", "기타"),
)
SITE_ACCOUNT_ROLES = frozenset({Role.SITE, Role.SITE_FUNCTIONAL_EVAL})
SITE_DEPARTMENT_CODES = frozenset({"1", "01", "7", "07", "15"})


@dataclass
class SiteAdminPlan:
    site: Site
    site_row: dict[str, str]
    employee_row: dict[str, Any]
    admin_role: str
    name: str
    login_id: str
    action: str
    target: User | None


def clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def load_site_rows(path: Path) -> list[dict[str, str]]:
    parsed = parse_excel_with_fallback(path)
    headers = [clean(value) for value in parsed.headers]
    return [
        {
            header: clean(values[index]) if index < len(values) else ""
            for index, header in enumerate(headers)
            if header
        }
        for values in parsed.rows
        if any(clean(value) for value in values)
    ]


def _resolved_admin_role(source_role: str, employee_row: dict[str, Any]) -> str:
    if source_role != "OTHER":
        return source_role
    position_code = clean(employee_row.get("position_code"))
    position = clean(employee_row.get("position"))
    if "안전" in position:
        return "SAFETY"
    if "공무" in position:
        return "GONGMU"
    if any(keyword in position for keyword in ("공사", "기술", "관급")):
        return "CONSTRUCTION_SUPERVISOR"
    if position_code == "22":
        return "SAFETY"
    if position_code in {"18", "19", "21", "23", "28"}:
        return "CONSTRUCTION_SUPERVISOR"
    return "OTHER"


def _select_employee_identity(
    identities: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if len(identities) == 1:
        return identities[0]
    site_identities = [
        row
        for row in identities
        if clean(row.get("department_code")) in SITE_DEPARTMENT_CODES
    ]
    if len(site_identities) == 1:
        return site_identities[0]
    return None


def _user_columns():
    return load_only(
        User.id,
        User.name,
        User.login_id,
        User.password_hash,
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


def build_site_admin_plan(
    db: Session,
    *,
    site_source: Path,
    employee_source: Path,
    as_of: date,
) -> tuple[list[SiteAdminPlan], list[dict[str, str]]]:
    site_rows = load_site_rows(site_source)
    employee_rows, _label = load_viewer_rows_from_path(employee_source)
    employee_by_name: dict[str, list[dict[str, Any]]] = {}
    for row in employee_rows:
        if row.get("termination_date"):
            continue
        name = clean(row.get("name"))
        birth6 = clean(row.get("birth6"))
        if name and len(birth6) == 6:
            employee_by_name.setdefault(name, []).append(row)

    sites = {site.site_code: site for site in db.query(Site).all()}
    plans: list[SiteAdminPlan] = []
    excluded: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for row in site_rows:
        current, _reason = is_current_site(row, as_of)
        code = row.get("현장코드", "")
        site = sites.get(code)
        if not current or site is None:
            continue
        alias = derive_deployment_site_alias(
            row.get("도급사명"), row.get("현장명", "")
        )
        for source_role, column in SOURCE_ROLE_COLUMNS:
            name = row.get(column, "")
            if not name or (code, name) in seen:
                continue
            seen.add((code, name))
            identities = employee_by_name.get(name, [])
            employee = _select_employee_identity(identities)
            if employee is None:
                excluded.append(
                    {
                        "site_code": code,
                        "name": name,
                        "reason": (
                            "IDENTITY_NOT_FOUND"
                            if not identities
                            else "AMBIGUOUS_IDENTITY"
                        ),
                    }
                )
                continue
            admin_role = _resolved_admin_role(source_role, employee)
            login_id = build_eval_login_id(alias, name)
            target = (
                db.query(User)
                .options(_user_columns())
                .filter(User.login_id == login_id)
                .first()
            )
            if target is not None and target.name.strip() != name:
                login_id = build_eval_login_id(code, name)
                target = (
                    db.query(User)
                    .options(_user_columns())
                    .filter(User.login_id == login_id)
                    .first()
                )
            if target is not None and target.name.strip() != name:
                excluded.append(
                    {
                        "site_code": code,
                        "name": name,
                        "reason": "LOGIN_COLLISION",
                    }
                )
                continue
            plans.append(
                SiteAdminPlan(
                    site=site,
                    site_row=row,
                    employee_row=employee,
                    admin_role=admin_role,
                    name=name,
                    login_id=login_id,
                    action="CREATE" if target is None else "UPDATE",
                    target=target,
                )
            )
    return plans, excluded


def summarize_site_admin_plan(
    plans: list[SiteAdminPlan], excluded: list[dict[str, str]]
) -> dict[str, Any]:
    def count(values: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for value in values:
            out[value] = out.get(value, 0) + 1
        return dict(sorted(out.items()))

    return {
        "planned_count": len(plans),
        "site_count": len({plan.site.site_code for plan in plans}),
        "excluded_count": len(excluded),
        "action_counts": count([plan.action for plan in plans]),
        "admin_role_counts": count([plan.admin_role for plan in plans]),
        "exclusion_reasons": count([item["reason"] for item in excluded]),
        "password_reset_count": sum(
            plan.target is None or plan.target.password_changed_at is None
            for plan in plans
        ),
        "password_preserved_count": sum(
            plan.target is not None and plan.target.password_changed_at is not None
            for plan in plans
        ),
    }


def apply_site_admin_plan(
    db: Session,
    *,
    site_source: Path,
    employee_source: Path,
    as_of: date,
) -> dict[str, Any]:
    plans, excluded = build_site_admin_plan(
        db,
        site_source=site_source,
        employee_source=employee_source,
        as_of=as_of,
    )
    summary = summarize_site_admin_plan(plans, excluded)
    now = utc_now()
    created = 0
    updated = 0

    for plan in plans:
        employee = plan.employee_row
        birth6 = clean(employee.get("birth6"))
        person = (
            db.query(Person).filter(Person.rrn_hash == employee.get("rrn_hash")).first()
            if employee.get("rrn_hash")
            else None
        )
        user = plan.target
        if user is None:
            user = User(
                name=plan.name,
                login_id=plan.login_id,
                password_hash=get_password_hash(birth6),
                birth_date=employee.get("birth_date"),
                role=(
                    Role.SITE_FUNCTIONAL_EVAL
                    if plan.admin_role == "SITE_MANAGER"
                    else Role.SITE
                ),
                ui_type=UIType.SITE,
                site_id=plan.site.id,
                person_id=person.id if person else None,
                is_active=True,
                must_change_password=True,
                initial_password_issued=True,
                account_issued_by="site_admin_erp_bulk",
                account_issued_at=now,
            )
            db.add(user)
            db.flush()
            created += 1
        else:
            user.name = plan.name
            user.ui_type = UIType.SITE
            user.site_id = plan.site.id
            user.person_id = person.id if person else user.person_id
            user.is_active = True
            if user.role not in SITE_ACCOUNT_ROLES:
                user.role = Role.SITE
            if user.password_changed_at is None:
                user.password_hash = get_password_hash(birth6)
                user.must_change_password = True
                user.initial_password_issued = True
                user.account_issued_by = "site_admin_erp_bulk"
                user.account_issued_at = now
            db.add(user)
            updated += 1

        deployments = (
            db.query(NewSiteDeployment)
            .filter(NewSiteDeployment.site_code == plan.site.site_code)
            .all()
        )
        for deployment in deployments:
            admin = (
                db.query(NewSiteDeploymentAdministrator)
                .filter(
                    NewSiteDeploymentAdministrator.deployment_id == deployment.id,
                    NewSiteDeploymentAdministrator.name == plan.name,
                )
                .first()
            )
            if admin is not None:
                admin.login_id = plan.login_id
                if admin.role == "OTHER":
                    admin.role = plan.admin_role
                db.add(admin)

    db.commit()
    return {
        **summary,
        "mode": "apply",
        "created_count": created,
        "updated_count": updated,
    }
