from datetime import timedelta
from typing import Annotated, Optional
import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config.security import create_access_token, verify_password
from app.config.settings import settings
from app.core.database import SessionLocal
from app.modules.users import models as user_models


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]


def authenticate_user(db: Session, login_id: str, password: str) -> Optional[user_models.User]:
    user = db.query(user_models.User).filter(user_models.User.login_id == login_id).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_user_access_token(user_id: int) -> str:
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    return create_access_token(subject=user_id, expires_delta=access_token_expires)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    request: Request,
    db: DbDep,
) -> user_models.User:
    from app.config.security import decode_access_token

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except Exception:
        raise credentials_exception

    user = db.query(user_models.User).filter(user_models.User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception

    # Enforce initial password change before allowing access to services.
    if getattr(user, "must_change_password", False):
        allowed_paths = {
            "/auth/change-password",
            "/auth/logout",
            "/auth/me",
        }
        if request.url.path not in allowed_paths:
            raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
    return user


def _get_dev_bypass_user(db: Session) -> user_models.User | None:
    """
    로컬/DEV 환경에서 DEV_BYPASS_AUTH=true 인 경우 사용할 테스트용 사용자 조회.
    기본적으로 hqsafe1 계정을 우선 사용하고, 없으면 HQ_SAFE/HQ_OTHER 중 하나를 선택한다.
    """
    user = db.query(user_models.User).filter(user_models.User.login_id == "hqsafe1").first()
    if user:
        return user
    user = (
        db.query(user_models.User)
        .filter(user_models.User.role.in_(["HQ_SAFE", "HQ_OTHER"]), user_models.User.is_active.is_(True))
        .first()
    )
    return user


def get_current_user_with_bypass(
    token: Annotated[Optional[str], Depends(oauth2_scheme_optional)],
    request: Request,
    db: DbDep,
) -> user_models.User:
    """
    운영(prod)에서는 기존 OAuth2/Bearer 인증을 그대로 사용하고,
    로컬/DEV 환경에서 DEV_BYPASS_AUTH=true 이고 토큰이 없는 경우에만
    테스트용 HQ 권한 사용자를 반환한다.
    """
    bypass = os.getenv("DEV_BYPASS_AUTH", "").lower() == "true"
    is_dev_env = settings.env in ("local", "dev")

    if bypass and is_dev_env and not token:
        user = _get_dev_bypass_user(db)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="DEV_BYPASS_AUTH is enabled but no HQ test user found. Run seed_data first.",
            )
        return user

    # 그 외에는 항상 기존 토큰 기반 인증 사용
    if not token:
        # optional 스킴이므로 토큰이 없는 경우 401을 수동으로 발생시킨다.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 기존 get_current_user 로직 재사용
    return get_current_user(token=token, request=request, db=db)
