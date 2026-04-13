import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.config.security import get_password_hash
from app.core.auth import DbDep, get_current_user
from app.core.enums import Role
from app.core.permissions import require_roles
from app.modules.users.models import User
from app.schemas.auth import AdminPasswordResetResponse, UserMe


router = APIRouter(prefix="/users", tags=["users"])

ALLOWED_MAP_PREFERENCES = {"NAVER", "TMAP"}


class UpdateMapPreferenceRequest(BaseModel):
    map_preference: str


@router.get("/me", response_model=UserMe)
def read_me(current_user: User = Depends(get_current_user)):
    return UserMe.model_validate(current_user)


@router.get("", response_model=list[UserMe])
def list_users(
    db: DbDep,
    _: User = Depends(require_roles(Role.HQ_SAFE, Role.HQ_OTHER)),
):
    return [UserMe.model_validate(u) for u in db.query(User).all()]


@router.patch("/me/map-preference", response_model=UserMe)
def update_my_map_preference(
    payload: UpdateMapPreferenceRequest,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    value = (payload.map_preference or "").strip().upper()
    if value not in ALLOWED_MAP_PREFERENCES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="map_preference must be NAVER or TMAP",
        )
    current_user.map_preference = value
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserMe.model_validate(current_user)


@router.post(
    "/{user_id}/admin-reset-password",
    response_model=AdminPasswordResetResponse,
)
def admin_reset_user_password(
    user_id: int,
    db: DbDep,
    _: User = Depends(require_roles(Role.HQ_SAFE, Role.HQ_OTHER)),
):
    """
    관리자 전용: 대상 사용자 비밀번호를 임시 값으로 덮어쓴다.
    기존 비밀번호는 해시만 보존되며 평문 조회는 불가하다.
    """
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="USER_NOT_FOUND")
    if not target.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="USER_INACTIVE")

    temporary_password = secrets.token_urlsafe(9)
    target.password_hash = get_password_hash(temporary_password)
    target.must_change_password = True
    target.password_changed_at = None
    db.add(target)
    db.commit()
    db.refresh(target)

    return AdminPasswordResetResponse(temporary_password=temporary_password)

