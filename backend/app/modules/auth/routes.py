from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config.security import get_password_hash, verify_password
from app.core.auth import authenticate_user, create_user_access_token, DbDep, get_current_user
from app.core.datetime_utils import utc_now
from app.core.password_policy import validate_password_policy
from app.core.permissions import Role
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.schemas.auth import ChangePasswordRequest, Token, UserMe


router = APIRouter(prefix="/auth", tags=["auth"])


def _resolve_default_pilot_site(db, user: User) -> int | None:
    """
    SITE 계정이 site 미연결일 때 기본 연결할 현장을 찾는다.
    우선순위:
    1) site_code == SITE002 (파일럿: 청라 C18BL)
    2) site_name에 C18BL 또는 청라C18 포함
    """
    if user.role != Role.SITE:
        return user.site_id

    def _preferred_c18_site() -> Site | None:
        by_code = db.query(Site).filter(Site.site_code == "SITE002").order_by(Site.id.asc()).first()
        if by_code is not None:
            return by_code
        candidates = (
            db.query(Site)
            .filter(
                (Site.site_name.contains("C18BL")) | (Site.site_name.contains("청라C18")),
                Site.address.isnot(None),
                Site.address != "",
            )
            .order_by(Site.id.asc())
            .all()
        )
        if not candidates:
            return None
        return candidates[0]

    # 기존에 연결된 site가 C18 중복의 주소 없는 항목이면, 주소 있는 C18로 교정한다.
    if user.site_id:
        current = db.query(Site).filter(Site.id == user.site_id).first()
        if current is not None:
            is_c18 = ("C18BL" in (current.site_name or "")) or ("청라C18" in (current.site_name or ""))
            has_address = bool((current.address or "").strip())
            if is_c18 and not has_address:
                preferred = _preferred_c18_site()
                if preferred is not None:
                    user.site_id = preferred.id
                    db.add(user)
                    db.commit()
                    db.refresh(user)
        return user.site_id

    by_code = db.query(Site).filter(Site.site_code == "SITE002").first()
    if by_code is not None:
        preferred = _preferred_c18_site()
        user.site_id = preferred.id if preferred is not None else by_code.id
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.site_id

    fallback = _preferred_c18_site() or (
        db.query(Site)
        .filter((Site.site_name.contains("C18BL")) | (Site.site_name.contains("청라C18")))
        .order_by(Site.id.asc())
        .first()
    )
    if fallback is not None:
        user.site_id = fallback.id
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.site_id
    return None


@router.post("/login", response_model=Token)
def login(
    db: DbDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect login_id or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _resolve_default_pilot_site(db, user)
    access_token = create_user_access_token(user.id)
    return Token(access_token=access_token, must_change_password=bool(user.must_change_password))


@router.get("/me", response_model=UserMe)
def me(db: DbDep, current_user=Depends(get_current_user)) -> UserMe:
    _resolve_default_pilot_site(db, current_user)
    return UserMe.model_validate(current_user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="CURRENT_PASSWORD_INCORRECT")

    if payload.new_password != payload.new_password_confirm:
        raise HTTPException(status_code=400, detail="NEW_PASSWORD_CONFIRM_MISMATCH")

    try:
        validate_password_policy(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    current_user.password_hash = get_password_hash(payload.new_password.strip())
    current_user.must_change_password = False
    current_user.password_changed_at = utc_now()
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return {"result": "ok", "message": "비밀번호가 변경되었습니다."}


@router.post("/logout")
def logout() -> dict[str, str]:
    # MVP에서는 토큰 무효화(블랙리스트) 미구현.
    # 프론트에서 토큰 삭제 후 로그인 화면으로 이동한다.
    return {"result": "ok"}

