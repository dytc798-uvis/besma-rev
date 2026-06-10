"""안전보건실 본사(한글 ID) 웹 계정 정의 — 기능인제·삼성인정제."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HqSafeAccountSpec:
    name: str
    login_id: str
    password: str
    title: str = ""
    """기능인제 본사 + 삼성인정제(문서 탐색) 웹 사용."""
    fe_samsung_web: bool = True


# create_hq_safe_accounts / generate_hq_account_sheets 와 동기화
HQ_SAFE_ACCOUNT_SPECS: tuple[HqSafeAccountSpec, ...] = (
    HqSafeAccountSpec("조동문", "안전보건-조동문", "600321", "전무"),
    HqSafeAccountSpec("김복수", "안전보건-김복수", "721228", "상무"),
    HqSafeAccountSpec("권학상", "안전보건-권학상", "620215", "부장"),
    HqSafeAccountSpec("정상익", "안전보건-정상익", "790808", "차장"),
    HqSafeAccountSpec("엄재복", "안전보건-엄재복", "920619", "대리"),
)

HQ_FE_SAMSUNG_WEB_LOGIN_IDS: frozenset[str] = frozenset(
    spec.login_id for spec in HQ_SAFE_ACCOUNT_SPECS if spec.fe_samsung_web
)

# 하위 호환: (name, login_id, password)
HQ_SAFE_ACCOUNTS: list[tuple[str, str, str]] = [
    (spec.name, spec.login_id, spec.password) for spec in HQ_SAFE_ACCOUNT_SPECS
]
