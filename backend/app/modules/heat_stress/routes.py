from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from app.core.auth import DbDep
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.core.permissions import CurrentUserDep, HQ_SAFE_WORKSPACE_ROLES
from app.modules.functional_eval.signature_service import validate_signature_data
from app.modules.heat_stress.models import HeatStressAuditLog, HeatStressRecord
from app.modules.heat_stress.pdf import build_default_pdf
from app.modules.heat_stress.schemas import HeatStressConfirm, HeatStressCreate
from app.modules.heat_stress.service import (
    ACTION_LABELS,
    FORMULA_VERSION,
    action_compliance,
    actions_json,
    calculate_apparent_temperature,
    parse_actions,
    policy_for,
)
from app.modules.sites.models import Site

router = APIRouter(prefix="/heat-stress", tags=["heat-stress"])


def _role(user) -> Role | str:
    return user.role


def _is_hq(user) -> bool:
    return _role(user) in HQ_SAFE_WORKSPACE_ROLES


def _is_site(user) -> bool:
    return _role(user) in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}


def _assert_site_context(user) -> int:
    if not _is_site(user) or not user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="현장 계정만 기록할 수 있습니다.")
    return int(user.site_id)


def _assert_view(user, record: HeatStressRecord) -> None:
    if _is_hq(user):
        return
    if _is_site(user) and user.site_id == record.site_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="열람 권한이 없습니다.")


def _record_payload(record: HeatStressRecord, site_name: str | None = None) -> dict:
    policy = policy_for(record.apparent_temperature_c)
    return {
        "id": record.id,
        "site_id": record.site_id,
        "site_name": site_name,
        "measured_at": record.measured_at,
        "work_location": record.work_location,
        "work_process": record.work_process,
        "measurement_source": record.measurement_source,
        "air_temperature_c": record.air_temperature_c,
        "relative_humidity_pct": record.relative_humidity_pct,
        "apparent_temperature_c": record.apparent_temperature_c,
        "formula_version": record.formula_version,
        "risk_level": record.risk_level,
        "risk_label": policy["risk_label"],
        "legal_guidance": record.legal_guidance,
        "company_guidance": record.company_guidance,
        "actual_actions": parse_actions(record.actual_actions_json),
        "actual_action_labels": [ACTION_LABELS.get(code, code) for code in parse_actions(record.actual_actions_json)],
        "action_notes": record.action_notes,
        "action_compliance": record.action_compliance,
        "recorder_name": record.recorder_name,
        "recorder_signed_at": record.recorder_signed_at,
        "confirmer_name": record.confirmer_name,
        "confirmer_title": record.confirmer_title,
        "confirmer_signed_at": record.confirmer_signed_at,
        "status": record.status,
        "template_code": record.template_code,
        "created_at": record.created_at,
    }


@router.get("/policy")
def get_policy(
    current_user: CurrentUserDep,
    air_temperature_c: float = Query(..., ge=-20, le=60),
    relative_humidity_pct: float = Query(..., ge=0, le=100),
):
    apparent = calculate_apparent_temperature(air_temperature_c, relative_humidity_pct)
    return {
        "apparent_temperature_c": apparent,
        "formula_version": FORMULA_VERSION,
        **policy_for(apparent),
        "action_options": [{"code": code, "label": label} for code, label in ACTION_LABELS.items()],
        "notice": "자동 안내는 조치 완료 기록이 아닙니다. 실제 실시한 조치를 선택한 뒤 서명하세요.",
    }


@router.post("/records", status_code=status.HTTP_201_CREATED)
def create_record(payload: HeatStressCreate, db: DbDep, current_user: CurrentUserDep):
    site_id = _assert_site_context(current_user)
    try:
        signature_sha, _ = validate_signature_data(payload.recorder_signature_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    apparent = calculate_apparent_temperature(payload.air_temperature_c, payload.relative_humidity_pct)
    policy = policy_for(apparent)
    now = utc_now()
    record = HeatStressRecord(
        site_id=site_id,
        measured_at=payload.measured_at.replace(tzinfo=None),
        work_location=payload.work_location.strip(),
        work_process=(payload.work_process or "").strip() or None,
        measurement_source=payload.measurement_source,
        air_temperature_c=payload.air_temperature_c,
        relative_humidity_pct=payload.relative_humidity_pct,
        apparent_temperature_c=apparent,
        formula_version=FORMULA_VERSION,
        risk_level=policy["risk_level"],
        legal_guidance=policy["legal_guidance"],
        company_guidance=policy["company_guidance"],
        actual_actions_json=actions_json(payload.actual_actions),
        action_notes=(payload.action_notes or "").strip() or None,
        action_compliance=action_compliance(apparent, payload.actual_actions),
        recorder_user_id=current_user.id,
        recorder_name=current_user.name,
        recorder_signature_data=payload.recorder_signature_data,
        recorder_signature_sha256=signature_sha,
        recorder_signed_at=now,
        status="CONFIRM_PENDING",
        template_code="HQ_DEFAULT_V1",
    )
    db.add(record)
    db.flush()
    db.add(HeatStressAuditLog(
        record_id=record.id,
        event_type="CREATE_AND_SIGN",
        actor_user_id=current_user.id,
        actor_name=current_user.name,
        detail_json=json.dumps({"formula": FORMULA_VERSION, "actions": payload.actual_actions}, ensure_ascii=False),
    ))
    db.commit()
    db.refresh(record)
    site_name = db.query(Site.site_name).filter(Site.id == site_id).scalar()
    return _record_payload(record, site_name)


@router.get("/records")
def list_records(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
):
    if not (_is_site(current_user) or _is_hq(current_user)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="열람 권한이 없습니다.")
    resolved_site_id = current_user.site_id if _is_site(current_user) else site_id
    query = db.query(HeatStressRecord, Site.site_name).join(Site, Site.id == HeatStressRecord.site_id)
    if resolved_site_id:
        query = query.filter(HeatStressRecord.site_id == resolved_site_id)
    if date_from:
        query = query.filter(HeatStressRecord.measured_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(HeatStressRecord.measured_at < datetime.combine(date_to + timedelta(days=1), time.min))
    if status_filter:
        query = query.filter(HeatStressRecord.status == status_filter.upper())
    rows = query.order_by(HeatStressRecord.measured_at.desc(), HeatStressRecord.id.desc()).limit(limit).all()
    return {"items": [_record_payload(record, site_name) for record, site_name in rows], "count": len(rows)}


@router.get("/records/{record_id}")
def get_record(record_id: int, db: DbDep, current_user: CurrentUserDep):
    row = db.query(HeatStressRecord, Site.site_name).join(Site, Site.id == HeatStressRecord.site_id).filter(
        HeatStressRecord.id == record_id
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    record, site_name = row
    _assert_view(current_user, record)
    return _record_payload(record, site_name)


@router.post("/records/{record_id}/confirm")
def confirm_record(record_id: int, payload: HeatStressConfirm, db: DbDep, current_user: CurrentUserDep):
    site_id = _assert_site_context(current_user)
    record = db.query(HeatStressRecord).filter(HeatStressRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    if record.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="다른 현장 기록은 확인할 수 없습니다.")
    if record.status == "CONFIRMED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 확인 서명이 완료된 기록입니다.")
    try:
        signature_sha, _ = validate_signature_data(payload.confirmer_signature_data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    record.confirmer_user_id = current_user.id
    record.confirmer_name = payload.confirmer_name.strip()
    record.confirmer_title = payload.confirmer_title.strip()
    record.confirmer_signature_data = payload.confirmer_signature_data
    record.confirmer_signature_sha256 = signature_sha
    record.confirmer_signed_at = utc_now()
    record.status = "CONFIRMED"
    db.add(HeatStressAuditLog(
        record_id=record.id,
        event_type="CONFIRM_SIGN",
        actor_user_id=current_user.id,
        actor_name=current_user.name,
        detail_json=json.dumps({"title": record.confirmer_title}, ensure_ascii=False),
    ))
    db.commit()
    db.refresh(record)
    site_name = db.query(Site.site_name).filter(Site.id == site_id).scalar()
    return _record_payload(record, site_name)


@router.get("/records/{record_id}/pdf")
def download_record_pdf(record_id: int, db: DbDep, current_user: CurrentUserDep):
    row = db.query(HeatStressRecord, Site.site_name).join(Site, Site.id == HeatStressRecord.site_id).filter(
        HeatStressRecord.id == record_id
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="기록을 찾을 수 없습니다.")
    record, site_name = row
    _assert_view(current_user, record)
    content = build_default_pdf(record, site_name)
    db.add(HeatStressAuditLog(
        record_id=record.id,
        event_type="PDF_EXPORT",
        actor_user_id=current_user.id,
        actor_name=current_user.name,
        detail_json=json.dumps({"template": record.template_code}, ensure_ascii=False),
    ))
    db.commit()
    filename = f"{site_name}_체감온도기록_{record.measured_at.strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/hq-summary")
def hq_summary(db: DbDep, current_user: CurrentUserDep, target_date: date | None = Query(None)):
    if not _is_hq(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본사 안전 권한이 필요합니다.")
    day = target_date or date.today()
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)
    base = db.query(HeatStressRecord).filter(HeatStressRecord.measured_at >= start, HeatStressRecord.measured_at < end)
    active_sites = db.query(Site.id).filter(func.upper(func.coalesce(Site.status, "")) != "CLOSED").all()
    recorded_site_ids = {row[0] for row in base.with_entities(HeatStressRecord.site_id).distinct().all()}
    return {
        "target_date": day,
        "active_site_count": len(active_sites),
        "recorded_site_count": len(recorded_site_ids),
        "missing_site_count": max(0, len(active_sites) - len(recorded_site_ids)),
        "at_or_above_31_count": base.filter(HeatStressRecord.apparent_temperature_c >= 31).count(),
        "at_or_above_33_count": base.filter(HeatStressRecord.apparent_temperature_c >= 33).count(),
        "action_required_count": base.filter(HeatStressRecord.action_compliance == "ACTION_REQUIRED").count(),
        "confirm_pending_count": base.filter(HeatStressRecord.status == "CONFIRM_PENDING").count(),
        "total_record_count": base.count(),
    }
