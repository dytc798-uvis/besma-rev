from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.core.enums import Role
from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep
from app.modules.pdf_signing import service
from app.modules.pdf_signing.schemas import (
    PdfSigningPublicInfo,
    PdfSigningRequestCreateResponse,
    PdfSigningRequestListItem,
    PdfSigningSlotSummary,
    PdfSigningSubmitRequest,
    PdfSigningSubmitResponse,
)

router = APIRouter(prefix="/pdf-signing", tags=["pdf-signing"])

ADMIN_ROLES = {
    Role.ACCIDENT_ADMIN,
    Role.HQ_SAFE,
    Role.HQ_SAFE_ADMIN,
    Role.SUPER_ADMIN,
}


def _require_admin(user: CurrentUserDep) -> None:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자만 사용할 수 있습니다.")


def _public_sign_url(request: Request, *, token: str, slot: str | None = None) -> str:
    origin = request.headers.get("origin") or str(request.base_url).rstrip("/")
    if "api." in origin:
        origin = origin.replace("api.", "www.", 1)
    path = service.build_sign_url(token=token, slot=slot)
    return f"{origin}{path}"


def _to_list_item(request: Request, row) -> PdfSigningRequestListItem:
    return PdfSigningRequestListItem(
        id=row.id,
        token=row.token,
        slot=row.slot,
        sign_url=_public_sign_url(request, token=row.token, slot=row.slot),
        purpose_label=row.purpose_label,
        signer_name=row.signer_name,
        signer_title=row.signer_title,
        original_filename=row.original_filename,
        status=row.status,
        expires_at=row.expires_at,
        signed_at=row.signed_at,
        signer_ip=row.signer_ip,
        original_sha256=row.original_sha256,
        signed_sha256=row.signed_sha256,
        created_at=row.created_at,
    )


def _public_info_from_row(row) -> PdfSigningPublicInfo:
    return PdfSigningPublicInfo(
        signer_name=row.signer_name,
        signer_title=row.signer_title,
        purpose_label=row.purpose_label,
        original_filename=row.original_filename,
        status=row.status,
        expires_at=row.expires_at,
    )


def _refresh_expired(row, db: DbDep) -> None:
    if row.status == "pending" and row.expires_at < service._utcnow():
        row.status = "expired"
        db.commit()


@router.get("/slots", response_model=list[PdfSigningSlotSummary])
def list_temp_sign_slots(request: Request, db: DbDep, current_user: CurrentUserDep):
    _require_admin(current_user)
    slot_rows = service.list_slot_requests(db)
    summaries: list[PdfSigningSlotSummary] = []
    for slot, row in slot_rows.items():
        summaries.append(
            PdfSigningSlotSummary(
                slot=slot,
                slot_label=service.TEMP_SIGN_SLOT_LABELS.get(slot, slot),
                sign_url=_public_sign_url(request, token=row.token if row else "", slot=slot),
                request=_to_list_item(request, row) if row else None,
            )
        )
    return summaries


@router.post("/slots/{slot}", response_model=PdfSigningRequestCreateResponse)
async def create_slot_signing_request(
    slot: str,
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
    signer_name: str = Form(...),
    signer_title: str = Form(...),
    purpose_label: str | None = Form(None),
    expires_hours: int = Form(168),
):
    _require_admin(current_user)
    try:
        normalized_slot = service.normalize_slot(slot)
    except ValueError:
        raise HTTPException(status_code=400, detail="slot은 sign1 또는 sign2 여야 합니다.")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    row = service.create_request(
        db,
        created_by_user_id=current_user.id,
        signer_name=signer_name,
        signer_title=signer_title,
        purpose_label=purpose_label or service.TEMP_SIGN_SLOT_LABELS.get(normalized_slot),
        original_filename=file.filename,
        original_bytes=content,
        expires_hours=expires_hours,
        slot=normalized_slot,
    )
    return PdfSigningRequestCreateResponse(
        id=row.id,
        token=row.token,
        slot=row.slot,
        sign_url=_public_sign_url(request, token=row.token, slot=row.slot),
        purpose_label=row.purpose_label,
        signer_name=row.signer_name,
        signer_title=row.signer_title,
        original_filename=row.original_filename,
        status=row.status,
        expires_at=row.expires_at,
    )


@router.post("/requests", response_model=PdfSigningRequestCreateResponse)
async def create_signing_request(
    request: Request,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
    signer_name: str = Form(...),
    signer_title: str = Form(...),
    purpose_label: str | None = Form(None),
    expires_hours: int = Form(168),
    slot: str | None = Form(None),
):
    _require_admin(current_user)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드할 수 있습니다.")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")

    try:
        row = service.create_request(
            db,
            created_by_user_id=current_user.id,
            signer_name=signer_name,
            signer_title=signer_title,
            purpose_label=purpose_label,
            original_filename=file.filename,
            original_bytes=content,
            expires_hours=expires_hours,
            slot=slot,
        )
    except ValueError as exc:
        if str(exc) == "invalid_slot":
            raise HTTPException(status_code=400, detail="slot은 sign1 또는 sign2 여야 합니다.")
        raise

    return PdfSigningRequestCreateResponse(
        id=row.id,
        token=row.token,
        slot=row.slot,
        sign_url=_public_sign_url(request, token=row.token, slot=row.slot),
        purpose_label=row.purpose_label,
        signer_name=row.signer_name,
        signer_title=row.signer_title,
        original_filename=row.original_filename,
        status=row.status,
        expires_at=row.expires_at,
    )


@router.get("/requests", response_model=list[PdfSigningRequestListItem])
def list_signing_requests(request: Request, db: DbDep, current_user: CurrentUserDep):
    _require_admin(current_user)
    rows = service.list_requests(db)
    return [_to_list_item(request, row) for row in rows]


@router.get("/requests/{request_id}/download")
def download_signing_pdf(
    request_id: int,
    kind: str,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _require_admin(current_user)
    row = service.get_request(db, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="요청을 찾을 수 없습니다.")
    if kind == "signed":
        if not row.signed_path:
            raise HTTPException(status_code=404, detail="서명 완료 PDF가 없습니다.")
        path = row.signed_path
        filename = f"signed_{row.original_filename}"
    elif kind == "original":
        path = row.original_path
        filename = row.original_filename
    else:
        raise HTTPException(status_code=400, detail="kind는 original 또는 signed 여야 합니다.")

    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/public/slot/{slot}", response_model=PdfSigningPublicInfo)
def get_public_signing_info_by_slot(slot: str, db: DbDep):
    try:
        normalized = service.normalize_slot(slot)
    except ValueError:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다.")
    row = service.get_by_slot(db, normalized)
    if row is None:
        raise HTTPException(status_code=404, detail="아직 등록된 PDF가 없습니다.")
    _refresh_expired(row, db)
    return _public_info_from_row(row)


@router.get("/public/slot/{slot}/document")
def get_public_document_by_slot(slot: str, db: DbDep):
    try:
        service.normalize_slot(slot)
    except ValueError:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다.")
    return _public_document_response(db, slot=slot)


@router.get("/public/{token}/document")
def get_public_document_by_token(token: str, db: DbDep):
    return _public_document_response(db, token=token)


@router.post("/public/slot/{slot}/sign", response_model=PdfSigningSubmitResponse)
def submit_public_signature_by_slot(
    slot: str,
    payload: PdfSigningSubmitRequest,
    request: Request,
    db: DbDep,
):
    try:
        service.normalize_slot(slot)
    except ValueError:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다.")
    return _submit_signature(
        db=db,
        request=request,
        payload=payload,
        slot=slot,
    )


@router.get("/public/{token}", response_model=PdfSigningPublicInfo)
def get_public_signing_info(token: str, db: DbDep):
    row = service.get_by_token(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다.")
    _refresh_expired(row, db)
    return _public_info_from_row(row)


@router.post("/public/{token}/sign", response_model=PdfSigningSubmitResponse)
def submit_public_signature(
    token: str,
    payload: PdfSigningSubmitRequest,
    request: Request,
    db: DbDep,
):
    return _submit_signature(db=db, request=request, payload=payload, token=token)


def _public_document_response(db: DbDep, *, token: str | None = None, slot: str | None = None):
    try:
        row = service.get_public_pending_document(db, token=token, slot=slot)
    except ValueError as exc:
        code = str(exc)
        if code == "token_not_found":
            raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다.")
        if code == "document_not_available":
            raise HTTPException(status_code=409, detail="확인할 수 있는 문서가 없습니다.")
        raise
    return FileResponse(
        path=row.original_path,
        media_type="application/pdf",
        filename=row.original_filename,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(row.original_filename)}",
        },
    )


def _submit_signature(
    *,
    db: DbDep,
    request: Request,
    payload: PdfSigningSubmitRequest,
    token: str | None = None,
    slot: str | None = None,
) -> PdfSigningSubmitResponse:
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    try:
        row = service.submit_signature(
            db,
            token=token,
            slot=slot,
            signature_png_base64=payload.signature_png_base64,
            signer_ip=client_ip,
            signer_user_agent=user_agent,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "token_not_found":
            raise HTTPException(status_code=404, detail="유효하지 않은 링크입니다.")
        if code == "token_already_used":
            raise HTTPException(status_code=409, detail="이미 서명이 완료된 링크입니다.")
        if code == "token_expired":
            raise HTTPException(status_code=410, detail="만료된 링크입니다.")
        if code in {"invalid_signature_image", "empty_pdf", "page_not_found"}:
            raise HTTPException(status_code=400, detail="서명 이미지 또는 PDF 처리에 실패했습니다.")
        raise
    return PdfSigningSubmitResponse(
        status=row.status,
        signed_at=row.signed_at,
        signed_sha256=row.signed_sha256 or "",
    )
