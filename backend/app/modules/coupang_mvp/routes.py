from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from app.config.settings import settings
from app.core.datetime_utils import utc_now
from app.core.permissions import CurrentUserDep
from app.modules.coupang_mvp.schemas import (
    CoupangDocumentUpsert,
    CoupangWorkbookExportRequest,
)
from app.modules.coupang_mvp.xlsx_export import generate_submission_workbook


router = APIRouter(prefix="/coupang-mvp", tags=["coupang-mvp"])

_LEDGER_LOCK = Lock()
_MAX_IMAGE_BYTES = 15 * 1024 * 1024
_MAX_DRAWING_OBJECTS = 100
_MAX_DRAWING_JSON_BYTES = 1_500_000
_ALLOWED_IMAGES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
_ASSET_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_PILOT_LOGIN_ID = "안전보건-정상익"
_PILOT_SITE_ID = 101
_PILOT_SITE_NAME = "[3.쿠팡] YAN 5FC(양지) 전기공사"


def _assert_coupang_access(user) -> None:
    if (getattr(user, "login_id", "") or "").strip() != _PILOT_LOGIN_ID:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="정식 공개 전 내부 실험 기능입니다.",
        )


def _pilot_site_id() -> int:
    return _PILOT_SITE_ID


def _root() -> Path:
    target = settings.storage_root / "coupang-mvp"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _assets_dir(site_id: int) -> Path:
    target = _root() / "assets" / str(int(site_id))
    target.mkdir(parents=True, exist_ok=True)
    return target


def _ledger_path() -> Path:
    return _root() / "documents.json"


def _template_path() -> Path:
    return _root() / "templates" / "coupang-yangji5-v1.xlsx"


def _read_rows() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail="쿠팡 MVP 저장 원장을 읽을 수 없습니다.") from exc
    if not isinstance(payload, list):
        raise HTTPException(status_code=500, detail="쿠팡 MVP 저장 원장 형식이 올바르지 않습니다.")
    return [row for row in payload if isinstance(row, dict)]


def _write_rows(rows: list[dict[str, Any]]) -> None:
    path = _ledger_path()
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    data = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
    try:
        with temp.open("wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id") or 0) for row in rows), default=0) + 1


def _validate_drawing(drawing: dict[str, Any]) -> None:
    encoded = json.dumps(drawing, ensure_ascii=False).encode("utf-8")
    if len(encoded) > _MAX_DRAWING_JSON_BYTES:
        raise HTTPException(status_code=413, detail="도면 편집 데이터가 너무 큽니다.")
    objects = drawing.get("objects", [])
    if not isinstance(objects, list) or len(objects) > _MAX_DRAWING_OBJECTS:
        raise HTTPException(status_code=400, detail=f"도면 객체는 {_MAX_DRAWING_OBJECTS}개 이하만 저장할 수 있습니다.")
    for value in (drawing.get("background_asset_id"), *(obj.get("asset_id") for obj in objects if isinstance(obj, dict))):
        if value in {None, ""}:
            continue
        if not isinstance(value, str) or not _ASSET_ID_PATTERN.fullmatch(value):
            raise HTTPException(status_code=400, detail="도면 이미지 식별자가 올바르지 않습니다.")


def _public_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


@router.get("/access")
def access_info(current_user: CurrentUserDep):
    _assert_coupang_access(current_user)
    return {
        "available": True,
        "pilot_only": True,
        "site_id": _pilot_site_id(),
        "site_name": _PILOT_SITE_NAME,
        "defaults": {
            "contractor_name": "부현전기",
            "hazard": "안전고리 미체결로 인한 추락 위험",
            "control": "적정 안전고리 체결 및 관리감독자 확인",
            "workplace": "지하1층 2번코어",
        },
    }


@router.get("/documents")
def list_documents(current_user: CurrentUserDep):
    _assert_coupang_access(current_user)
    items = [
        _public_row(row)
        for row in _read_rows()
        if int(row.get("site_id") or 0) == _pilot_site_id()
    ]
    items.sort(key=lambda row: (row.get("work_date") or "", row.get("updated_at") or ""), reverse=True)
    return {"items": items}


@router.get("/documents/{document_id}")
def get_document(document_id: int, current_user: CurrentUserDep):
    _assert_coupang_access(current_user)
    row = next(
        (
            item
            for item in _read_rows()
            if int(item.get("id") or 0) == document_id
            and int(item.get("site_id") or 0) == _pilot_site_id()
        ),
        None,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="저장된 문서를 찾을 수 없습니다.")
    return _public_row(row)


@router.post("/documents")
def create_document(payload: CoupangDocumentUpsert, current_user: CurrentUserDep):
    _assert_coupang_access(current_user)
    _validate_drawing(payload.drawing)
    now = utc_now().isoformat()
    with _LEDGER_LOCK:
        rows = _read_rows()
        row = {
            "id": _next_id(rows),
            "site_id": _pilot_site_id(),
            "site_name": _PILOT_SITE_NAME,
            "created_by_user_id": current_user.id,
            "created_by_name": current_user.name,
            "created_at": now,
            "updated_at": now,
            **payload.model_dump(mode="json"),
        }
        rows.append(row)
        _write_rows(rows)
    return _public_row(row)


@router.put("/documents/{document_id}")
def update_document(document_id: int, payload: CoupangDocumentUpsert, current_user: CurrentUserDep):
    _assert_coupang_access(current_user)
    _validate_drawing(payload.drawing)
    with _LEDGER_LOCK:
        rows = _read_rows()
        row = next(
            (
                item
                for item in rows
                if int(item.get("id") or 0) == document_id
                and int(item.get("site_id") or 0) == _pilot_site_id()
            ),
            None,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="저장된 문서를 찾을 수 없습니다.")
        row.update(payload.model_dump(mode="json"))
        row["updated_at"] = utc_now().isoformat()
        row["updated_by_user_id"] = current_user.id
        row["updated_by_name"] = current_user.name
        _write_rows(rows)
    return _public_row(row)


@router.post("/documents/{document_id}/export-xlsx")
def export_document_workbook(
    document_id: int,
    payload: CoupangWorkbookExportRequest,
    current_user: CurrentUserDep,
):
    _assert_coupang_access(current_user)
    row = next(
        (
            item
            for item in _read_rows()
            if int(item.get("id") or 0) == document_id
            and int(item.get("site_id") or 0) == _pilot_site_id()
        ),
        None,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="저장된 문서를 찾을 수 없습니다.")
    filename = f"{row.get('work_date')}_{row.get('floor')}_쿠팡_제출서류.xlsx"
    safe_name = re.sub(r"[^0-9A-Za-z가-힣_.-]+", "_", filename)
    output = _root() / "exports" / str(_pilot_site_id()) / f"{uuid.uuid4().hex}_{safe_name}"
    try:
        generate_submission_workbook(
            _template_path(),
            output,
            row,
            payload.drawing_png,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    response = FileResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=safe_name,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.post("/assets")
async def upload_asset(current_user: CurrentUserDep, file: UploadFile = File(...)):
    _assert_coupang_access(current_user)
    media_type = (file.content_type or "").lower()
    suffix = _ALLOWED_IMAGES.get(media_type)
    if suffix is None:
        raise HTTPException(status_code=400, detail="JPG, PNG 또는 WEBP 이미지만 업로드할 수 있습니다.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 이미지는 업로드할 수 없습니다.")
    if len(content) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="이미지는 15MB 이하만 업로드할 수 있습니다.")
    site_assets = _assets_dir(_pilot_site_id())
    temp = site_assets / f".verify-{uuid.uuid4().hex}{suffix}"
    temp.write_bytes(content)
    try:
        with Image.open(temp) as image:
            image.verify()
        with Image.open(temp) as image:
            width, height = image.size
        if width < 10 or height < 10 or width > 12000 or height > 12000:
            raise HTTPException(status_code=400, detail="이미지 크기가 허용 범위를 벗어났습니다.")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="손상되었거나 지원하지 않는 이미지입니다.") from exc
    finally:
        temp.unlink(missing_ok=True)
    asset_id = uuid.uuid4().hex
    target = site_assets / f"{asset_id}{suffix}"
    target.write_bytes(content)
    return {
        "asset_id": asset_id,
        "filename": Path(file.filename or f"image{suffix}").name[:255],
        "content_type": media_type,
        "width": width,
        "height": height,
        "content_url": f"/coupang-mvp/assets/{asset_id}",
    }


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, current_user: CurrentUserDep):
    _assert_coupang_access(current_user)
    if not _ASSET_ID_PATTERN.fullmatch(asset_id):
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
    candidates = [
        path
        for path in _assets_dir(_pilot_site_id()).glob(f"{asset_id}.*")
        if path.is_file()
    ]
    if len(candidates) != 1:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
    path = candidates[0]
    content_type = {
        ".jpg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    response = FileResponse(path, media_type=content_type)
    response.headers["Cache-Control"] = "private, max-age=3600"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
