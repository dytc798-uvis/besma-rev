from fastapi import APIRouter, HTTPException, Query, status

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep, HQ_SAFE_WORKSPACE_ROLES
from app.core.role_preview_access import can_role_preview
from app.modules.sites.models import Site
from app.modules.weather.service import build_location_overview


router = APIRouter(prefix="/weather", tags=["weather"])


def _can_view(user) -> bool:
    return user.role in (
        set(HQ_SAFE_WORKSPACE_ROLES)
        | {Role.HQ_OTHER, Role.SITE, Role.SITE_FUNCTIONAL_EVAL}
    )


@router.get("/location-overview")
def location_overview(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = Query(default=None),
    latitude: float | None = Query(default=None, ge=31, le=44),
    longitude: float | None = Query(default=None, ge=123, le=133),
):
    if not _can_view(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="WEATHER_VIEW_NOT_ALLOWED")

    resolved_site_id = current_user.site_id if current_user.role in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL} else site_id
    site = None
    if resolved_site_id:
        site = db.query(Site).filter(Site.id == resolved_site_id).first()
        if site is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SITE_NOT_FOUND")
        if current_user.role in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL} and current_user.site_id != site.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SITE_SCOPE_MISMATCH")

    explicit_gps_location = latitude is not None and longitude is not None
    lat = latitude if latitude is not None else (site.latitude if site else None)
    lon = longitude if longitude is not None else (site.longitude if site else None)
    if lat is None or lon is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="LOCATION_REQUIRED")

    if site_id and current_user.role in HQ_SAFE_WORKSPACE_ROLES and not can_role_preview(current_user.login_id):
        # HQ weather viewers may see their configured HQ overview, but arbitrary site-context preview is restricted.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ROLE_PREVIEW_NOT_ALLOWED")

    try:
        return build_location_overview(
            float(lat),
            float(lon),
            None if explicit_gps_location else (site.site_name if site else None),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="WEATHER_PROVIDER_UNAVAILABLE") from exc
