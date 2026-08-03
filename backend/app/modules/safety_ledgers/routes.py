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
    SafetyCardAccount,
    SafetyCardExpense,
    SafetyVehicle,
    SafetyVehicleDriver,
    SafetyVehicleLog,
)
from app.modules.safety_ledgers.schemas import (
    CardAccountUpdate,
    CardExpenseReview,
    VehicleDriversUpdate,
    VehicleLogReview,
)
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
_PILOT_USER_NAMES = frozenset({"정상익", "엄재복", "박영선", "조동문"})
_SHARED_CARD_USER_NAMES = frozenset({"정상익", "엄재복", "박영선"})
_SHARED_CARD_SCOPE = "SAFETY_SHARED"
_JO_CARD_SCOPE = "JO_DONGMUN"
_DEFAULT_CARD_NUMBERS = {
    _SHARED_CARD_SCOPE: "5585-03**-****-6925",
    _JO_CARD_SCOPE: "5585-03**-****-3946",
}


def _assert_access(user) -> None:
    assert_hq_safe_workspace(user)
    if (getattr(user, "name", "") or "").strip() not in _PILOT_USER_NAMES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="법인카드·운행기록부 시범 운영 대상 계정이 아닙니다.",
        )


def _card_scope(user) -> tuple[str, str]:
    name = (getattr(user, "name", "") or "").strip()
    if name in _SHARED_CARD_USER_NAMES:
        return _SHARED_CARD_SCOPE, "안전실 공용카드"
    if name == "조동문":
        return _JO_CARD_SCOPE, "조동문 법인카드"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="등록된 법인카드가 없습니다.")


def _ensure_card_account(db, user) -> SafetyCardAccount:
    card_scope, card_label = _card_scope(user)
    account = db.query(SafetyCardAccount).filter(SafetyCardAccount.card_scope == card_scope).first()
    if account is None:
        masked = _DEFAULT_CARD_NUMBERS[card_scope]
        account = SafetyCardAccount(
            card_scope=card_scope,
            label=card_label,
            card_number_masked=masked,
            card_last4=_card_last4(masked) or "",
            updated_by_user_id=getattr(user, "id", None),
        )
        db.add(account)
        db.commit()
        db.refresh(account)
    return account


def _masked_card_number(value: str) -> tuple[str, str]:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 4:
        return f"****-****-****-{digits}", digits
    if len(digits) == 16:
        return f"{digits[:4]}-{digits[4:6]}**-****-{digits[-4:]}", digits[-4:]
    raise HTTPException(status_code=400, detail="카드번호 16자리 또는 마지막 4자리를 입력해 주세요.")


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


def _ensure_vehicle_for_user(db, user) -> SafetyVehicle:
    user_name = (getattr(user, "name", "") or "").strip()
    if user_name == "조동문":
        vehicle_name, plate_number, drivers = "그랜저", "160하3180", ("조동문",)
    else:
        vehicle_name, plate_number, drivers = "투싼", "181하8339", ("정상익", "박영선")

    vehicle = db.query(SafetyVehicle).filter(SafetyVehicle.plate_number == plate_number).first()
    if vehicle is None:
        vehicle = SafetyVehicle(vehicle_name=vehicle_name, plate_number=plate_number, department="안전보건실")
        db.add(vehicle)
        db.flush()
    existing = {row.driver_name for row in vehicle.drivers}
    for order, driver_name in enumerate(drivers, 1):
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


def _normalized_description(description: str | None, merchant: str | None) -> str | None:
    clean = (description or "").strip()
    text = f"{clean} {(merchant or '').strip()}".lower()
    category_keywords = (
        ("주유비", ("주유", "휘발유", "경유", "gasoline", "diesel")),
        ("중식비", ("중식", "점심", "lunch")),
        ("석식비", ("석식", "저녁", "dinner")),
        ("회식비", ("회식",)),
        ("주차비", ("주차", "parking")),
        ("통행료", ("통행", "하이패스", "톨게이트")),
        ("숙박비", ("숙박", "호텔", "모텔")),
    )
    for category, keywords in category_keywords:
        if any(keyword in text for keyword in keywords):
            return category
    return clean or None


def _vehicle_destination(purpose: str | None) -> str | None:
    clean = (purpose or "").strip()
    match = re.search(r"[↔→]\s*([^;]+)", clean)
    destination = match.group(1).strip() if match else clean
    if destination in {"회사", "후곡마을(자택)", "자택"}:
        return None
    if destination in {"", "본사", "안전보건실 업무"}:
        return None
    return destination or None


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
        "card_scope": row.card_scope,
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


def _export_paths(db, user) -> tuple[Path, Path]:
    card_scope, _card_label = _card_scope(user)
    vehicle = _ensure_vehicle_for_user(db, user)
    export_dir = _storage_dir("exports")
    vehicle_logs = (
        db.query(SafetyVehicleLog)
        .filter(SafetyVehicleLog.vehicle_id == vehicle.id)
        .order_by(SafetyVehicleLog.driven_on.asc(), SafetyVehicleLog.id.asc())
        .all()
    )
    expenses = (
        db.query(SafetyCardExpense)
        .filter(SafetyCardExpense.card_scope == card_scope)
        .order_by(SafetyCardExpense.used_at.asc(), SafetyCardExpense.id.asc())
        .all()
    )
    destination_candidates: dict[date, set[str]] = {}
    for log in vehicle_logs:
        destination = _vehicle_destination(log.purpose)
        if destination:
            destination_candidates.setdefault(log.driven_on, set()).add(destination)
    site_names_by_date = {
        driven_on: next(iter(candidates))
        for driven_on, candidates in destination_candidates.items()
        if len(candidates) == 1
    }
    card_filename = CARD_FILENAME if card_scope == _SHARED_CARD_SCOPE else "조동문_법인카드 정산서.xlsx"
    vehicle_filename = (
        VEHICLE_FILENAME
        if vehicle.plate_number == "181하8339"
        else "조동문_업무용승용차 운행기록부.xlsx"
    )
    card_template = (
        settings.safety_ledger_card_template_path
        if card_scope == _SHARED_CARD_SCOPE
        else settings.safety_ledger_jo_card_template_path
    )
    card_path = build_card_workbook(
        expenses,
        export_dir / card_filename,
        template_path=card_template,
        site_names_by_date=site_names_by_date,
    )
    vehicle_path = build_vehicle_workbook(
        vehicle,
        vehicle_logs,
        export_dir / vehicle_filename,
        template_path=settings.safety_ledger_vehicle_template_path,
    )
    copy_exports_to_nas((card_path, vehicle_path), settings.safety_ledger_nas_root)
    return card_path, vehicle_path


@router.get("/bootstrap")
def bootstrap(db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    card_scope, _card_label = _card_scope(current_user)
    card_account = _ensure_card_account(db, current_user)
    vehicle = _ensure_vehicle_for_user(db, current_user)
    logs = (
        db.query(SafetyVehicleLog)
        .options(joinedload(SafetyVehicleLog.vehicle))
        .filter(SafetyVehicleLog.vehicle_id == vehicle.id)
        .order_by(SafetyVehicleLog.driven_on.desc(), SafetyVehicleLog.id.desc())
        .all()
    )
    expenses = (
        db.query(SafetyCardExpense)
        .filter(SafetyCardExpense.card_scope == card_scope)
        .order_by(SafetyCardExpense.created_at.desc())
        .all()
    )
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
        "card_account": {
            "scope": card_scope,
            "label": card_account.label,
            "card_number_masked": card_account.card_number_masked,
            "card_last4": card_account.card_last4,
        },
        "vision_enabled": bool((settings.openai_api_key or "").strip()),
        "vision_model": settings.safety_ledger_vision_model,
        "review_threshold": _CONFIRM_THRESHOLD,
    }


@router.put("/card-account")
def update_card_account(
    payload: CardAccountUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_access(current_user)
    account = _ensure_card_account(db, current_user)
    masked, last4 = _masked_card_number(payload.card_number)
    account.card_number_masked = masked
    account.card_last4 = last4
    account.updated_by_user_id = current_user.id
    db.add(account)
    db.commit()
    db.refresh(account)
    return {
        "scope": account.card_scope,
        "label": account.label,
        "card_number_masked": account.card_number_masked,
        "card_last4": account.card_last4,
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
    vehicle = _ensure_vehicle_for_user(db, current_user)
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
    _export_paths(db, current_user)
    return _serialize_vehicle_log(row)


@router.put("/vehicles/{vehicle_id}/drivers")
def update_vehicle_drivers(
    vehicle_id: int,
    payload: VehicleDriversUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_access(current_user)
    vehicle = _ensure_vehicle_for_user(db, current_user)
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
    refreshed = _ensure_vehicle_for_user(db, current_user)
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
    vehicle = _ensure_vehicle_for_user(db, current_user)
    if row.vehicle_id != vehicle.id:
        raise HTTPException(status_code=404, detail="운행기록을 찾을 수 없습니다.")
    allowed = {driver.driver_name for driver in vehicle.drivers if driver.is_active}
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
    _export_paths(db, current_user)
    return _serialize_vehicle_log(row)


@router.post("/card-expenses")
async def create_card_expense(
    db: DbDep,
    current_user: CurrentUserDep,
    receipt: Annotated[UploadFile, File(...)],
    used_at: Annotated[datetime | None, Form()] = None,
    used_at_is_default: Annotated[bool, Form()] = False,
    site_name: Annotated[str | None, Form()] = None,
    merchant: Annotated[str | None, Form()] = None,
    amount: Annotated[int | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    card_last4: Annotated[str | None, Form()] = None,
    note: Annotated[str | None, Form()] = None,
):
    _assert_access(current_user)
    card_scope, _card_label = _card_scope(current_user)
    card_account = _ensure_card_account(db, current_user)
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
        card_scope=card_scope,
        used_at=(extracted_used_at if used_at_is_default and extracted_used_at else used_at)
        or extracted_used_at
        or utc_now(),
        site_name=(site_name or "").strip() or None,
        merchant=(merchant or "").strip() or (str(extracted.get("merchant") or "").strip() if extracted else None) or None,
        amount=amount if amount is not None else (extracted.get("amount") if extracted else None),
        description=_normalized_description(
            (description or "").strip()
            or (str(extracted.get("description") or "").strip() if extracted else None),
            (merchant or "").strip() or (str(extracted.get("merchant") or "").strip() if extracted else None),
        ),
        card_last4=card_account.card_last4,
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
    _export_paths(db, current_user)
    return _serialize_card(row)


@router.patch("/card-expenses/{expense_id}")
def review_card_expense(
    expense_id: int,
    payload: CardExpenseReview,
    db: DbDep,
    current_user: CurrentUserDep,
):
    _assert_access(current_user)
    card_scope, _card_label = _card_scope(current_user)
    card_account = _ensure_card_account(db, current_user)
    row = (
        db.query(SafetyCardExpense)
        .filter(SafetyCardExpense.id == expense_id, SafetyCardExpense.card_scope == card_scope)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="법인카드 내역을 찾을 수 없습니다.")
    for field in ("used_at", "site_name", "merchant", "amount", "description", "note"):
        setattr(row, field, getattr(payload, field))
    row.description = _normalized_description(row.description, row.merchant)
    row.card_last4 = card_account.card_last4
    if payload.confirm:
        if row.used_at is None or row.merchant is None or row.amount is None:
            raise HTTPException(status_code=400, detail="확정하려면 사용일시, 사용처, 금액을 입력해 주세요.")
        row.extraction_status = "CONFIRMED"
        row.reviewed_at = utc_now()
    db.add(row)
    db.commit()
    db.refresh(row)
    _export_paths(db, current_user)
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
    vehicle = _ensure_vehicle_for_user(db, current_user)
    if row is None or row.vehicle_id != vehicle.id:
        raise HTTPException(status_code=404, detail="운행기록을 찾을 수 없습니다.")
    return _image_response(row.dashboard_image_path, row.dashboard_original_name)


@router.get("/card-expenses/{expense_id}/image")
def receipt_image(expense_id: int, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    card_scope, _card_label = _card_scope(current_user)
    row = (
        db.query(SafetyCardExpense)
        .filter(SafetyCardExpense.id == expense_id, SafetyCardExpense.card_scope == card_scope)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="법인카드 내역을 찾을 수 없습니다.")
    return _image_response(row.receipt_image_path, row.receipt_original_name)


@router.get("/exports/{kind}")
def download_export(kind: str, db: DbDep, current_user: CurrentUserDep):
    _assert_access(current_user)
    card_scope, _card_label = _card_scope(current_user)
    card_path, vehicle_path = _export_paths(db, current_user)
    if kind == "card":
        filename = CARD_FILENAME if card_scope == _SHARED_CARD_SCOPE else "조동문_법인카드 정산서.xlsx"
        path = card_path
    elif kind == "vehicle":
        filename = (
            VEHICLE_FILENAME
            if (getattr(current_user, "name", "") or "").strip() != "조동문"
            else "조동문_업무용승용차 운행기록부.xlsx"
        )
        path = vehicle_path
    else:
        raise HTTPException(status_code=404, detail="지원하지 않는 결과 파일입니다.")
    response = FileResponse(
        path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response
