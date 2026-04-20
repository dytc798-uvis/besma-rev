# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.enums import Role
from app.modules.accidents import service
from app.modules.accidents.nas_path_utils import build_explorer_bat_bytes, to_displayed_accident_nas_path
from app.schemas.accidents import (
    AccidentDetail,
    AccidentMasterExcelSyncResult,
    AccidentImportResult,
    AccidentInitialReportOutput,
    AccidentListItem,
    AccidentLookups,
    AccidentParseCreateRequest,
    AccidentParsePreviewResponse,
    AccidentUpdateRequest,
    AccidentWorklistResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/accidents", tags=["accidents"])

ACCIDENT_ALLOWED_ROLES = {
    Role.ACCIDENT_ADMIN,
    Role.HQ_SAFE,
    Role.HQ_SAFE_ADMIN,
    Role.SUPER_ADMIN,
}


def _require_accident_access(user) -> None:
    if user is None or getattr(user, "role", None) not in ACCIDENT_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="사고관리 기능은 본사 안전 및 사고관리 권한에서만 사용할 수 있습니다.",
        )


@router.post(
    "/initial-report/parse-preview",
    response_model=AccidentParsePreviewResponse,
)
def parse_accident_preview(
    body: AccidentParseCreateRequest,
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    return service.preview_parse(body.message_raw or "")


@router.post(
    "/initial-report/parse-and-create",
    response_model=AccidentDetail,
    status_code=status.HTTP_201_CREATED,
)
def parse_and_create_accident(
    body: AccidentParseCreateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    row = service.create_from_request(
        db,
        body=body,
        created_by_user_id=getattr(user, "id", None),
    )
    return row


@router.get("/lookups", response_model=AccidentLookups)
def get_accident_lookups(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    return service.lookups(db)


@router.get("", response_model=list[AccidentListItem])
def list_accidents(
    queues: list[str] = Query(default=[]),
    statuses: list[str] = Query(default=[]),
    management_categories: list[str] = Query(default=[]),
    only_incomplete: bool = Query(default=False),
    show_all: bool = Query(default=False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    return service.list_accidents(
        db,
        queue_keys=queues or None,
        statuses=statuses or None,
        management_categories=management_categories or None,
        only_incomplete=only_incomplete,
        default_queue_only=not show_all,
    )


@router.get("/worklist", response_model=AccidentWorklistResponse)
def get_accident_worklist(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    return service.get_worklist(db)


@router.get("/{accident_id}/initial-report", response_model=AccidentInitialReportOutput)
def get_initial_report_output(
    accident_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    row = service.get_accident_or_404(db, accident_id)
    view = service.initial_report_view(row)
    return AccidentInitialReportOutput(
        accident_id=row.id,
        accident_code=row.accident_id,
        display_code=row.display_code,
        parse_status=row.parse_status,
        composed_line=view["composed_line"],
        fields=view["fields"],
        message_raw=view["message_raw"],
    )


@router.get("/{accident_id}/nas-folder-launcher")
def download_nas_folder_launcher(
    accident_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    """NAS 표시 경로로 탐색기를 여는 Windows 배치 파일을 내려받는다(클라이언트 PC에서 실행)."""
    _require_accident_access(user)
    row = service.get_accident_or_404(db, accident_id)
    service.ensure_accident_folder_persisted(db, row)
    display = to_displayed_accident_nas_path(row.nas_folder_path, row.accident_id)
    if not display or not str(display).strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="NAS 경로가 없습니다.")
    try:
        bat = build_explorer_bat_bytes(display)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="NAS 경로가 없습니다.") from None
    safe_name = f"open_accident_{(row.accident_id or str(row.id)).replace(' ', '_')}_nas.bat"
    logger.info(
        "NAS folder launcher downloaded accident_pk=%s accident_id=%s user=%s",
        row.id,
        row.accident_id,
        getattr(user, "login_id", None),
    )
    return Response(
        content=bat,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/{accident_id}", response_model=AccidentDetail)
def get_accident(
    accident_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    return service.get_accident_or_404(db, accident_id)


@router.put("/{accident_id}", response_model=AccidentDetail)
def update_accident(
    accident_id: int,
    body: AccidentUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    return service.update_accident(
        db,
        accident_id=accident_id,
        actor_user_id=getattr(user, "id", None),
        site_standard_name=body.site_standard_name,
        reporter_name=body.reporter_name,
        status=body.status,
        management_category=body.management_category,
        accident_datetime_text=body.accident_datetime_text,
        accident_datetime=body.accident_datetime,
        accident_place=body.accident_place,
        work_content=body.work_content,
        injured_person_name=body.injured_person_name,
        accident_circumstance=body.accident_circumstance,
        accident_reason=body.accident_reason,
        injured_part=body.injured_part,
        diagnosis_name=body.diagnosis_name,
        action_taken=body.action_taken,
        notes=body.notes,
        initial_report_template=body.initial_report_template,
    )


@router.delete("/{accident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_accident(
    accident_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    service.delete_accident(db, accident_id=accident_id)


@router.post("/{accident_id}/attachments", response_model=AccidentDetail)
async def upload_accident_attachment(
    accident_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    await service.save_attachment(db, accident_id=accident_id, upload=file)
    return service.get_accident_or_404(db, accident_id)


@router.get("/attachments/{attachment_id}")
def download_accident_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    row = service.get_attachment_or_404(db, attachment_id)
    path = service.attachment_absolute_path(row)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="첨부 파일이 존재하지 않습니다.")
    return FileResponse(path, filename=row.file_name)


@router.get("/export/master")
def export_master(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    content = service.export_master_workbook(db)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote('BESMA_사고MASTER_export.xlsx')}"}
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/import/master", response_model=AccidentImportResult)
def import_master(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    result = service.import_master_rows(db)
    return AccidentImportResult(**result)


@router.post("/export-to-master-excel", response_model=AccidentMasterExcelSyncResult)
def export_to_master_excel(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_with_bypass),
):
    _require_accident_access(user)
    result = service.export_verified_accidents_to_master_excel(db)
    return AccidentMasterExcelSyncResult(**result)
