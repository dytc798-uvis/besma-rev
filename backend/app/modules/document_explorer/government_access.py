"""Fail-closed access to separately prepared government-site documents."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from app.config.settings import settings
from app.core.enums import Role


PUBLIC_PREFIX = "관급 공개 양식/"
GOVERNMENT_SITE_CODES = frozenset({"24028", "25037", "25040", "25059", "25063", "26004", "26024", "26052"})
# Only inspected, blank site forms are candidates. A copy alone never grants access;
# an HQ safety officer must still explicitly enable its public folder.
PUBLIC_CANDIDATE_RELATIVE_PATHS = frozenset({
    "02. 안전점검/안전보건 점검 체크리스트(26.2.3개정).xlsx",
    "04. 작업계획서/(정전,활선 작업) 작업계획서.xlsx",
    "05. 안전교육/안전보건교육 양식(변경)-2월4일최신버젼.xlsx",
    "08. 비상사태대응/비상훈련 계획서(양식).xlsx",
    "08. 비상사태대응/비상사태대비 훈련보고서(배포용).xlsx",
    "99. 기타양식/보호구지급대장 양식.xlsx",
})
_lock = Lock()


def is_government_site_record(site: object) -> bool:
    if str(getattr(site, "site_code", "") or "").strip() in GOVERNMENT_SITE_CODES:
        return True
    contract_type = str(getattr(site, "contract_type", "") or "").strip()
    site_name = str(getattr(site, "site_name", "") or "").strip()
    return "관급" in contract_type or "공공" in contract_type or "관급" in site_name


def is_government_site(user: object) -> bool:
    role = getattr(user, "role", None)
    role = getattr(role, "value", role)
    if role not in {Role.SITE.value, Role.SITE_FUNCTIONAL_EVAL.value}:
        return False
    site = getattr(user, "site", None)
    # Unlinked or unclassified accounts receive the narrower public-only view.
    if site is None:
        return True
    return is_government_site_record(site) or not str(getattr(site, "contract_type", "") or "").strip()


def policy_path() -> Path:
    return settings.storage_root / "document-explorer" / "government-access.json"


def _read_policy() -> dict:
    try:
        data = json.loads(policy_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"schema": 2, "visible_folders": [], "file_visibility": {}}
    if not isinstance(data, dict) or data.get("schema") not in {1, 2}:
        return {"schema": 2, "visible_folders": [], "file_visibility": {}}
    folders = data.get("visible_folders") if isinstance(data.get("visible_folders"), list) else []
    files = data.get("file_visibility") if isinstance(data.get("file_visibility"), dict) else {}
    return {
        "schema": 2,
        "visible_folders": [value for value in folders if isinstance(value, str) and value.startswith(PUBLIC_PREFIX)
                            and all(part not in {"", ".", ".."} for part in value.split("/"))],
        "file_visibility": {key: value for key, value in files.items()
                            if isinstance(key, str) and isinstance(value, bool)
                            and all(part not in {"", ".", ".."} for part in key.split("/"))},
    }


def _write_policy(data: dict) -> None:
    path = policy_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def read_visible_folders() -> set[str]:
    return set(_read_policy()["visible_folders"])


def normalize_public_folder(folder: str) -> str:
    value = (folder or "").replace("\\", "/").strip("/")
    if value.startswith("base/"):
        value = value[5:]
    if not value.startswith(PUBLIC_PREFIX) or any(part in {"", ".", ".."} for part in value.split("/")):
        raise HTTPException(status_code=400, detail="Invalid public folder")
    root = settings.document_explorer_base_dir.resolve()
    candidate = (root / value).resolve()
    if root not in candidate.parents or not candidate.is_dir():
        raise HTTPException(status_code=400, detail="Public folder does not exist")
    return value


def set_folder_visibility(folder: str, visible: bool) -> list[str]:
    normalized = normalize_public_folder(folder)
    with _lock:
        data = _read_policy()
        folders = set(data["visible_folders"])
        if visible:
            folders.add(normalized)
        else:
            folders.discard(normalized)
        data["visible_folders"] = sorted(folders)
        _write_policy(data)
        return sorted(folders)


def normalize_public_file(relative_path: str) -> str:
    value = (relative_path or "").replace("\\", "/").strip("/")
    if value.startswith("base/일반 양식/"):
        value = value[len("base/일반 양식/"):]
    if not value or any(part in {"", ".", ".."} for part in value.split("/")):
        raise HTTPException(400, "Invalid document path")
    root = settings.document_explorer_base_dir.resolve()
    original = (root / "일반 양식" / value).resolve()
    public = (root / PUBLIC_PREFIX / value).resolve()
    if not ((root / "일반 양식").resolve() in original.parents and original.is_file()
            or (root / PUBLIC_PREFIX).resolve() in public.parents and public.is_file()):
        raise HTTPException(400, "Document does not exist")
    return value


def configured_file_visible(relative_path: str) -> bool:
    policy = _read_policy()
    override = policy["file_visibility"].get(relative_path)
    return override if isinstance(override, bool) else relative_path in PUBLIC_CANDIDATE_RELATIVE_PATHS


def set_file_visibility(relative_path: str, visible: bool) -> bool:
    normalized = normalize_public_file(relative_path)
    with _lock:
        data = _read_policy()
        data["file_visibility"][normalized] = bool(visible)
        _write_policy(data)
    return bool(visible)


def public_folder_visible(relative_path: str, folders: set[str] | None = None) -> bool:
    path = relative_path.replace("\\", "/").strip("/")
    if not path.startswith("base/"):
        return False
    path = path[5:]
    if not path.startswith(PUBLIC_PREFIX):
        return False
    allowed = folders if folders is not None else read_visible_folders()
    return any(path.startswith(folder.rstrip("/") + "/") for folder in allowed)


def public_file_visible(relative_path: str, folders: set[str] | None = None) -> bool:
    if not public_folder_visible(relative_path, folders):
        return False
    normalized = relative_path.replace("\\", "/").strip("/")
    relative = normalized[len("base/") + len(PUBLIC_PREFIX):]
    return configured_file_visible(relative)
