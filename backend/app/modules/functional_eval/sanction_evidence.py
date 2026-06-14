"""제재 근거(사진·코멘트) 저장 및 검증."""

from __future__ import annotations

import hashlib
import io
import uuid
from pathlib import Path

from fastapi import UploadFile
from PIL import Image

from app.config.settings import settings

EVIDENCE_COMMENT = "COMMENT"
EVIDENCE_PHOTO = "PHOTO"
DEFAULT_SANCTION_PENALTY_POINTS = 5

_ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_PHOTO_BYTES = 8 * 1024 * 1024
_EVIDENCE_PHOTO_MAX_EDGE = 480
_EVIDENCE_JPEG_QUALITY = 65


def _evidence_storage_dir(period_id: int) -> Path:
    root = settings.storage_root / "functional_eval" / "sanction_evidence" / str(period_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resize_photo_to_jpeg(content: bytes) -> bytes:
    img = Image.open(io.BytesIO(content))
    img = img.convert("RGB")
    img.thumbnail((_EVIDENCE_PHOTO_MAX_EDGE, _EVIDENCE_PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_EVIDENCE_JPEG_QUALITY, optimize=True)
    return out.getvalue()


async def save_sanction_evidence_photo(*, period_id: int, file: UploadFile) -> tuple[str, str]:
    original = (file.filename or "evidence.jpg").strip()
    suffix = Path(original).suffix.lower() or ".jpg"
    if suffix not in _ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("INVALID_SANCTION_PHOTO_TYPE")
    content = await file.read()
    if not content:
        raise ValueError("EMPTY_SANCTION_PHOTO")
    if len(content) > _MAX_PHOTO_BYTES:
        raise ValueError("SANCTION_PHOTO_TOO_LARGE")
    content = _resize_photo_to_jpeg(content)
    digest = hashlib.sha256(content).hexdigest()[:12]
    stored_name = f"sanction_{digest}_{uuid.uuid4().hex[:8]}.jpg"
    path = _evidence_storage_dir(period_id) / stored_name
    path.write_bytes(content)
    return str(path.relative_to(settings.storage_root)), original


def get_sanction_evidence_photo_path(photo_path: str) -> Path:
    return settings.storage_root / photo_path
