from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.auth import _load_erp_login_aliases
from app.config.settings import settings
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.modules.functional_eval.site_alias import build_eval_login_id
from app.modules.new_site_deployment.constants import (
    ADMIN_PROVISION_LOGIN_ROLES,
    ADMIN_ROLE_KEYS,
    ADMIN_ROLES,
    AMOUNT_SAFETY_HEALTH_MANAGER,
    AMOUNT_SAFETY_MANAGER,
    CONSTRUCTION_MANAGEMENT_NEW_SITE_EDIT_LOGINS,
    BUDGET_EDIT_ROLES,
    PROCUREMENT_EDIT_ROLES,
    PROCUREMENT_SAFETY_CHECK_LOGINS,
    REQUIRED_DOCUMENT_TYPES,
    SAFETY_DEPLOYMENT_ITEMS,
)
from app.modules.new_site_deployment.deployment_alias import derive_deployment_site_alias
from app.modules.new_site_deployment.models import (
    NewSiteDeployment,
    NewSiteDeploymentAdministrator,
    NewSiteDeploymentDocument,
    NewSiteDeploymentPhoto,
)
from app.modules.sites.models import Site
from app.modules.users.models import User

INITIAL_SITE_PASSWORD = "1111"


def _initial_site_password(name: str) -> str:
    matches = [
        row
        for row in _load_erp_login_aliases().values()
        if (row.get("name") or "").strip() == name.strip()
        and len((row.get("birth6") or "").strip()) == 6
    ]
    if len(matches) == 1:
        return matches[0]["birth6"].strip()
    return INITIAL_SITE_PASSWORD


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def compute_requirement_labels(amount: int | None) -> list[str]:
    labels: list[str] = ["관리감독자 지정 (모든 현장)"]
    if amount is None or amount <= 0:
        return labels
    if amount >= AMOUNT_SAFETY_HEALTH_MANAGER:
        labels.insert(0, "안전보건관리책임자 선임 필요")
    elif amount >= AMOUNT_SAFETY_MANAGER:
        labels.insert(0, "안전관리자 선임 필요")
    return labels


def _next_site_code(db: Session) -> str:
    rows = db.query(Site.site_code).all()
    nums = [int(c[0]) for (c,) in rows if c[0] and str(c[0]).isdigit()]
    return str(max(nums) + 1 if nums else 26001)


def _storage_root() -> Path:
    root = settings.storage_root / "new_site_deployment"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _admin_role_label(role: str) -> str:
    for key, label in ADMIN_ROLES:
        if key == role:
            return label
    return role


def _parse_administrators_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    raw = payload.get("administrators")
    if isinstance(raw, list):
        out: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip()
            name = str(item.get("name") or "").strip()
            if role in ADMIN_ROLE_KEYS and name:
                out.append({"role": role, "name": name})
        return out

    legacy_fields = (
        ("SITE_MANAGER", "site_manager_name"),
        ("GONGMU", "gongmu_name"),
        ("SAFETY", "safety_name"),
        ("CONSTRUCTION_SUPERVISOR", "construction_supervisor_name"),
    )
    out = []
    for role, field in legacy_fields:
        name = _clean_optional_str(payload.get(field))
        if name:
            out.append({"role": role, "name": name})
    return out


def _sync_legacy_mirror_fields(row: NewSiteDeployment, admins: list[dict[str, str]]) -> None:
    def _first(role: str) -> str | None:
        for adm in admins:
            if adm["role"] == role:
                return adm["name"]
        return None

    row.site_manager_name = _first("SITE_MANAGER")
    row.gongmu_name = _first("GONGMU")
    row.safety_name = _first("SAFETY")
    row.construction_supervisor_name = _first("CONSTRUCTION_SUPERVISOR")
    row.site_manager_login_id = (
        build_eval_login_id(row.site_alias, row.site_manager_name) if row.site_manager_name else None
    ) or None
    row.gongmu_login_id = (
        build_eval_login_id(row.site_alias, row.gongmu_name) if row.gongmu_name else None
    ) or None


def _sync_administrators(
    db: Session,
    row: NewSiteDeployment,
    site: Site,
    admins: list[dict[str, str]],
) -> None:
    db.query(NewSiteDeploymentAdministrator).filter(
        NewSiteDeploymentAdministrator.deployment_id == row.id
    ).delete(synchronize_session=False)

    for idx, adm in enumerate(admins):
        role = adm["role"]
        name = adm["name"]
        login_id: str | None = None
        if role in ADMIN_PROVISION_LOGIN_ROLES:
            login_id = build_eval_login_id(row.site_alias, name) or None
            if login_id:
                _provision_site_user(db, login_id=login_id, name=name, site=site)
        db.add(
            NewSiteDeploymentAdministrator(
                deployment_id=row.id,
                role=role,
                name=name,
                login_id=login_id,
                sort_order=idx,
            )
        )

    _sync_legacy_mirror_fields(row, admins)
    # sites 정본 필드: project_manager=소장, site_manager=공무.
    site.project_manager = row.site_manager_name
    site.site_manager = row.gongmu_name
    db.add(site)
    db.add(row)


def _serialize_administrator(row: NewSiteDeploymentAdministrator) -> dict[str, Any]:
    return {
        "id": row.id,
        "role": row.role,
        "role_label": _admin_role_label(row.role),
        "name": row.name,
        "login_id": row.login_id,
        "sort_order": row.sort_order,
    }


def _default_safety_checks() -> dict[str, bool]:
    return {key: False for key, _ in SAFETY_DEPLOYMENT_ITEMS}


def _can_edit_budget(user: User) -> bool:
    if _role_value(user) in BUDGET_EDIT_ROLES:
        return True
    if (user.department or "").strip().startswith("공사관리"):
        return True
    return (user.login_id or "").strip() in CONSTRUCTION_MANAGEMENT_NEW_SITE_EDIT_LOGINS


def _can_edit_procurement(user: User) -> bool:
    return _role_value(user) in PROCUREMENT_EDIT_ROLES


def _can_edit_safety_checks(user: User) -> bool:
    rv = _role_value(user)
    if rv in {"HQ_SAFE", "HQ_SAFE_ADMIN", "SUPER_ADMIN"}:
        return True
    if (user.department or "").strip().startswith("공사관리"):
        return True
    login = (user.login_id or "").strip()
    return login in PROCUREMENT_SAFETY_CHECK_LOGINS


def _provision_site_user(
    db: Session,
    *,
    login_id: str,
    name: str,
    site: Site,
    must_change_password: bool = True,
) -> User:
    initial_password = _initial_site_password(name)
    user = db.query(User).filter(User.login_id == login_id).first()
    if user is None:
        user = User(
            name=name,
            login_id=login_id,
            password_hash=get_password_hash(initial_password),
            role=Role.SITE,
            ui_type=UIType.SITE,
            site_id=site.id,
            must_change_password=must_change_password,
            is_active=True,
        )
        db.add(user)
    else:
        user.name = name
        user.role = Role.SITE
        user.ui_type = UIType.SITE
        user.site_id = site.id
        user.is_active = True
        if must_change_password and user.password_changed_at is None:
            user.password_hash = get_password_hash(initial_password)
            user.must_change_password = True
        db.add(user)
    return user


def _ensure_site_for_deployment(db: Session, row: NewSiteDeployment, user: User) -> Site:
    if row.site_id:
        site = db.query(Site).filter(Site.id == row.site_id).first()
        if site:
            return site

    site_code = row.site_code or _next_site_code(db)
    site = db.query(Site).filter(Site.site_code == site_code).first()
    if site is None:
        site = Site(
            site_code=site_code,
            site_name=row.site_name[:200],
            contractor_name=row.contractor,
            project_amount=row.construction_amount,
            project_manager=row.site_manager_name,
            site_manager=row.gongmu_name,
            created_by_user_id=user.id,
        )
        db.add(site)
        db.flush()
    else:
        site.site_name = row.site_name[:200]
        site.contractor_name = row.contractor
        site.project_amount = row.construction_amount
        site.project_manager = row.site_manager_name
        site.site_manager = row.gongmu_name
        db.add(site)

    row.site_id = site.id
    row.site_code = site.site_code
    return site


def _recompute_complete(row: NewSiteDeployment) -> bool:
    checks = row.safety_checks_json or {}
    # "주황색(관리자 미배치)"는 소장/공무 배치 누락을 기준으로 함.
    # 안전(관리자)·공사(관리감독자)는 현재 완료 판정에 포함하지 않음(기존 동작 호환).
    admins_ok = bool(row.site_manager_name) and bool(row.gongmu_name)
    procurement_ok = row.container_arrival_date is not None and all(
        bool(checks.get(key)) for key, _ in SAFETY_DEPLOYMENT_ITEMS
    )
    photo_keys = {p.item_key for p in row.photos}
    photos_ok = all(key in photo_keys for key, _ in SAFETY_DEPLOYMENT_ITEMS)
    doc_types = {d.doc_type for d in row.documents}
    docs_ok = all(key in doc_types for key, _ in REQUIRED_DOCUMENT_TYPES)
    return admins_ok and procurement_ok and photos_ok and docs_ok


def serialize_deployment(row: NewSiteDeployment) -> dict[str, Any]:
    checks = row.safety_checks_json or _default_safety_checks()
    computed_complete = _recompute_complete(row)
    photo_map = {p.item_key: _serialize_photo(p) for p in row.photos}
    doc_map = {d.doc_type: _serialize_document(d) for d in row.documents}
    admins = [_serialize_administrator(a) for a in sorted(row.administrators, key=lambda x: x.sort_order)]
    return {
        "id": row.id,
        "site_id": row.site_id,
        "site_code": row.site_code,
        "site_alias": row.site_alias,
        "contractor": row.contractor,
        "site_name": row.site_name,
        "construction_amount": row.construction_amount,
        "construction_period": row.construction_period,
        "administrators": admins,
        "admin_role_options": [{"key": k, "label": lb} for k, lb in ADMIN_ROLES],
        "site_manager_name": row.site_manager_name,
        "gongmu_name": row.gongmu_name,
        "safety_name": row.safety_name,
        "construction_supervisor_name": row.construction_supervisor_name,
        "site_manager_login_id": row.site_manager_login_id,
        "gongmu_login_id": row.gongmu_login_id,
        "container_arrival_date": row.container_arrival_date.isoformat() if row.container_arrival_date else None,
        "safety_checks": checks,
        "requirement_labels": compute_requirement_labels(row.construction_amount),
        "safety_items": [{"key": k, "label": lb} for k, lb in SAFETY_DEPLOYMENT_ITEMS],
        "required_documents": [{"key": k, "label": lb} for k, lb in REQUIRED_DOCUMENT_TYPES],
        "photos": photo_map,
        "documents": doc_map,
        "is_complete": computed_complete,
        "needs_highlight": not computed_complete,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _serialize_photo(row: NewSiteDeploymentPhoto) -> dict[str, Any]:
    return {
        "id": row.id,
        "item_key": row.item_key,
        "original_filename": row.original_filename,
        "uploaded_at": row.uploaded_at,
        "download_url": f"/new-site-deployment/files/photos/{row.id}",
    }


def _serialize_document(row: NewSiteDeploymentDocument) -> dict[str, Any]:
    return {
        "id": row.id,
        "doc_type": row.doc_type,
        "original_filename": row.original_filename,
        "uploaded_at": row.uploaded_at,
        "download_url": f"/new-site-deployment/files/documents/{row.id}",
    }


def list_deployments(db: Session, user: User) -> list[dict[str, Any]]:
    q = db.query(NewSiteDeployment).order_by(NewSiteDeployment.id.desc())
    if _role_value(user) == Role.SITE.value and user.site_id:
        q = q.filter(NewSiteDeployment.site_id == user.site_id)
    rows = q.all()
    return [serialize_deployment(r) for r in rows]


def menu_status(db: Session, user: User) -> dict[str, Any]:
    items = list_deployments(db, user)
    incomplete = [i for i in items if not i.get("is_complete")]
    return {
        "incomplete_count": len(incomplete),
        "needs_highlight": len(incomplete) > 0,
        "password_warning": _role_value(user) in {"HQ_BUDGET_ESTIMATE", "HQ_OUTSOURCING_PURCHASE"}
        and bool(user.must_change_password),
    }


def get_deployment(db: Session, user: User, deployment_id: int) -> dict[str, Any]:
    row = db.query(NewSiteDeployment).filter(NewSiteDeployment.id == deployment_id).first()
    if row is None:
        raise ValueError("NOT_FOUND")
    if _role_value(user) == Role.SITE.value and user.site_id and row.site_id != user.site_id:
        raise ValueError("FORBIDDEN")
    return serialize_deployment(row)


def get_site_deployment(db: Session, user: User) -> dict[str, Any] | None:
    if not user.site_id:
        return None
    row = (
        db.query(NewSiteDeployment)
        .filter(NewSiteDeployment.site_id == user.site_id)
        .order_by(NewSiteDeployment.id.desc())
        .first()
    )
    return serialize_deployment(row) if row else None


def create_deployment(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    if not _can_edit_budget(user):
        raise ValueError("FORBIDDEN")
    contractor = (payload.get("contractor") or "").strip() or None
    site_name = (payload.get("site_name") or "").strip()
    if not site_name:
        raise ValueError("SITE_NAME_REQUIRED")
    alias = derive_deployment_site_alias(contractor, site_name)
    admins = _parse_administrators_payload(payload)
    row = NewSiteDeployment(
        site_alias=alias,
        contractor=contractor,
        site_name=site_name,
        construction_amount=_parse_amount(payload.get("construction_amount")),
        construction_period=_clean_optional_str(payload.get("construction_period")),
        safety_checks_json=_default_safety_checks(),
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    site = _ensure_site_for_deployment(db, row, user)
    _sync_administrators(db, row, site, admins)
    row.is_complete = _recompute_complete(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_deployment(row)


def update_deployment_budget(db: Session, user: User, deployment_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not _can_edit_budget(user):
        raise ValueError("FORBIDDEN")
    row = db.query(NewSiteDeployment).filter(NewSiteDeployment.id == deployment_id).first()
    if row is None:
        raise ValueError("NOT_FOUND")

    for field in ("contractor", "site_name", "construction_period"):
        if field in payload:
            val = _clean_optional_str(payload.get(field)) if field != "site_name" else (payload.get(field) or "").strip()
            if field == "site_name" and not val:
                raise ValueError("SITE_NAME_REQUIRED")
            setattr(row, field, val if field != "site_name" else val)

    if "construction_amount" in payload:
        row.construction_amount = _parse_amount(payload.get("construction_amount"))

    row.site_alias = derive_deployment_site_alias(row.contractor, row.site_name)
    row.updated_by_user_id = user.id
    row.updated_at = utc_now()

    site = _ensure_site_for_deployment(db, row, user)
    if "administrators" in payload or any(
        k in payload
        for k in (
            "site_manager_name",
            "gongmu_name",
            "safety_name",
            "construction_supervisor_name",
        )
    ):
        admins = _parse_administrators_payload(payload)
        _sync_administrators(db, row, site, admins)

    row.is_complete = _recompute_complete(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_deployment(row)


def update_deployment_procurement(
    db: Session, user: User, deployment_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    if not _can_edit_procurement(user):
        raise ValueError("FORBIDDEN")
    row = db.query(NewSiteDeployment).filter(NewSiteDeployment.id == deployment_id).first()
    if row is None:
        raise ValueError("NOT_FOUND")

    if "container_arrival_date" in payload:
        raw = payload.get("container_arrival_date")
        row.container_arrival_date = date.fromisoformat(str(raw)) if raw else None

    if "safety_checks" in payload:
        if not _can_edit_safety_checks(user):
            raise ValueError("SAFETY_CHECK_FORBIDDEN")
        incoming = payload.get("safety_checks") or {}
        checks = row.safety_checks_json or _default_safety_checks()
        for key, _ in SAFETY_DEPLOYMENT_ITEMS:
            if key in incoming:
                checks[key] = bool(incoming[key])
        row.safety_checks_json = checks

    row.updated_by_user_id = user.id
    row.updated_at = utc_now()
    row.is_complete = _recompute_complete(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_deployment(row)


def _save_upload_file(deployment_id: int, subdir: str, filename: str, src: Path) -> str:
    safe = re.sub(r"[^\w.\-가-힣]", "_", filename)[:180]
    dest_dir = _storage_root() / str(deployment_id) / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{utc_now().strftime('%Y%m%d%H%M%S')}_{safe}"
    shutil.copy2(src, dest)
    return str(dest.relative_to(settings.storage_root)).replace("\\", "/")


def upload_photo(
    db: Session,
    user: User,
    deployment_id: int,
    item_key: str,
    *,
    file_path: Path,
    original_filename: str,
) -> dict[str, Any]:
    if _role_value(user) != Role.SITE.value:
        raise ValueError("SITE_ONLY")
    row = db.query(NewSiteDeployment).filter(NewSiteDeployment.id == deployment_id).first()
    if row is None or row.site_id != user.site_id:
        raise ValueError("FORBIDDEN")
    valid_keys = {k for k, _ in SAFETY_DEPLOYMENT_ITEMS}
    if item_key not in valid_keys:
        raise ValueError("INVALID_ITEM")

    existing = (
        db.query(NewSiteDeploymentPhoto)
        .filter(NewSiteDeploymentPhoto.deployment_id == deployment_id, NewSiteDeploymentPhoto.item_key == item_key)
        .first()
    )
    rel = _save_upload_file(deployment_id, "photos", original_filename, file_path)
    if existing:
        existing.stored_path = rel
        existing.original_filename = original_filename
        existing.uploaded_by_user_id = user.id
        existing.uploaded_at = utc_now()
        db.add(existing)
    else:
        db.add(
            NewSiteDeploymentPhoto(
                deployment_id=deployment_id,
                item_key=item_key,
                stored_path=rel,
                original_filename=original_filename,
                uploaded_by_user_id=user.id,
            )
        )
    row.is_complete = _recompute_complete(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_deployment(row)


def upload_document(
    db: Session,
    user: User,
    deployment_id: int,
    doc_type: str,
    *,
    file_path: Path,
    original_filename: str,
) -> dict[str, Any]:
    if _role_value(user) != Role.SITE.value:
        raise ValueError("SITE_ONLY")
    row = db.query(NewSiteDeployment).filter(NewSiteDeployment.id == deployment_id).first()
    if row is None or row.site_id != user.site_id:
        raise ValueError("FORBIDDEN")
    valid = {k for k, _ in REQUIRED_DOCUMENT_TYPES}
    if doc_type not in valid:
        raise ValueError("INVALID_DOC")

    existing = (
        db.query(NewSiteDeploymentDocument)
        .filter(
            NewSiteDeploymentDocument.deployment_id == deployment_id,
            NewSiteDeploymentDocument.doc_type == doc_type,
        )
        .first()
    )
    rel = _save_upload_file(deployment_id, "documents", original_filename, file_path)
    if existing:
        existing.stored_path = rel
        existing.original_filename = original_filename
        existing.uploaded_by_user_id = user.id
        existing.uploaded_at = utc_now()
        db.add(existing)
    else:
        db.add(
            NewSiteDeploymentDocument(
                deployment_id=deployment_id,
                doc_type=doc_type,
                stored_path=rel,
                original_filename=original_filename,
                uploaded_by_user_id=user.id,
            )
        )
    row.is_complete = _recompute_complete(row)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_deployment(row)


def resolve_stored_file(db: Session, *, kind: str, file_id: int) -> tuple[Path, str]:
    if kind == "photos":
        row = db.query(NewSiteDeploymentPhoto).filter(NewSiteDeploymentPhoto.id == file_id).first()
    elif kind == "documents":
        row = db.query(NewSiteDeploymentDocument).filter(NewSiteDeploymentDocument.id == file_id).first()
    else:
        raise ValueError("INVALID_KIND")
    if row is None:
        raise ValueError("NOT_FOUND")
    path = settings.storage_root / row.stored_path
    if not path.is_file():
        raise ValueError("FILE_MISSING")
    return path, row.original_filename


def _parse_amount(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, int):
        return raw
    text = re.sub(r"[^\d]", "", str(raw))
    return int(text) if text else None


def _clean_optional_str(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None
