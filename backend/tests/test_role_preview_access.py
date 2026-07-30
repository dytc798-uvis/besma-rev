from app.core.role_preview_access import can_role_preview


def test_role_preview_is_limited_to_jung_sangik_account():
    assert can_role_preview("안전보건-정상익") is True
    assert can_role_preview(" 안전보건-정상익 ") is True


def test_role_preview_rejects_other_accounts_and_alias_text():
    assert can_role_preview("sijung") is False
    assert can_role_preview("안전보건-다른사용자") is False
    assert can_role_preview(None) is False
