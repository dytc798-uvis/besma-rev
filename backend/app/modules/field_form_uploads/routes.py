from __future__ import annotations

import json
import re
import zipfile
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.datetime_utils import kst_today, utc_now
from app.core.enums import Role
from app.core.permissions import CurrentUserDep, HQ_SAFE_WORKSPACE_ROLES

router = APIRouter(prefix="/field-form-uploads", tags=["field-form-uploads"])

UPLOAD_DEADLINE = date(2026, 7, 13)
ZIP_ONLY_MESSAGE = "압축하여 업로드 바랍니다. zip 확장자만 업로드 가능합니다."
MAX_UPLOADS_PER_SITE = 2
FIELD_FORM_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
UPLOAD_LIMIT_MESSAGE = "현장별 업로드는 최대 2개까지만 가능합니다."
UPLOAD_SIZE_MESSAGE = "파일 크기는 20MB 이하만 업로드할 수 있습니다."
_LEDGER_LOCK = Lock()


def _ensure_upload_dir() -> Path:
    target = settings.storage_root / "field-form-uploads"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _ledger_path() -> Path:
    return _ensure_upload_dir() / "ledger.json"


def _read_ledger() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _write_ledger(items: list[dict[str, Any]]) -> None:
    _ledger_path().write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _next_upload_id(items: list[dict[str, Any]]) -> int:
    ids = [int(row.get("id") or 0) for row in items if isinstance(row, dict)]
    return (max(ids) if ids else 0) + 1


def _site_upload_count(items: list[dict[str, Any]], site_id: int | None) -> int:
    if site_id is None:
        return 0
    return sum(1 for row in items if int(row.get("site_id") or 0) == int(site_id))


def _safe_filename_part(value: str) -> str:
    safe = re.sub(r"[^\w.\-가-힣()]+", "_", (value or "").strip(), flags=re.UNICODE)
    safe = safe.strip("._")
    return safe[:120] or "현장"


def _role_value(current_user) -> str:
    role = getattr(current_user, "role", "")
    return getattr(role, "value", role)


def _assert_site_user(current_user) -> None:
    if _role_value(current_user) not in {Role.SITE.value, Role.SITE_FUNCTIONAL_EVAL.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SITE only")
    if not current_user.site_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SITE user must have site_id")


def _assert_hq_user(current_user) -> None:
    role = _role_value(current_user)
    hq_roles = {r.value for r in HQ_SAFE_WORKSPACE_ROLES} | {Role.HQ_OTHER.value}
    if role not in hq_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HQ only")


def _relative_storage_path(path: Path) -> str:
    return str(path.relative_to(settings.storage_root)).replace("\\", "/")


def _zip_document_count(path: Path) -> int:
    try:
        with zipfile.ZipFile(path) as zf:
            return sum(1 for info in zf.infolist() if not info.is_dir())
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ZIP_ONLY_MESSAGE) from exc


def _site_name(current_user) -> str:
    site = getattr(current_user, "site", None)
    name = getattr(site, "site_name", None)
    return str(name or f"site_{current_user.site_id}")


@router.get("/deadline")
def get_deadline() -> dict:
    return {
        "deadline": UPLOAD_DEADLINE.isoformat(),
        "upload_open": kst_today() <= UPLOAD_DEADLINE,
        "max_uploads_per_site": MAX_UPLOADS_PER_SITE,
        "max_upload_size_bytes": FIELD_FORM_UPLOAD_MAX_BYTES,
    }


def _submitted_site_rows() -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    items = sorted(_read_ledger(), key=lambda row: (row.get("uploaded_at") or "", row.get("id") or 0))
    for item in items:
        key = str(item.get("site_id") or item.get("site_name") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "rank": len(rows) + 1,
                "site_id": item.get("site_id"),
                "site_name": item.get("site_name") or "",
                "uploaded_by_name": item.get("uploaded_by_name") or "",
                "uploaded_by_login_id": item.get("uploaded_by_login_id") or "",
                "document_count": item.get("document_count") or 0,
                "uploaded_at": item.get("uploaded_at") or "",
            }
        )
        if len(rows) >= 62:
            break
    return rows


@router.get("/submitted-sites")
def list_submitted_sites(current_user: CurrentUserDep):
    return {"items": _submitted_site_rows(), "limit": 62}


@router.post("")
async def upload_field_forms(
    current_user: CurrentUserDep,
    file: Annotated[UploadFile, File(...)],
):
    _assert_site_user(current_user)
    if kst_today() > UPLOAD_DEADLINE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="현장 양식 업로드 기한이 종료되었습니다.")

    source_name = Path(file.filename or "").name
    if not source_name.lower().endswith(".zip"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=ZIP_ONLY_MESSAGE)

    if _site_upload_count(_read_ledger(), current_user.site_id) >= MAX_UPLOADS_PER_SITE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=UPLOAD_LIMIT_MESSAGE)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="빈 파일은 업로드할 수 없습니다.")
    if len(content) > FIELD_FORM_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=UPLOAD_SIZE_MESSAGE)

    storage_dir = _ensure_upload_dir()
    site_label = _safe_filename_part(_site_name(current_user))
    temp_name = f"upload_{current_user.site_id}_{int(utc_now().timestamp())}.zip"
    temp_path = storage_dir / temp_name
    temp_path.write_bytes(content)

    document_count = _zip_document_count(temp_path)
    stored_filename = f"{site_label}_({document_count})개.zip"
    final_path = storage_dir / stored_filename
    if final_path.exists():
        stamp = utc_now().strftime("%Y%m%d%H%M%S")
        final_path = storage_dir / f"{site_label}_({document_count})개_{stamp}.zip"
        stored_filename = final_path.name
    temp_path.replace(final_path)

    with _LEDGER_LOCK:
        items = _read_ledger()
        if _site_upload_count(items, current_user.site_id) >= MAX_UPLOADS_PER_SITE:
            final_path.unlink(missing_ok=True)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=UPLOAD_LIMIT_MESSAGE)
        row = {
            "id": _next_upload_id(items),
            "site_id": current_user.site_id,
            "site_name": _site_name(current_user),
            "uploaded_by_name": getattr(current_user, "name", ""),
            "uploaded_by_login_id": getattr(current_user, "login_id", ""),
            "stored_path": _relative_storage_path(final_path),
            "stored_filename": stored_filename,
            "original_filename": source_name,
            "document_count": document_count,
            "file_size": len(content),
            "uploaded_at": utc_now().isoformat(),
        }
        items.append(row)
        _write_ledger(items)

    return {**row, "download_url": f"/field-form-uploads/{row['id']}/download"}


@router.get("")
def list_uploads(current_user: CurrentUserDep):
    _assert_hq_user(current_user)
    items = sorted(_read_ledger(), key=lambda row: (row.get("uploaded_at") or "", row.get("id") or 0), reverse=True)
    return {
        "items": [{**row, "download_url": f"/field-form-uploads/{row.get('id')}/download"} for row in items],
        "deadline": UPLOAD_DEADLINE.isoformat(),
    }


@router.get("/{upload_id}/download")
def download_upload(upload_id: int, current_user: CurrentUserDep):
    _assert_hq_user(current_user)
    row = next((item for item in _read_ledger() if int(item.get("id") or 0) == upload_id), None)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload not found")
    path = settings.storage_root / str(row.get("stored_path") or "")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    filename = str(row.get("stored_filename") or path.name)
    response = FileResponse(path=path, media_type="application/zip", filename=filename)
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
