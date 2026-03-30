from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.communications.models import (
    Communication,
    CommunicationAttachment,
    CommunicationReceiver,
)
from app.modules.users.models import User
from app.schemas.communications import (
    CommunicationAttachmentResponse,
    CommunicationListItemResponse,
    CommunicationReceiverOption,
    CommunicationSenderResponse,
    CommunicationUnreadCountResponse,
)

router = APIRouter(prefix="/communications", tags=["communications"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
}


def _ensure_communications_dir() -> Path:
    d = settings.storage_root / "communications"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _assert_site_user(current_user: CurrentUserDep) -> None:
    if current_user.role != Role.SITE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SITE only feature")
    if not current_user.site_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SITE user must have site_id")


@router.get("/receivers", response_model=list[CommunicationReceiverOption])
def list_receivers(db: DbDep, current_user: CurrentUserDep):
    _assert_site_user(current_user)
    users = (
        db.query(User)
        .filter(
            User.site_id == current_user.site_id,
            User.role == Role.SITE.value,
            User.is_active.is_(True),
            User.id != current_user.id,
        )
        .order_by(User.name.asc())
        .all()
    )
    return [
        CommunicationReceiverOption(id=u.id, name=u.name, login_id=u.login_id)
        for u in users
    ]


@router.post("")
async def create_communication(
    db: DbDep,
    current_user: CurrentUserDep,
    receiver_user_ids: Annotated[list[int], Form(...)],
    files: list[UploadFile] = File(...),
    title: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
):
    _assert_site_user(current_user)
    receiver_ids = sorted({int(v) for v in receiver_user_ids if v})
    if not receiver_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receiver_user_ids is required")
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one image is required")

    users = (
        db.query(User)
        .filter(User.id.in_(receiver_ids), User.site_id == current_user.site_id, User.role == Role.SITE.value)
        .all()
    )
    if len(users) != len(receiver_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All receivers must be SITE users in the same site",
        )

    communication = Communication(
        site_id=current_user.site_id,
        sender_user_id=current_user.id,
        title=(title or "").strip() or None,
        description=(description or "").strip() or None,
    )
    db.add(communication)
    db.flush()

    storage_dir = _ensure_communications_dir()
    for index, upload in enumerate(files, start=1):
        content_type = (upload.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only image uploads are allowed")
        original_name = upload.filename or "image"
        ext = Path(original_name).suffix or ".bin"
        stored_name = f"comm_{communication.id}_{int(utc_now().timestamp())}_{index}{ext}"
        target_path = storage_dir / stored_name
        target_path.write_bytes(await upload.read())
        db.add(
            CommunicationAttachment(
                communication_id=communication.id,
                file_path=str(target_path.relative_to(settings.storage_root)),
                original_name=original_name,
                file_type="image",
            )
        )

    for receiver_id in receiver_ids:
        db.add(
            CommunicationReceiver(
                communication_id=communication.id,
                receiver_user_id=receiver_id,
            )
        )

    db.commit()
    return {"id": communication.id}


@router.get("", response_model=list[CommunicationListItemResponse])
def list_received_communications(db: DbDep, current_user: CurrentUserDep, limit: int = 30):
    _assert_site_user(current_user)
    rows = (
        db.query(CommunicationReceiver, Communication, User)
        .join(Communication, Communication.id == CommunicationReceiver.communication_id)
        .join(User, User.id == Communication.sender_user_id)
        .filter(
            CommunicationReceiver.receiver_user_id == current_user.id,
            Communication.site_id == current_user.site_id,
            Communication.is_deleted.is_(False),
        )
        .order_by(Communication.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    result: list[CommunicationListItemResponse] = []
    for receiver, communication, sender in rows:
        attachments = (
            db.query(CommunicationAttachment)
            .filter(CommunicationAttachment.communication_id == communication.id)
            .order_by(CommunicationAttachment.id.asc())
            .all()
        )
        result.append(
            CommunicationListItemResponse(
                id=communication.id,
                title=communication.title,
                description=communication.description,
                created_at=communication.created_at,
                is_read=receiver.is_read,
                sender=CommunicationSenderResponse(
                    id=sender.id, name=sender.name, login_id=sender.login_id
                ),
                attachments=[
                    CommunicationAttachmentResponse(
                        id=a.id,
                        original_name=a.original_name,
                        file_type=a.file_type,
                        uploaded_at=a.uploaded_at,
                        download_url=f"/communications/attachments/{a.id}/download",
                    )
                    for a in attachments
                ],
            )
        )
    return result


@router.get("/unread-count", response_model=CommunicationUnreadCountResponse)
def get_unread_count(db: DbDep, current_user: CurrentUserDep):
    _assert_site_user(current_user)
    unread_count = (
        db.query(CommunicationReceiver)
        .join(Communication, Communication.id == CommunicationReceiver.communication_id)
        .filter(
            CommunicationReceiver.receiver_user_id == current_user.id,
            CommunicationReceiver.is_read.is_(False),
            Communication.site_id == current_user.site_id,
            Communication.is_deleted.is_(False),
        )
        .count()
    )
    return CommunicationUnreadCountResponse(unread_count=unread_count)


@router.post("/{communication_id}/read")
def mark_communication_read(communication_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_site_user(current_user)
    receiver = (
        db.query(CommunicationReceiver)
        .join(Communication, Communication.id == CommunicationReceiver.communication_id)
        .filter(
            CommunicationReceiver.communication_id == communication_id,
            CommunicationReceiver.receiver_user_id == current_user.id,
            Communication.site_id == current_user.site_id,
            Communication.is_deleted.is_(False),
        )
        .first()
    )
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Communication not found")
    if not receiver.is_read:
        receiver.is_read = True
        receiver.read_at = utc_now()
        db.commit()
    return {"ok": True}


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_site_user(current_user)
    row = (
        db.query(CommunicationAttachment, Communication)
        .join(Communication, Communication.id == CommunicationAttachment.communication_id)
        .join(CommunicationReceiver, CommunicationReceiver.communication_id == Communication.id)
        .filter(
            CommunicationAttachment.id == attachment_id,
            CommunicationReceiver.receiver_user_id == current_user.id,
            Communication.site_id == current_user.site_id,
            Communication.is_deleted.is_(False),
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    attachment, _ = row
    file_path = settings.storage_root / attachment.file_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(path=file_path, media_type=media_type, filename=attachment.original_name)
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(attachment.original_name)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

