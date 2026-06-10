from __future__ import annotations

from app.modules.users.hq_safe_accounts import (
    HQ_FE_SAMSUNG_WEB_LOGIN_IDS,
    HQ_SAFE_ACCOUNT_SPECS,
)


def test_hq_fe_samsung_web_login_ids_include_named_staff():
    assert "안전보건-김복수" in HQ_FE_SAMSUNG_WEB_LOGIN_IDS
    assert "안전보건-정상익" in HQ_FE_SAMSUNG_WEB_LOGIN_IDS
    assert "안전보건-엄재복" in HQ_FE_SAMSUNG_WEB_LOGIN_IDS


def test_hq_account_titles():
    by_name = {spec.name: spec for spec in HQ_SAFE_ACCOUNT_SPECS}
    assert by_name["김복수"].title == "상무"
    assert by_name["정상익"].title == "차장"
    assert by_name["엄재복"].title == "대리"
