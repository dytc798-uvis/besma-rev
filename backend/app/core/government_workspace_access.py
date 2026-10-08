"""Government workspace management and explicitly scoped, read-only previews."""
from typing import Annotated
from types import SimpleNamespace
from fastapi import Depends, HTTPException, Request
from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.core.role_preview_access import can_role_preview


def is_government_owner(user):
    # Existing account explicitly authorized by the owner; never a name-only grant.
    return (user.id == 8 and user.login_id == "hq01" and user.name == "정상익"
            and user.role == Role.ACCIDENT_ADMIN and user.ui_type == "HQ_SAFE"
            and user.is_active)


def can_manage_government(user):
    if getattr(user, "government_preview", False):
        return False
    return is_government_owner(user) or (
        user.role in {Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN}
        and not (user.role == Role.HQ_SAFE and user.login_id in {"hq01", "hq02", "hq03", "hq04", "hq05"})
    )


def government_actor(request: Request, db: DbDep, user: CurrentUserDep):
    raw = request.query_params.get("preview_site_id")
    if raw is None:
        return user
    if not can_role_preview(user.login_id):
        raise HTTPException(403, "ROLE_PREVIEW_NOT_ALLOWED")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        raise HTTPException(403, "ROLE_PREVIEW_READ_ONLY")
    from app.modules.sites.models import Site
    from app.modules.document_explorer.government_access import is_government_site_record
    from app.modules.documents.active_site_scope import in_active_scope, today_kst
    try:
        site = db.get(Site, int(raw))
    except (ValueError, TypeError):
        raise HTTPException(422, "INVALID_PREVIEW_SITE")
    if not site or not is_government_site_record(site) or not in_active_scope(site, today_kst(), "government"):
        raise HTTPException(403, "GOVERNMENT_ACTIVE_PREVIEW_SITE_REQUIRED")
    return SimpleNamespace(id=user.id, login_id=user.login_id, name=user.name,
                           role=Role.SITE, ui_type="SITE", site_id=site.id, site=site,
                           is_active=True, government_preview=True)


GovernmentUserDep = Annotated[object, Depends(government_actor)]
