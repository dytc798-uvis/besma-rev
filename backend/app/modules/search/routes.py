from fastapi import APIRouter, Query

from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.search.service import search_risk_library
from app.schemas.search import RiskLibrarySearchResponse
from app.core.auth import DbDep


router = APIRouter(prefix="/search", tags=["search"])

SEARCH_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
    Role.SITE.value,
    Role.HQ_OTHER.value,
}


def _assert_search_access(current_user) -> None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    if role_value not in SEARCH_ALLOWED_ROLES:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Search API is allowed for HQ/SITE users only",
        )


@router.get("/risk-library", response_model=RiskLibrarySearchResponse)
def search_risk_library_endpoint(
    db: DbDep,
    current_user: CurrentUserDep,
    query: str = Query(default=""),
    mode: str = Query(default="quick"),
    limit: int = Query(default=30, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    unit_work: str | None = Query(default=None),
    risk_type: str | None = Query(default=None),
):
    _assert_search_access(current_user)
    result = search_risk_library(
        db,
        query=query,
        mode=mode,
        limit=limit,
        offset=offset,
        unit_work=unit_work,
        risk_type=risk_type,
    )
    return RiskLibrarySearchResponse(**result)
