from fastapi import APIRouter, HTTPException, Query, status

from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.search.service import (
    get_risk_assessment_designation,
    risk_item_available_for_contractor,
    search_risk_library,
    upsert_risk_assessment_designation,
    upsert_risk_library_site_assignment,
)
from app.modules.sites.models import Site
from app.schemas.search import (
    RiskAssessmentDesignation,
    RiskAssessmentDesignationUpdate,
    RiskLibrarySearchResponse,
    RiskLibrarySiteAssignmentRead,
    RiskLibrarySiteAssignmentUpdate,
)
from app.core.auth import DbDep


router = APIRouter(prefix="/search", tags=["search"])

SEARCH_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
    Role.ACCIDENT_ADMIN.value,
    Role.SITE.value,
    Role.HQ_OTHER.value,
}

DESIGNATION_HQ_EDIT_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
}


def _role_value(current_user) -> str | None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    return role_value


def _assert_search_access(current_user) -> None:
    role_value = _role_value(current_user)
    if role_value not in SEARCH_ALLOWED_ROLES:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Search API is allowed for HQ/SITE users only",
        )


def _resolve_site_scope(
    db,
    current_user,
    requested_site_id: int | None,
    *,
    for_edit: bool = False,
) -> Site | None:
    role_value = _role_value(current_user)
    if role_value == Role.SITE.value:
        site_id = getattr(current_user, "site_id", None)
    else:
        if for_edit and role_value not in DESIGNATION_HQ_EDIT_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only SITE or HQ safety administrators can update risk assessment assignments",
            )
        site_id = requested_site_id
    if site_id is None:
        return None
    site = db.query(Site).filter(Site.id == int(site_id)).first()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return site


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
    contractor: str | None = Query(default=None),
    site_id: int | None = Query(default=None, ge=1),
):
    _assert_search_access(current_user)
    role_value = _role_value(current_user)
    site = _resolve_site_scope(db, current_user, site_id)
    contractor_name = site.contractor_name if site is not None else contractor
    can_edit_designation = bool(
        site is not None
        and (
            role_value == Role.SITE.value
            or role_value in DESIGNATION_HQ_EDIT_ROLES
        )
    )
    result = search_risk_library(
        db,
        query=query,
        mode=mode,
        limit=limit,
        offset=offset,
        unit_work=unit_work,
        risk_type=risk_type,
        contractor_name=contractor_name,
        site_id=site.id if site is not None else None,
        can_edit_designation=can_edit_designation,
        can_print=role_value != Role.HQ_OTHER.value,
        contractor_scope_required=site is not None,
    )
    return RiskLibrarySearchResponse(**result)


@router.get(
    "/risk-assessment/designation",
    response_model=RiskAssessmentDesignation,
)
def read_risk_assessment_designation(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = Query(default=None, ge=1),
):
    _assert_search_access(current_user)
    site = _resolve_site_scope(db, current_user, site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required")
    role_value = _role_value(current_user)
    can_edit = role_value == Role.SITE.value or role_value in DESIGNATION_HQ_EDIT_ROLES
    result = get_risk_assessment_designation(db, site_id=site.id, can_edit=can_edit)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return RiskAssessmentDesignation(**result)


@router.put(
    "/risk-assessment/designation",
    response_model=RiskAssessmentDesignation,
)
def update_risk_assessment_designation(
    payload: RiskAssessmentDesignationUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = Query(default=None, ge=1),
):
    _assert_search_access(current_user)
    site = _resolve_site_scope(db, current_user, site_id, for_edit=True)
    if site is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required")
    result = upsert_risk_assessment_designation(
        db,
        site_id=site.id,
        inspector_name=payload.inspector_name,
        verifier_name=payload.verifier_name,
        appointed_on=payload.appointed_on,
        note=payload.note,
        updated_by_user_id=current_user.id,
    )
    return RiskAssessmentDesignation(**result)


@router.put(
    "/risk-library/{risk_item_id:int}/site-assignment",
    response_model=RiskLibrarySiteAssignmentRead,
)
def update_risk_library_site_assignment(
    risk_item_id: int,
    payload: RiskLibrarySiteAssignmentUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = Query(default=None, ge=1),
):
    _assert_search_access(current_user)
    site = _resolve_site_scope(db, current_user, site_id, for_edit=True)
    if site is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required")
    if not risk_item_available_for_contractor(
        db,
        risk_item_id=risk_item_id,
        contractor_name=site.contractor_name,
        contractor_scope_required=True,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk item not found for this site contractor",
        )
    try:
        result = upsert_risk_library_site_assignment(
            db,
            site_id=site.id,
            risk_item_id=risk_item_id,
            improvement_owner_name=payload.improvement_owner_name,
            improvement_verifier_name=payload.improvement_verifier_name,
            updated_by_user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "risk_item_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk item not found")
        raise
    return RiskLibrarySiteAssignmentRead(**result)
