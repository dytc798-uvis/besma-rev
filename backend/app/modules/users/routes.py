from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.auth import DbDep, get_current_user
from app.core.enums import Role
from app.core.permissions import require_roles
from app.modules.users.models import User
from app.schemas.auth import UserMe


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

