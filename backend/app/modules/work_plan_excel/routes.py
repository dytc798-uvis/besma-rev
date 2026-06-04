from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.core.permissions import CurrentUserDep
from app.modules.work_plan_excel import equipment_lookup, service
from app.schemas.work_plan_forklift import (
    ForkliftEquipmentSpecResponse,
    ForkliftWorkPlanGenerateResponse,
    ForkliftWorkPlanInput,
)

router = APIRouter(prefix="/work-plans/forklift", tags=["work-plans"])


@router.get("/lookup-specs", response_model=ForkliftEquipmentSpecResponse)
def lookup_forklift_specs(
    current_user: CurrentUserDep,
    model: str = Query(..., min_length=2, description="지게차 모델명"),
    allow_web: bool = Query(default=True, description="내장 카탈로그 미매칭 시 웹 검색 시도"),
):
    _ = current_user
    spec = equipment_lookup.lookup_forklift_equipment_specs(model, allow_web=allow_web)
    return ForkliftEquipmentSpecResponse.model_validate(spec.model_dump())


@router.post("/generate", response_model=ForkliftWorkPlanGenerateResponse)
def generate_forklift_work_plan(
    payload: ForkliftWorkPlanInput,
    current_user: CurrentUserDep,
):
    _ = current_user
    try:
        out_path, filename = service.generate_forklift_work_plan(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return ForkliftWorkPlanGenerateResponse(
        filename=filename,
        saved_path=str(out_path),
        download_url=f"/work-plans/forklift/download/{quote(filename)}",
        sheet_name=service.SHEET_NAME,
    )


@router.get("/download/{filename}")
def download_forklift_work_plan(
    filename: str,
    current_user: CurrentUserDep,
):
    _ = current_user
    try:
        file_path = service.resolve_saved_work_plan(filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_filename") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file_not_found") from exc

    encoded = quote(file_path.name)
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=file_path.name,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
