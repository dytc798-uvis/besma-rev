ROLE_PREVIEW_ALLOWED_LOGIN_IDS = frozenset({"안전보건-정상익"})


def can_role_preview(login_id: str | None) -> bool:
    return (login_id or "").strip() in ROLE_PREVIEW_ALLOWED_LOGIN_IDS
