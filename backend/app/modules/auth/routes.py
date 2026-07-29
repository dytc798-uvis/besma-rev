from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config.security import get_password_hash, verify_password
from app.core.auth import (
    _load_erp_login_aliases,
    authenticate_user,
    create_user_access_token,
    DbDep,
    get_current_user,
)
from app.core.datetime_utils import utc_now
from app.core.password_policy import validate_password_policy
from app.core.permissions import Role
from app.modules.auth.account_issuance_service import (
    AccountIssuanceError,
    fe_consent_required,
    issue_hq_account,
    issue_site_accounts,
    user_participates_in_fe_consent,
)
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.core.system_backup_access import can_system_backup
from app.schemas.auth import (
    ChangePasswordRequest,
    FindLoginIdsRequest,
    FindLoginIdsResponse,
    IssueAccountRequest,
    IssueAccountResponse,
    IssuedAccountItem,
    LoginIdLookupItem,
    PublicPasswordResetRequest,
    PublicPasswordResetResponse,
    Token,
    UserMe,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _role_label(role: str) -> str:
    return {
        "HQ_SAFE": "본사",
        "HQ_SAFE_ADMIN": "본사",
        "ACCIDENT_ADMIN": "본사",
        "SUPER_ADMIN": "관리자",
        "HQ_OTHER": "본사",
        "SITE": "현장",
        "SITE_FUNCTIONAL_EVAL": "현장",
        "FUNCTIONAL_EVAL_VIEWER": "조회",
        "HQ_BUDGET_ESTIMATE": "본사",
        "HQ_OUTSOURCING_PURCHASE": "본사",
    }.get(role, role)


def _clean_birth6(value: str | None) -> str:
    return "".join(ch for ch in (value or "").strip() if ch.isdigit())[:6]


def _erp_alias_for_identity(name: str, birth6: str, erp_login_id: str | None = None) -> dict[str, str] | None:
    clean_name = (name or "").strip()
    clean_birth6 = _clean_birth6(birth6)
    clean_erp = (erp_login_id or "").strip().lower()
    if not clean_name or len(clean_birth6) != 6:
        return None

    aliases = _load_erp_login_aliases()
    if clean_erp:
        row = aliases.get(clean_erp)
        if row and row.get("name") == clean_name and _clean_birth6(row.get("birth6")) == clean_birth6:
            return row
        return None

    matches = [
        row
        for row in aliases.values()
        if row.get("name") == clean_name and _clean_birth6(row.get("birth6")) == clean_birth6
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _active_account_candidates(db, *, name: str) -> list[User]:
    return (
        db.query(User)
        .filter(
            User.name == name,
            User.is_active.is_(True),
            ~User.role.in_(["WORKER"]),
        )
        .order_by(User.role.asc(), User.login_id.asc())
        .all()
    )


def _select_identity_account(candidates: list[User]) -> User | None:
    if len(candidates) == 1:
        return candidates[0]
    named_login_candidates = [u for u in candidates if "-" in (u.login_id or "")]
    if len(named_login_candidates) == 1:
        return named_login_candidates[0]
    site_candidates = [u for u in candidates if getattr(u.role, "value", u.role) == "SITE"]
    if len(site_candidates) == 1:
        return site_candidates[0]
    return None


def _resolve_default_pilot_site(db, user: User) -> int | None:
    """
    SITE 怨꾩젙??site 誘몄뿰寃곗씪 ??湲곕낯 ?곌껐???꾩옣??李얜뒗??
    ?곗꽑?쒖쐞:
    1) site_code == SITE002 (?뚯씪?? 泥?씪 C18BL)
    2) site_name??C18BL ?먮뒗 泥?씪C18 ?ы븿
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
                (Site.site_name.contains("C18BL")) | (Site.site_name.contains("泥?씪C18")),
                Site.address.isnot(None),
                Site.address != "",
            )
            .order_by(Site.id.asc())
            .all()
        )
        if not candidates:
            return None
        return candidates[0]

    # 湲곗〈???곌껐??site媛 C18 以묐났??二쇱냼 ?녿뒗 ??ぉ?대㈃, 二쇱냼 ?덈뒗 C18濡?援먯젙?쒕떎.
    if user.site_id:
        current = db.query(Site).filter(Site.id == user.site_id).first()
        if current is not None:
            is_c18 = ("C18BL" in (current.site_name or "")) or ("泥?씪C18" in (current.site_name or ""))
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
        .filter((Site.site_name.contains("C18BL")) | (Site.site_name.contains("泥?씪C18")))
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
    needs_fe = user_participates_in_fe_consent(current_user)
    consent_req = fe_consent_required(db, current_user) if needs_fe else False
    base = UserMe.model_validate(current_user)
    return base.model_copy(
        update={
            "can_system_backup": can_system_backup(current_user.login_id),
            "needs_fe_consent": needs_fe,
            "fe_consent_required": consent_req,
        }
    )


@router.post("/issue-accounts", response_model=IssueAccountResponse)
def issue_accounts(payload: IssueAccountRequest, request: Request, db: DbDep) -> IssueAccountResponse:
    scope = (payload.scope or "").strip().lower()
    client_ip = request.client.host if request.client else None
    try:
        if scope == "site":
            result = issue_site_accounts(
                db,
                site_code=payload.site_code or "",
                name=payload.name,
                birth6_raw=payload.birth6,
                request_ip=client_ip,
            )
        elif scope == "hq":
            result = issue_hq_account(
                db,
                name=payload.name,
                birth6_raw=payload.birth6,
                department=payload.department,
                request_ip=client_ip,
            )
        else:
            raise AccountIssuanceError(
                "?낅젰???뺣낫? ?쇱튂?섎뒗 怨꾩젙??李얠쓣 ???놁뒿?덈떎. ?뺣낫瑜??뺤씤 ???ㅼ떆 ?쒕룄??二쇱꽭??",
                internal_reason="bad_scope",
            )
    except AccountIssuanceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    accounts = [IssuedAccountItem.model_validate(item) for item in result.get("accounts", [])]
    return IssueAccountResponse(
        scope=result["scope"],
        message=result.get("message", "?꾩씠??諛쒓툒???꾨즺?섏뿀?듬땲??"),
        site_code=result.get("site_code"),
        site_label=result.get("site_label"),
        recipient_name=result.get("recipient_name"),
        role_label=result.get("role_label"),
        accounts=accounts,
    )


@router.post("/find-login-ids", response_model=FindLoginIdsResponse)
def find_login_ids(payload: FindLoginIdsRequest, db: DbDep) -> FindLoginIdsResponse:
    alias = _erp_alias_for_identity(payload.name, payload.birth6, payload.erp_login_id)
    if not alias:
        raise HTTPException(
            status_code=400,
            detail="입력한 정보와 일치하는 계정을 찾을 수 없습니다. 이름, 생년월일, ERP 아이디를 확인해 주세요.",
        )

    candidates = _active_account_candidates(db, name=alias["name"])
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail="입력한 정보와 일치하는 계정을 찾을 수 없습니다. 이름, 생년월일, ERP 아이디를 확인해 주세요.",
        )

    accounts = [
        LoginIdLookupItem(
            login_id=user.login_id,
            name=user.name,
            role_label=_role_label(getattr(user.role, "value", user.role)),
        )
        for user in candidates
    ]
    return FindLoginIdsResponse(message="조회 가능한 아이디입니다.", accounts=accounts)


@router.post("/reset-password-public", response_model=PublicPasswordResetResponse)
def reset_password_public(payload: PublicPasswordResetRequest, db: DbDep) -> PublicPasswordResetResponse:
    alias = _erp_alias_for_identity(payload.name, payload.birth6, payload.erp_login_id)
    if not alias:
        raise HTTPException(
            status_code=400,
            detail="입력한 정보와 일치하는 계정을 찾을 수 없습니다. 이름, 생년월일, ERP 아이디를 확인해 주세요.",
        )

    if payload.new_password != payload.new_password_confirm:
        raise HTTPException(status_code=400, detail="새 비밀번호 확인이 일치하지 않습니다.")

    try:
        validate_password_policy(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    candidates = _active_account_candidates(db, name=alias["name"])
    if not candidates:
        raise HTTPException(
            status_code=400,
            detail="입력한 정보와 일치하는 계정을 찾을 수 없습니다. 이름, 생년월일, ERP 아이디를 확인해 주세요.",
        )

    new_hash = get_password_hash(payload.new_password.strip())
    changed_at = utc_now()
    for user in candidates:
        user.password_hash = new_hash
        user.must_change_password = False
        user.password_changed_at = changed_at
        db.add(user)
    db.commit()
    return PublicPasswordResetResponse(message="연결된 계정의 비밀번호가 변경되었습니다. 새 비밀번호로 로그인해 주세요.")


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

    return {"result": "ok", "message": "鍮꾨?踰덊샇媛 蹂寃쎈릺?덉뒿?덈떎."}


@router.post("/logout")
def logout() -> dict[str, str]:
    # MVP?먯꽌???좏겙 臾댄슚??釉붾옓由ъ뒪?? 誘멸뎄??
    # ?꾨줎?몄뿉???좏겙 ??젣 ??濡쒓렇???붾㈃?쇰줈 ?대룞?쒕떎.
    return {"result": "ok"}


