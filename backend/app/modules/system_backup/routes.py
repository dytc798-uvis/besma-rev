from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.core.auth import get_current_user
from app.core.system_backup_access import can_system_backup
from app.modules.system_backup.service import build_full_backup_zip
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system-backup", tags=["system-backup"])

_pending_zips: dict[str, tuple[Path, int]] = {}


def _require_backup_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    if not can_system_backup(current_user.login_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System backup is not allowed for this account",
        )
    return current_user


@router.get("/access")
def backup_access(current_user: Annotated[User, Depends(get_current_user)]) -> dict:
    return {"allowed": can_system_backup(current_user.login_id)}


@router.post("/prepare-download")
def prepare_download(current_user: Annotated[User, Depends(_require_backup_user)]) -> dict:
    """DB·storage·서버 소스를 ZIP으로 묶고 다운로드 토큰을 반환한다."""
    result = build_full_backup_zip(created_by_login_id=current_user.login_id)
    token = result.zip_path.name
    _pending_zips[token] = (result.zip_path, int(current_user.id))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"besma-full-backup-{stamp}.zip"
    logger.info(
        "system backup prepared user_id=%s login_id=%s files=%s zip_bytes=%s",
        current_user.id,
        current_user.login_id,
        result.file_count,
        result.manifest.get("zip_bytes"),
    )
    return {
        "download_token": token,
        "filename": filename,
        "file_count": result.file_count,
        "zip_bytes": result.manifest.get("zip_bytes"),
        "created_at": result.manifest.get("created_at"),
        "skipped_count": len(result.skipped_paths),
    }


@router.get("/download/{download_token}")
def download_backup(
    download_token: str,
    current_user: Annotated[User, Depends(_require_backup_user)],
) -> FileResponse:
    safe_name = Path(download_token).name
    pending = _pending_zips.get(safe_name)
    if pending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file not found or expired")
    zip_path, owner_user_id = pending
    if owner_user_id != int(current_user.id) or not zip_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file not found or expired")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"besma-full-backup-{stamp}.zip"

    def _cleanup() -> None:
        _pending_zips.pop(safe_name, None)
        try:
            zip_path.unlink(missing_ok=True)
        except OSError:
            pass

    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=filename,
        background=_cleanup,
    )
