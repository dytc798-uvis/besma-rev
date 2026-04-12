from datetime import datetime

from pydantic import BaseModel


class CommunicationReceiverOption(BaseModel):
    id: int
    name: str
    login_id: str


class CommunicationAttachmentResponse(BaseModel):
    id: int
    original_name: str
    file_type: str
    uploaded_at: datetime
    download_url: str


class CommunicationSenderResponse(BaseModel):
    id: int
    name: str
    login_id: str


class CommunicationListItemResponse(BaseModel):
    id: int
    title: str | None
    description: str | None
    created_at: datetime
    is_read: bool
    bundle_pdf_download_url: str | None = None
    sender: CommunicationSenderResponse
    attachments: list[CommunicationAttachmentResponse]


class CommunicationUnreadCountResponse(BaseModel):
    unread_count: int

