from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user_with_bypass
from app.core.enums import Role, UIType
from app.modules.users.models import User

CurrentUserDep = Annotated[User, Depends(get_current_user_with_bypass)]

# 본사 안전(HQ_SAFE) UI에서 공통으로 쓰는 문서·취합·탐색 API.
# 데모의 hq01(ACCIDENT_ADMIN)처럼 사고 전용 역할이어도 동일 UI를 쓰면 403이 나지 않게 포함한다.
HQ_SAFE_WORKSPACE_ROLES: frozenset[Role] = frozenset(
    {Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN, Role.ACCIDENT_ADMIN}
)

FUNCTIONAL_EVAL_VIEWER_ROLES: frozenset[Role] = frozenset({Role.FUNCTIONAL_EVAL_VIEWER})

FE_HQ_READ_ROLES: frozenset[Role] = HQ_SAFE_WORKSPACE_ROLES | FUNCTIONAL_EVAL_VIEWER_ROLES
FE_HQ_MONITORING_ROLES: frozenset[Role] = frozenset(
    {Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN, Role.HQ_OTHER}
)

FE_HQ_ADMIN_ROLES: frozenset[Role] = frozenset({Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN})


def assert_hq_safe_workspace(user: User) -> None:
    if user.role not in HQ_SAFE_WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def assert_document_file_access(user: User, *, site_id: int | None) -> None:
    """Apply the common authorization boundary for document file contents."""
    if user.role in HQ_SAFE_WORKSPACE_ROLES:
        return
    if user.role in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}:
        if user.site_id is not None and site_id == user.site_id:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def assert_fe_hq_read(user: User) -> None:
    if user.role not in FE_HQ_READ_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def assert_fe_hq_monitoring(user: User) -> None:
    if user.role not in FE_HQ_MONITORING_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def assert_fe_hq_admin(user: User) -> None:
    if user.role not in FE_HQ_ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def is_functional_eval_viewer(user: User) -> bool:
    return user.role == Role.FUNCTIONAL_EVAL_VIEWER


def require_roles(*allowed_roles: Role):
    def dependency(user: CurrentUserDep) -> User:
        if user.role not in {r.value for r in allowed_roles}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return user

    return dependency


def require_ui_types(*allowed_ui_types: UIType):
    def dependency(user: CurrentUserDep) -> User:
        if user.ui_type not in {u.value for u in allowed_ui_types}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not allowed ui_type",
            )
        return user

    return dependency
