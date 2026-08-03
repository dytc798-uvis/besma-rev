from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import joinedload

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, assert_hq_safe_workspace
from app.core.image_storage import resized_jpeg_bytes
from app.modules.inspection_journals.models import InspectionJournal, InspectionJournalPhoto
from app.modules.inspection_journals.pdf_export import build_inspection_journal_pdf
from app.modules.inspection_journals.training_catalog import TRAINING_CATALOG, public_catalog


router = APIRouter(prefix="/inspection-journals", tags=["inspection-journals"])
_ALLOWED_IMAGES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024


def _assert_access(user) -> None:
    assert_hq_safe_workspace(user)


def _storage_dir(kind: str) -> Path:
    path = settings.storage_root / "inspection-journals" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def _serialize_photo(row: InspectionJournalPhoto) -> dict[str, Any]:
    return {
        "id": row.id,
        "caption": row.caption,
        "original_name": row.original_name,
        "rotation_degrees": row.rotation_degrees,
        "crop_left": row.crop_left,
        "crop_top": row.crop_top,
        "crop_right": row.crop_right,
        "crop_bottom": row.crop_bottom,
        "image_url": f"/inspection-journals/{row.journal_id}/photos/{row.id}",
    }


def _serialize(row: InspectionJournal, *, include_content: bool = False) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "site_name": row.site_name,
        "subject": row.subject,
        "inspected_on": row.inspected_on.isoformat(),
        "time_text": row.time_text,
        "location": row.location,
        "attendees": row.attendees,
        "instructor_name": row.instructor_name,
        "instructor_affiliation": row.instructor_affiliation,
        "training_code": row.training_code,
        "training_label": row.training_label,
        "additional_content": row.additional_content,
        "special_notes": row.special_notes,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat(),
        "pdf_url": f"/inspection-journals/{row.id}/pdf",
        "photos": [_serialize_photo(photo) for photo in row.photos],
    }
    if include_content:
        payload["legal_content"] = row.legal_content
    return payload


def _crop_value(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(0.95, number))


@router.get("/training-catalog")
def training_catalog(current_user: CurrentUserDep):
    _assert_access(current_user)
    return public_catalog()


@router.get("")
def list_journals(db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    rows = (
        db.query(InspectionJournal)
        .options(joinedload(InspectionJournal.photos))
        .order_by(InspectionJournal.inspected_on.desc(), InspectionJournal.id.desc())
        .limit(100)
        .all()
    )
    return [_serialize(row) for row in rows]


@router.post("")
async def create_journal(
    db: DbDep,
    current_user: CurrentUserDep,
    site_name: Annotated[str, Form()],
    subject: Annotated[str, Form()],
    inspected_on: Annotated[date, Form()],
    training_code: Annotated[str, Form()],
    time_text: Annotated[str | None, Form()] = None,
    location: Annotated[str | None, Form()] = None,
    attendees: Annotated[str | None, Form()] = None,
    instructor_name: Annotated[str | None, Form()] = None,
    instructor_affiliation: Annotated[str | None, Form()] = None,
    additional_content: Annotated[str | None, Form()] = None,
    special_notes: Annotated[str | None, Form()] = None,
    photo_metadata: Annotated[str, Form()] = "[]",
    photos: list[UploadFile] = File(default=[]),
):
    _assert_access(current_user)
    catalog_row = TRAINING_CATALOG.get(training_code)
    if catalog_row is None:
        raise HTTPException(status_code=400, detail="지원하지 않는 교육 구분입니다.")
    if not site_name.strip() or not subject.strip():
        raise HTTPException(status_code=400, detail="현장명과 점검·교육 제목은 필수입니다.")
    try:
        metadata = json.loads(photo_metadata or "[]")
        if not isinstance(metadata, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="사진 편집정보 형식이 올바르지 않습니다.")

    row = InspectionJournal(
        site_name=site_name.strip(),
        subject=subject.strip(),
        inspected_on=inspected_on,
        time_text=(time_text or "").strip() or None,
        location=(location or "").strip() or None,
        attendees=(attendees or "").strip() or None,
        instructor_name=(instructor_name or "").strip() or None,
        instructor_affiliation=(instructor_affiliation or "").strip() or None,
        training_code=training_code,
        training_label=catalog_row["label"],
        legal_content=catalog_row["legal_content"],
        additional_content=(additional_content or "").strip() or None,
        special_notes=(special_notes or "").strip() or None,
        created_by_user_id=current_user.id,
        created_by_name=(current_user.name or current_user.login_id).strip(),
    )
    db.add(row)
    db.flush()
    photo_dir = _storage_dir("photos")
    written_paths: list[Path] = []
    try:
        for index, upload in enumerate(photos):
            media_type = (upload.content_type or "").lower()
            suffix = _ALLOWED_IMAGES.get(media_type)
            if suffix is None:
                raise HTTPException(status_code=400, detail="점검사진은 JPG, PNG, WEBP만 사용할 수 있습니다.")
            content = await upload.read()
            if not content or len(content) > _MAX_IMAGE_BYTES:
                raise HTTPException(status_code=400, detail="점검사진은 비어 있지 않은 15MB 이하 파일이어야 합니다.")
            try:
                content = resized_jpeg_bytes(content, max_long_edge=2200, quality=89)
            except (OSError, ValueError):
                raise HTTPException(status_code=400, detail="점검사진을 읽거나 리사이징할 수 없습니다.")
            path = photo_dir / f"{uuid.uuid4().hex}.jpg"
            path.write_bytes(content)
            written_paths.append(path)
            meta = metadata[index] if index < len(metadata) and isinstance(metadata[index], dict) else {}
            rotation = int(meta.get("rotation_degrees") or 0) % 360
            left, top = _crop_value(meta.get("crop_left")), _crop_value(meta.get("crop_top"))
            right, bottom = _crop_value(meta.get("crop_right")), _crop_value(meta.get("crop_bottom"))
            if left + right >= 0.99 or top + bottom >= 0.99:
                raise HTTPException(status_code=400, detail="사진 크롭 영역이 너무 작습니다.")
            db.add(
                InspectionJournalPhoto(
                    journal_id=row.id,
                    image_path=str(path.relative_to(settings.storage_root)).replace("\\", "/"),
                    original_name=Path(upload.filename or f"photo{suffix}").name[:255],
                    caption=str(meta.get("caption") or "").strip()[:500] or None,
                    rotation_degrees=rotation,
                    crop_left=left,
                    crop_top=top,
                    crop_right=right,
                    crop_bottom=bottom,
                    sort_order=index,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        for path in written_paths:
            path.unlink(missing_ok=True)
        raise
    refreshed = (
        db.query(InspectionJournal)
        .options(joinedload(InspectionJournal.photos))
        .filter(InspectionJournal.id == row.id)
        .one()
    )
    return _serialize(refreshed, include_content=True)


@router.get("/{journal_id}/photos/{photo_id}")
def journal_photo(journal_id: int, photo_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    row = (
        db.query(InspectionJournalPhoto)
        .filter(InspectionJournalPhoto.id == photo_id, InspectionJournalPhoto.journal_id == journal_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="점검사진을 찾을 수 없습니다.")
    path = settings.storage_root / row.image_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="점검사진 파일을 찾을 수 없습니다.")
    response = FileResponse(path, filename=row.original_name)
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(row.original_name)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/{journal_id}/pdf")
def journal_pdf(journal_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    row = (
        db.query(InspectionJournal)
        .options(joinedload(InspectionJournal.photos))
        .filter(InspectionJournal.id == journal_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="점검일지를 찾을 수 없습니다.")
    output = _storage_dir("exports") / f"inspection-journal-{journal_id}.pdf"
    build_inspection_journal_pdf(row, output, settings.storage_root)
    filename = f"{row.inspected_on:%Y%m%d}_{row.site_name}_{row.subject}_점검일지.pdf"
    return FileResponse(output, filename=filename, media_type="application/pdf")
