from fastapi import APIRouter, Query

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.law_registry.service import search_law_registry
from app.schemas.law_registry import LawSearchResponse

router = APIRouter(prefix="/law-registry", tags=["law-registry"])

LAW_REGISTRY_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
    Role.SITE.value,
    Role.HQ_OTHER.value,
}


def _assert_law_registry_access(current_user) -> None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    if role_value not in LAW_REGISTRY_ALLOWED_ROLES:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Law registry API is allowed for HQ/SITE users only",
        )


@router.get("/search", response_model=LawSearchResponse)
def search_law_registry_endpoint(
    db: DbDep,
    current_user: CurrentUserDep,
    q: str = Query(default=""),
    law_type: str | None = Query(default=None),
    department: str | None = Query(default=None),
    risk_tag: str | None = Query(default=None),
    work_type_tag: str | None = Query(default=None),
    document_tag: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    _assert_law_registry_access(current_user)
    result = search_law_registry(
        db,
        query=q,
        law_type=law_type,
        department=department,
        risk_tag=risk_tag,
        work_type_tag=work_type_tag,
        document_tag=document_tag,
        limit=limit,
        offset=offset,
    )
    return LawSearchResponse(**result)
