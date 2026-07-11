from datetime import datetime

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    must_change_password: bool = False
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None
    exp: datetime | None = None


class LoginRequest(BaseModel):
    login_id: str
    password: str


class UserMe(BaseModel):
    id: int
    name: str
    login_id: str
    role: str
    ui_type: str
    site_id: int | None
    person_id: int | None
    map_preference: str | None = "NAVER"
    must_change_password: bool
    needs_fe_consent: bool = False
    fe_consent_required: bool = False
    can_system_backup: bool = False

    class Config:
        from_attributes = True


class IssueAccountRequest(BaseModel):
    scope: str  # site | hq
    site_code: str | None = None
    department: str | None = None
    name: str
    birth6: str


class IssuedAccountItem(BaseModel):
    role_label: str
    name: str
    login_id: str
    initial_password: str
    site_code: str | None = None
    site_label: str | None = None


class IssueAccountResponse(BaseModel):
    scope: str
    message: str
    site_code: str | None = None
    site_label: str | None = None
    recipient_name: str | None = None
    role_label: str | None = None
    accounts: list[IssuedAccountItem]


class FindLoginIdsRequest(BaseModel):
    name: str
    birth6: str
    erp_login_id: str | None = None


class LoginIdLookupItem(BaseModel):
    login_id: str
    name: str
    role_label: str


class FindLoginIdsResponse(BaseModel):
    message: str
    accounts: list[LoginIdLookupItem]


class PublicPasswordResetRequest(BaseModel):
    name: str
    birth6: str
    erp_login_id: str
    new_password: str
    new_password_confirm: str


class PublicPasswordResetResponse(BaseModel):
    result: str = "ok"
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    new_password_confirm: str


class AdminPasswordResetResponse(BaseModel):
    """관리자 초기화로 발급된 임시 비밀번호(1회 표시). 조회 API로는 재확인 불가."""

    temporary_password: str
    message: str = "임시 비밀번호가 발급되었습니다. 사용자에게 전달한 뒤, 로그인 후 비밀번호 변경을 안내하세요."
