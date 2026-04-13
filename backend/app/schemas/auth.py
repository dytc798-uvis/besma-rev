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

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    new_password_confirm: str


class AdminPasswordResetResponse(BaseModel):
    """관리자 초기화로 발급된 임시 비밀번호(1회 표시). 조회 API로는 재확인 불가."""

    temporary_password: str
    message: str = "임시 비밀번호가 발급되었습니다. 사용자에게 전달한 뒤, 로그인 후 비밀번호 변경을 안내하세요."

