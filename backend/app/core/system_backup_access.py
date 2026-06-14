"""전체 시스템 백업 — 허용 계정 (서버 이전·재해 복구용)."""

from __future__ import annotations

SYSTEM_BACKUP_ALLOWED_LOGIN_ID = "안전보건-정상익"


def can_system_backup(login_id: str | None) -> bool:
    return (login_id or "").strip() == SYSTEM_BACKUP_ALLOWED_LOGIN_ID
