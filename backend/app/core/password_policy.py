"""
비밀번호 정책은 이 모듈에서만 정의한다.
정책 강화 시 `MIN_PASSWORD_LENGTH` 및 `validate_password_policy`만 조정하면 된다.
"""

from __future__ import annotations

# 향후 8자·특수문자 등으로 확장할 때 이 상수와 validate_password_policy만 수정한다.
MIN_PASSWORD_LENGTH = 4


def validate_password_policy(password: str) -> None:
    """
    비밀번호가 정책을 만족하는지 검사한다.

    Raises:
        ValueError: 정책 위반 시. args[0]은 API detail 문자열로 그대로 쓸 수 있다.
    """
    raw = password if password is not None else ""
    stripped = raw.strip()
    if not stripped:
        raise ValueError("NEW_PASSWORD_REQUIRED")
    if len(stripped) < MIN_PASSWORD_LENGTH:
        raise ValueError("비밀번호는 4자리 이상이어야 합니다.")
