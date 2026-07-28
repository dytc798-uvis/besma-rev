from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, time
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy.orm import joinedload

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.datetime_utils import utc_now
from app.core.permissions import CurrentUserDep, assert_hq_safe_workspace
from app.modules.safety_ledgers.image_extraction import extract_image
from app.modules.safety_ledgers.models import (
    SafetyCardExpense,
    SafetyVehicle,
    SafetyVehicleDriver,
    SafetyVehicleLog,
)
from app.modules.safety_ledgers.schemas import CardExpenseReview, VehicleDriversUpdate, VehicleLogReview
from app.modules.safety_ledgers.workbook_export import (
    CARD_FILENAME,
    VEHICLE_FILENAME,
    build_card_workbook,
    build_vehicle_workbook,
    copy_exports_to_nas,
)


router = APIRouter(prefix="/safety-ledgers", tags=["safety-ledgers"])
_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
_MAX_IMAGE_BYTES = 15 * 1024 * 1024
_CONFIRM_THRESHOLD = 90


def _assert_access(user) -> None:
    assert_hq_safe_workspace(user)


def _storage_dir(kind: str) -> Path:
    target = settings.storage_root / "safety-ledgers" / kind
    target.mkdir(parents=True, exist_ok=True)
    return target


def _relative_path(path: Path) -> str:
    return str(path.relative_to(settings.storage_root)).replace("\\", "/")


async def _save_image(file: UploadFile, kind: str) -> tuple[Path, str, str]:
    media_type = (file.content_type or "").lower()
    suffix = _ALLOWED_IMAGE_TYPES.get(media_type)
    if not suffix:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JPG, PNG, WEBP 또는 HEIC 사진만 업로드할 수 있습니다.",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="빈 사진은 업로드할 수 없습니다.")
    if len(content) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="사진은 15MB 이하만 업로드할 수 있습니다.")
    path = _storage_dir(kind) / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(content)
    return path, Path(file.filename or f"capture{suffix}").name[:255], media_type


def _ensure_pilot_vehicle(db) -> SafetyVehicle:
    vehicle = db.query(SafetyVehicle).filter(SafetyVehicle.plate_number == "181하8339").first()
    if vehicle is None:
        vehicle = SafetyVehicle(vehicle_name="투싼", plate_number="181하8339", department="안전보건실")
        db.add(vehicle)
        db.flush()
    existing = {row.driver_name for row in vehicle.drivers}
    for order, driver_name in enumerate(("정상익", "박영선"), 1):
        if driver_name not in existing:
            db.add(SafetyVehicleDriver(vehicle_id=vehicle.id, driver_name=driver_name, sort_order=order))
    db.commit()
    return (
        db.query(SafetyVehicle)
        .options(joinedload(SafetyVehicle.drivers))
        .filter(SafetyVehicle.id == vehicle.id)
        .one()
    )


def _parse_iso_datetime(date_value: Any, time_value: Any) -> datetime | None:
    if not date_value:
        return None
    try:
        parsed_date = date.fromisoformat(str(date_value))
        parsed_time = time.fromisoformat(str(time_value or "00:00"))
        return datetime.combine(parsed_date, parsed_time)
    except ValueError:
        return None


def _card_last4(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-4:] if len(digits) >= 4 else None


def _serialize_vehicle_log(row: SafetyVehicleLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "vehicle_id": row.vehicle_id,
        "vehicle_name": row.vehicle.vehicle_name if row.vehicle else "",
        "plate_number": row.vehicle.plate_number if row.vehicle else "",
        "driven_on": row.driven_on.isoformat(),
        "driver_name": row.driver_name,
        "use_type": row.use_type,
        "odometer_km": row.odometer_km,
        "trip_km": row.trip_km,
        "purpose": row.purpose,
        "extraction_status": row.extraction_status,
        "extraction_confidence": row.extraction_confidence,
        "image_url": f"/safety-ledgers/vehicle-logs/{row.id}/image",
        "created_at": row.created_at.isoformat(),
    }


def _serialize_card(row: SafetyCardExpense) -> dict[str, Any]:
    return {
        "id": row.id,
        "used_at": row.used_at.isoformat() if row.used_at else None,
        "site_name": row.site_name,
        "merchant": row.merchant,
        "amount": row.amount,
        "description": row.description,
        "card_last4": row.card_last4,
        "note": row.note,
        "extraction_status": row.extraction_status,
        "extraction_confidence": row.extraction_confidence,
        "image_url": f"/safety-ledgers/card-expenses/{row.id}/image",
        "created_at": row.created_at.isoformat(),
    }


def _export_paths(db) -> tuple[Path, Path]:
    vehicle = _ensure_pilot_vehicle(db)
    export_dir = _storage_dir("exports")
    vehicle_logs = (
        db.query(SafetyVehicleLog)
        .filter(SafetyVehicleLog.vehicle_id == vehicle.id)
        .order_by(SafetyVehicleLog.driven_on.asc(), SafetyVehicleLog.id.asc())
        .all()
    )
    expenses = db.query(SafetyCardExpense).order_by(SafetyCardExpense.used_at.asc(), SafetyCardExpense.id.asc()).all()
    card_path = build_card_workbook(
        expenses,
        export_dir / CARD_FILENAME,
        template_path=settings.safety_ledger_card_template_path,
    )
    vehicle_path = build_vehicle_workbook(vehicle, vehicle_logs, export_dir / VEHICLE_FILENAME)
    copy_exports_to_nas((card_path, vehicle_path), settings.safety_ledger_nas_root)
    return card_path, vehicle_path


@router.get("/bootstrap")
def bootstrap(db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    vehicle = _ensure_pilot_vehicle(db)
    logs = (
        db.query(SafetyVehicleLog)
        .options(joinedload(SafetyVehicleLog.vehicle))
        .filter(SafetyVehicleLog.vehicle_id == vehicle.id)
        .order_by(SafetyVehicleLog.driven_on.desc(), SafetyVehicleLog.id.desc())
        .all()
    )
    expenses = db.query(SafetyCardExpense).order_by(SafetyCardExpense.created_at.desc()).all()
    return {
        "vehicle": {
            "id": vehicle.id,
            "vehicle_name": vehicle.vehicle_name,
            "plate_number": vehicle.plate_number,
            "department": vehicle.department,
            "drivers": [row.driver_name for row in vehicle.drivers if row.is_active],
            "max_drivers": 4,
        },
        "vehicle_logs": [_serialize_vehicle_log(row) for row in logs],
        "card_expenses": [_serialize_card(row) for row in expenses],
        "vision_enabled": bool((settings.openai_api_key or "").strip()),
        "vision_model": settings.safety_ledger_vision_model,
        "review_threshold": _CONFIRM_THRESHOLD,
    }


@router.post("/vehicle-logs")
async def create_vehicle_log(
    db: DbDep,
    current_user: CurrentUserDep,
    photo: Annotated[UploadFile, File(...)],
    driven_on: Annotated[date, Form(...)],
    driver_name: Annotated[str, Form(...)],
    purpose: Annotated[str | None, Form()] = None,
    odometer_km: Annotated[int | None, Form()] = None,
    trip_km: Annotated[float | None, Form()] = None,
):
    _assert_access(current_user)
    vehicle = _ensure_pilot_vehicle(db)
    allowed_drivers = {row.driver_name for row in vehicle.drivers if row.is_active}
    clean_driver = driver_name.strip()
    if clean_driver not in allowed_drivers:
        raise HTTPException(status_code=400, detail="이 차량에 등록된 운전자만 선택할 수 있습니다.")
    path, original_name, media_type = await _save_image(photo, "vehicle")
    extracted: dict[str, Any] | None = None
    extraction_error: str | None = None
    try:
        extracted = await run_in_threadpool(extract_image, path, media_type, "odometer")
    except Exception as exc:
        extraction_error = type(exc).__name__
    extracted_odometer = extracted.get("odometer_km") if extracted else None
    final_odometer = odometer_km if odometer_km is not None else extracted_odometer
    extracted_trip = extracted.get("trip_km") if extracted else None
    final_trip = trip_km if trip_km is not None else extracted_trip
    if final_trip is None and final_odometer is not None:
        previous = (
            db.query(SafetyVehicleLog)
            .filter(
                SafetyVehicleLog.vehicle_id == vehicle.id,
                SafetyVehicleLog.odometer_km.isnot(None),
                SafetyVehicleLog.driven_on <= driven_on,
            )
            .order_by(SafetyVehicleLog.driven_on.desc(), SafetyVehicleLog.id.desc())
            .first()
        )
        if previous and previous.odometer_km is not None and final_odometer >= previous.odometer_km:
            final_trip = final_odometer - previous.odometer_km
    confidence = int(extracted.get("confidence", 0)) if extracted else None
    status_value = "AUTO_EXTRACTED" if extracted else ("EXTRACTION_FAILED" if extraction_error else "NEEDS_REVIEW")
    row = SafetyVehicleLog(
        vehicle_id=vehicle.id,
        driven_on=driven_on,
        driver_name=clean_driver,
        odometer_km=final_odometer,
        trip_km=final_trip,
        purpose=(purpose or "").strip() or None,
        dashboard_image_path=_relative_path(path),
        dashboard_original_name=original_name,
        extraction_status=status_value,
        extraction_confidence=confidence,
        extraction_raw_json=json.dumps(extracted or {"error": extraction_error}, ensure_ascii=False),
        created_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    row.vehicle = vehicle
    _export_paths(db)
    return _serialize_vehicle_log(row)


@router.put("/vehicles/{vehicle_id}/drivers")
def update_vehicle_drivers(
    vehicle_id: int,
    payload: VehicleDriversUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_access(current_user)
    vehicle = _ensure_pilot_vehicle(db)
    if vehicle.id != vehicle_id:
        raise HTTPException(status_code=404, detail="차량을 찾을 수 없습니다.")
    existing = {row.driver_name: row for row in vehicle.drivers}
    requested = set(payload.driver_names)
    for row in vehicle.drivers:
        row.is_active = row.driver_name in requested
        db.add(row)
    for order, name in enumerate(payload.driver_names, 1):
        row = existing.get(name)
        if row is None:
            row = SafetyVehicleDriver(vehicle_id=vehicle.id, driver_name=name)
        row.sort_order = order
        row.is_active = True
        db.add(row)
    db.commit()
    refreshed = _ensure_pilot_vehicle(db)
    return {"drivers": [row.driver_name for row in refreshed.drivers if row.is_active], "max_drivers": 4}


@router.patch("/vehicle-logs/{log_id}")
def review_vehicle_log(
    log_id: int,
    payload: VehicleLogReview,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_access(current_user)
    row = db.query(SafetyVehicleLog).options(joinedload(SafetyVehicleLog.vehicle)).filter_by(id=log_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="운행기록을 찾을 수 없습니다.")
    allowed = {driver.driver_name for driver in _ensure_pilot_vehicle(db).drivers if driver.is_active}
    if payload.driver_name not in allowed:
        raise HTTPException(status_code=400, detail="등록된 운전자만 선택할 수 있습니다.")
    for field in ("driven_on", "driver_name", "odometer_km", "trip_km", "use_type", "purpose"):
        setattr(row, field, getattr(payload, field))
    if payload.confirm:
        if row.trip_km is None:
            raise HTTPException(status_code=400, detail="확정하려면 주행km를 입력해 주세요.")
        row.extraction_status = "CONFIRMED"
        row.reviewed_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    _export_paths(db)
    return _serialize_vehicle_log(row)


@router.post("/card-expenses")
async def create_card_expense(
    db: DbDep,
    current_user: CurrentUserDep,
    receipt: Annotated[UploadFile, File(...)],
    used_at: Annotated[datetime | None, Form()] = None,
    site_name: Annotated[str | None, Form()] = None,
    merchant: Annotated[str | None, Form()] = None,
    amount: Annotated[int | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    card_last4: Annotated[str | None, Form()] = None,
    note: Annotated[str | None, Form()] = None,
):
    _assert_access(current_user)
    path, original_name, media_type = await _save_image(receipt, "receipts")
    extracted: dict[str, Any] | None = None
    extraction_error: str | None = None
    try:
        extracted = await run_in_threadpool(extract_image, path, media_type, "receipt")
    except Exception as exc:
        extraction_error = type(exc).__name__
    extracted_used_at = (
        _parse_iso_datetime(extracted.get("transaction_date"), extracted.get("transaction_time"))
        if extracted
        else None
    )
    confidence = int(extracted.get("confidence", 0)) if extracted else None
    status_value = "AUTO_EXTRACTED" if extracted else ("EXTRACTION_FAILED" if extraction_error else "NEEDS_REVIEW")
    row = SafetyCardExpense(
        used_at=used_at or extracted_used_at,
        site_name=(site_name or "").strip() or None,
        merchant=(merchant or "").strip() or (str(extracted.get("merchant") or "").strip() if extracted else None) or None,
        amount=amount if amount is not None else (extracted.get("amount") if extracted else None),
        description=(description or "").strip()
        or (str(extracted.get("description") or "").strip() if extracted else None)
        or None,
        card_last4=_card_last4(card_last4) or (_card_last4(extracted.get("card_last4")) if extracted else None),
        note=(note or "").strip() or None,
        receipt_image_path=_relative_path(path),
        receipt_original_name=original_name,
        extraction_status=status_value,
        extraction_confidence=confidence,
        extraction_raw_json=json.dumps(extracted or {"error": extraction_error}, ensure_ascii=False),
        created_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _export_paths(db)
    return _serialize_card(row)


@router.patch("/card-expenses/{expense_id}")
def review_card_expense(
    expense_id: int,
    payload: CardExpenseReview,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_access(current_user)
    row = db.query(SafetyCardExpense).filter_by(id=expense_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="법인카드 내역을 찾을 수 없습니다.")
    for field in ("used_at", "site_name", "merchant", "amount", "description", "card_last4", "note"):
        setattr(row, field, getattr(payload, field))
    if payload.confirm:
        if row.used_at is None or row.merchant is None or row.amount is None:
            raise HTTPException(status_code=400, detail="확정하려면 사용일시, 사용처, 금액을 입력해 주세요.")
        row.extraction_status = "CONFIRMED"
        row.reviewed_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    _export_paths(db)
    return _serialize_card(row)


def _image_response(path_value: str, original_name: str) -> FileResponse:
    path = settings.storage_root / path_value
    if not path.exists():
        raise HTTPException(status_code=404, detail="사진 파일을 찾을 수 없습니다.")
    response = FileResponse(path, filename=original_name)
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(original_name)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@router.get("/vehicle-logs/{log_id}/image")
def vehicle_image(log_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    row = db.query(SafetyVehicleLog).filter_by(id=log_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="운행기록을 찾을 수 없습니다.")
    return _image_response(row.dashboard_image_path, row.dashboard_original_name)


@router.get("/card-expenses/{expense_id}/image")
def receipt_image(expense_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    row = db.query(SafetyCardExpense).filter_by(id=expense_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="법인카드 내역을 찾을 수 없습니다.")
    return _image_response(row.receipt_image_path, row.receipt_original_name)


@router.get("/exports/{kind}")
def download_export(kind: str, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    card_path, vehicle_path = _export_paths(db)
    if kind == "card":
        path, filename = card_path, CARD_FILENAME
    elif kind == "vehicle":
        path, filename = vehicle_path, VEHICLE_FILENAME
    else:
        raise HTTPException(status_code=404, detail="지원하지 않는 결과 파일입니다.")
    response = FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
