"""고객사 포상 — 현장 사진 제출 · 본사 승인 · 가점."""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.datetime_utils import format_kst_datetime_short, utc_now
from app.core.enums import Role
from app.modules.functional_eval.models import FunctionalEvalCustomerReward, FunctionalEvalPeriod, FunctionalEvalWorker
from app.modules.users.models import User

CUSTOMER_REWARD_NOTE = "고객사포상"
DEFAULT_CUSTOMER_REWARD_POINTS = 5
REWARD_STATUS_PENDING = "PENDING"
REWARD_STATUS_APPROVED = "APPROVED"
REWARD_STATUS_REJECTED = "REJECTED"

_ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_PHOTO_BYTES = 8 * 1024 * 1024
_REWARD_PHOTO_MAX_EDGE = 480
_REWARD_JPEG_QUALITY = 65


def _resize_photo_to_jpeg(content: bytes) -> bytes:
    img = Image.open(io.BytesIO(content))
    img = img.convert("RGB")
    img.thumbnail((_REWARD_PHOTO_MAX_EDGE, _REWARD_PHOTO_MAX_EDGE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_REWARD_JPEG_QUALITY, optimize=True)
    return out.getvalue()


def _reward_storage_dir(period_id: int) -> Path:
    root = settings.storage_root / "functional_eval" / "customer_rewards" / str(period_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _serialize_reward(row: FunctionalEvalCustomerReward, worker_name: str) -> dict[str, Any]:
    return {
        "id": row.id,
        "period_id": row.period_id,
        "worker_id": row.worker_id,
        "worker_name": worker_name,
        "site_code": row.site_code,
        "status": row.status,
        "bonus_points": row.bonus_points,
        "original_filename": row.original_filename,
        "photo_url": f"/functional-eval/customer-rewards/{row.id}/photo",
        "submitted_by_user_id": row.submitted_by_user_id,
        "reviewed_by_user_id": row.reviewed_by_user_id,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewed_at_label": format_kst_datetime_short(row.reviewed_at),
        "reject_note": row.reject_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_at_label": format_kst_datetime_short(row.created_at),
    }


async def save_reward_photo(*, period_id: int, file: UploadFile) -> tuple[str, str]:
    original = (file.filename or "photo.jpg").strip()
    suffix = Path(original).suffix.lower() or ".jpg"
    if suffix not in _ALLOWED_IMAGE_SUFFIXES:
        raise ValueError("INVALID_REWARD_PHOTO_TYPE")
    content = await file.read()
    if not content:
        raise ValueError("EMPTY_REWARD_PHOTO")
    if len(content) > _MAX_PHOTO_BYTES:
        raise ValueError("REWARD_PHOTO_TOO_LARGE")
    content = _resize_photo_to_jpeg(content)
    digest = hashlib.sha256(content).hexdigest()[:12]
    stored_name = f"reward_{digest}_{uuid.uuid4().hex[:8]}.jpg"
    path = _reward_storage_dir(period_id) / stored_name
    path.write_bytes(content)
    return str(path.relative_to(settings.storage_root)), original


def submit_customer_reward(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    user: User,
    worker_id: int,
    photo_path: str,
    original_filename: str,
    bonus_points: int = DEFAULT_CUSTOMER_REWARD_POINTS,
) -> dict[str, Any]:
    from app.modules.functional_eval import service as fe_service

    if user.role != Role.SITE_FUNCTIONAL_EVAL:
        raise ValueError("SITE_ONLY")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None or worker.period_id != period.id:
        raise ValueError("WORKER_NOT_FOUND")
    fe_service._assert_worker_evidence_access(db, user, worker)

    existing = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.period_id == period.id,
            FunctionalEvalCustomerReward.worker_id == worker.id,
        )
        .first()
    )
    if existing is not None:
        raise ValueError("REWARD_ALREADY_SUBMITTED")

    pending = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.period_id == period.id,
            FunctionalEvalCustomerReward.worker_id == worker.id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_PENDING,
        )
        .first()
    )
    if pending is not None:
        raise ValueError("REWARD_ALREADY_PENDING")

    row = FunctionalEvalCustomerReward(
        period_id=period.id,
        worker_id=worker.id,
        site_code=worker.site_code,
        photo_path=photo_path,
        original_filename=original_filename,
        status=REWARD_STATUS_PENDING,
        bonus_points=max(1, min(int(bonus_points or DEFAULT_CUSTOMER_REWARD_POINTS), 100)),
        submitted_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_reward(row, worker.name)


def list_pending_customer_rewards(db: Session, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalCustomerReward, FunctionalEvalWorker)
        .join(FunctionalEvalWorker, FunctionalEvalWorker.id == FunctionalEvalCustomerReward.worker_id)
        .filter(
            FunctionalEvalCustomerReward.period_id == period.id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_PENDING,
        )
        .order_by(FunctionalEvalCustomerReward.created_at.asc(), FunctionalEvalCustomerReward.id.asc())
        .all()
    )
    return [_serialize_reward(reward, worker.name) for reward, worker in rows]


def list_worker_customer_rewards(db: Session, worker_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(FunctionalEvalCustomerReward, FunctionalEvalWorker)
        .join(FunctionalEvalWorker, FunctionalEvalWorker.id == FunctionalEvalCustomerReward.worker_id)
        .filter(FunctionalEvalCustomerReward.worker_id == worker_id)
        .order_by(FunctionalEvalCustomerReward.created_at.desc())
        .all()
    )
    return [_serialize_reward(reward, worker.name) for reward, worker in rows]


def get_reward_photo_path(db: Session, reward_id: int) -> Path:
    row = db.query(FunctionalEvalCustomerReward).filter(FunctionalEvalCustomerReward.id == reward_id).first()
    if row is None:
        raise ValueError("REWARD_NOT_FOUND")
    return settings.storage_root / row.photo_path


def approve_customer_reward(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    user: User,
    reward_id: int,
    bonus_points: int | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service as fe_service

    row = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.id == reward_id,
            FunctionalEvalCustomerReward.period_id == period.id,
        )
        .first()
    )
    if row is None:
        raise ValueError("REWARD_NOT_FOUND")
    if row.status != REWARD_STATUS_PENDING:
        raise ValueError("REWARD_NOT_PENDING")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")

    points = max(1, min(int(bonus_points or row.bonus_points or DEFAULT_CUSTOMER_REWARD_POINTS), 100))
    row.status = REWARD_STATUS_APPROVED
    row.bonus_points = points
    row.reviewed_by_user_id = user.id
    row.reviewed_at = utc_now()
    db.commit()
    db.refresh(row)
    return _serialize_reward(row, worker.name)


def reject_customer_reward(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    reward_id: int,
    user: User,
    reject_note: str | None = None,
) -> dict[str, Any]:
    from app.modules.functional_eval import service as fe_service

    row = (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.id == reward_id,
            FunctionalEvalCustomerReward.period_id == period.id,
        )
        .first()
    )
    if row is None:
        raise ValueError("REWARD_NOT_FOUND")
    if row.status != REWARD_STATUS_PENDING:
        raise ValueError("REWARD_NOT_PENDING")
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == row.worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")

    row.status = REWARD_STATUS_REJECTED
    row.reviewed_by_user_id = user.id
    row.reviewed_at = utc_now()
    row.reject_note = (reject_note or "").strip() or None
    db.commit()
    db.refresh(row)
    return _serialize_reward(row, worker.name)


def worker_has_approved_customer_reward(db: Session, worker_id: int) -> bool:
    return (
        db.query(FunctionalEvalCustomerReward)
        .filter(
            FunctionalEvalCustomerReward.worker_id == worker_id,
            FunctionalEvalCustomerReward.status == REWARD_STATUS_APPROVED,
        )
        .count()
        > 0
    )
