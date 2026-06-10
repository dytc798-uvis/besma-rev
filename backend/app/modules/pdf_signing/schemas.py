from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PdfSigningSlotSummary(BaseModel):
    slot: str
    slot_label: str
    sign_url: str
    request: "PdfSigningRequestListItem | None"


class PdfSigningRequestCreateResponse(BaseModel):
    id: int
    token: str
    slot: str | None
    sign_url: str
    purpose_label: str | None
    signer_name: str
    signer_title: str
    original_filename: str
    status: str
    expires_at: datetime


class PdfSigningRequestListItem(BaseModel):
    id: int
    token: str
    slot: str | None
    sign_url: str
    purpose_label: str | None
    signer_name: str
    signer_title: str
    original_filename: str
    status: str
    expires_at: datetime
    signed_at: datetime | None
    signer_ip: str | None
    original_sha256: str
    signed_sha256: str | None
    created_at: datetime


class PdfSigningPublicInfo(BaseModel):
    signer_name: str
    signer_title: str
    purpose_label: str | None
    original_filename: str
    status: str
    expires_at: datetime


class PdfSigningSubmitRequest(BaseModel):
    signature_png_base64: str = Field(..., min_length=32)


class PdfSigningSubmitResponse(BaseModel):
    status: str
    signed_at: datetime
    signed_sha256: str
