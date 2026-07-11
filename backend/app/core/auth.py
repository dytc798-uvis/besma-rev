from datetime import timedelta
from typing import Annotated, Optional
import csv
import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config.security import create_access_token, verify_password
from app.config.settings import BASE_DIR, settings
from app.core.database import SessionLocal
from app.core.enums import Role
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


_ERP_LOGIN_ALIAS_FILE = BASE_DIR / "docs" / "erp_login_ids_20260711.csv"
_ERP_LOGIN_ALIAS_MTIME: float | None = None
_ERP_LOGIN_ALIAS_MAP: dict[str, dict[str, str]] = {}


def _load_erp_login_aliases() -> dict[str, dict[str, str]]:
    global _ERP_LOGIN_ALIAS_MTIME, _ERP_LOGIN_ALIAS_MAP

    try:
        stat = _ERP_LOGIN_ALIAS_FILE.stat()
    except OSError:
        _ERP_LOGIN_ALIAS_MTIME = None
        _ERP_LOGIN_ALIAS_MAP = {}
        return {}

    if _ERP_LOGIN_ALIAS_MTIME == stat.st_mtime:
        return _ERP_LOGIN_ALIAS_MAP

    aliases: dict[str, dict[str, str]] = {}
    try:
        with _ERP_LOGIN_ALIAS_FILE.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                erp_login_id = (row.get("erp_login_id") or "").strip().lower()
                name = (row.get("name") or "").strip()
                if not erp_login_id or not name:
                    continue
                aliases[erp_login_id] = {
                    "erp_login_id": erp_login_id,
                    "name": name,
                    "birth6": (row.get("birth6") or "").strip(),
                    "employee_code": (row.get("employee_code") or "").strip(),
                }
    except OSError:
        aliases = {}

    _ERP_LOGIN_ALIAS_MTIME = stat.st_mtime
    _ERP_LOGIN_ALIAS_MAP = aliases
    return aliases


def _authenticate_erp_login_alias(db: Session, login_id: str, password: str) -> Optional[user_models.User]:
    alias = _load_erp_login_aliases().get((login_id or "").strip().lower())
    if not alias:
        return None

    candidates = (
        db.query(user_models.User)
        .filter(
            user_models.User.name == alias["name"],
            user_models.User.is_active.is_(True),
            ~user_models.User.role.in_([Role.WORKER.value]),
        )
        .all()
    )
    matched = [user for user in candidates if verify_password(password, user.password_hash)]
    if len(matched) != 1:
        named_login_matched = [user for user in matched if "-" in (user.login_id or "")]
        if len(named_login_matched) == 1:
            return named_login_matched[0]
        site_matched = [user for user in matched if user.role == Role.SITE]
        if len(site_matched) == 1:
            return site_matched[0]
        return None
    return matched[0]


def authenticate_user(db: Session, login_id: str, password: str) -> Optional[user_models.User]:
    user = db.query(user_models.User).filter(user_models.User.login_id == login_id).first()
    if not user or not user.is_active:
        user = _authenticate_erp_login_alias(db, login_id, password)
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
            "/functional-eval/consent/status",
        }
        if request.url.path not in allowed_paths:
            raise HTTPException(status_code=403, detail="PASSWORD_CHANGE_REQUIRED")
    return user


def _get_dev_bypass_user(db: Session) -> user_models.User | None:
    """
    로컬/DEV 환경에서 DEV_BYPASS_AUTH=true 인 경우 사용할 테스트용 사용자 조회.
    기본적으로 hq01 계정을 우선 사용하고, 없으면 HQ_SAFE/HQ_OTHER 중 하나를 선택한다.
    """
    user = db.query(user_models.User).filter(user_models.User.login_id == "hq01").first()
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
