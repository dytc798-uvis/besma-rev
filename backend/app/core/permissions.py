from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user_with_bypass
from app.core.enums import Role, UIType
from app.modules.users.models import User

CurrentUserDep = Annotated[User, Depends(get_current_user_with_bypass)]


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
