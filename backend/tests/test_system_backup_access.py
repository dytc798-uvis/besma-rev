from app.core.system_backup_access import SYSTEM_BACKUP_ALLOWED_LOGIN_ID, can_system_backup


def test_can_system_backup_only_allowed_login():
    assert can_system_backup(SYSTEM_BACKUP_ALLOWED_LOGIN_ID) is True
    assert can_system_backup("  안전보건-정상익") is False
    assert can_system_backup("안전보건-조동문") is False
    assert can_system_backup("") is False
    assert can_system_backup(None) is False
