# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.accidents.models import Accident, AccidentAttachment, AccidentSiteStandard


def next_display_code(db: Session, *, year: int) -> str:
    """ACC-YYYY-NNNN — 문자열 max 대신 최신 id 기준으로 증가(10000건 이상에서도 안전)."""
    prefix = f"ACC-{year}-"
    q = (
        select(Accident.display_code)
        .where(Accident.display_code.like(f"{prefix}%"))
        .order_by(Accident.id.desc())
        .limit(1)
    )
    row = db.execute(q).scalar_one_or_none()
    if not row:
        return f"{prefix}0001"
    try:
        tail = int(str(row).split("-")[-1])
    except (ValueError, IndexError):
        tail = 0
    return f"{prefix}{tail + 1:04d}"


def next_accident_id(db: Session, *, year: int) -> str:
    prefix = f"{year}-"
    q = (
        select(Accident.accident_id)
        .where(Accident.accident_id.like(f"{prefix}%"))
        .order_by(Accident.id.desc())
        .limit(1)
    )
    row = db.execute(q).scalar_one_or_none()
    if not row:
        return f"{prefix}001"
    try:
        tail = int(str(row).split("-")[-1])
    except (ValueError, IndexError):
        tail = 0
    return f"{prefix}{tail + 1:03d}"


def create_accident(
    db: Session,
    *,
    display_code: str,
    accident_id: str,
    source_type: str,
    message_raw: str,
    parse_status: str,
    parse_note: str | None,
    site_name: str | None,
    reporter_name: str | None,
    accident_datetime_text: str | None,
    accident_datetime: datetime | None,
    accident_place: str | None,
    work_content: str | None,
    injured_person_name: str | None,
    accident_circumstance: str | None,
    accident_reason: str | None,
    injured_part: str | None,
    diagnosis_name: str | None,
    action_taken: str | None,
    status: str,
    management_category: str,
    verification_status: str,
    site_standard_name: str | None,
    initial_report_template: str | None,
    is_complete: bool,
    nas_folder_path: str | None,
    nas_folder_key: str | None,
    notes: str | None,
    created_by_user_id: int | None,
    updated_by_user_id: int | None,
) -> Accident:
    row = Accident(
        display_code=display_code,
        accident_id=accident_id,
        source_type=source_type,
        message_raw=message_raw,
        parse_status=parse_status,
        parse_note=parse_note,
        site_name=site_name,
        reporter_name=reporter_name,
        accident_datetime_text=accident_datetime_text,
        accident_datetime=accident_datetime,
        accident_place=accident_place,
        work_content=work_content,
        injured_person_name=injured_person_name,
        accident_circumstance=accident_circumstance,
        accident_reason=accident_reason,
        injured_part=injured_part,
        diagnosis_name=diagnosis_name,
        action_taken=action_taken,
        status=status,
        management_category=management_category,
        verification_status=verification_status,
        site_standard_name=site_standard_name,
        initial_report_template=initial_report_template,
        is_complete=is_complete,
        nas_folder_path=nas_folder_path,
        nas_folder_key=nas_folder_key,
        notes=notes,
        created_by_user_id=created_by_user_id,
        updated_by_user_id=updated_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_accidents(
    db: Session,
    *,
    queue_keys: list[str] | None = None,
    statuses: list[str] | None = None,
    management_categories: list[str] | None = None,
    only_incomplete: bool = False,
    default_queue_only: bool = True,
    limit: int = 500,
) -> list[Accident]:
    q = select(Accident)
    if queue_keys:
        queue_filters = []
        if "신규" in queue_keys:
            queue_filters.append(Accident.status == "신규")
        if "미완성" in queue_keys:
            queue_filters.append(Accident.is_complete.is_(False))
        if "별도관리" in queue_keys:
            queue_filters.append(Accident.management_category == "별도관리")
        if queue_filters:
            q = q.where(or_(*queue_filters))
    if statuses:
        q = q.where(Accident.status.in_(statuses))
    if management_categories:
        q = q.where(Accident.management_category.in_(management_categories))
    if only_incomplete:
        q = q.where(Accident.is_complete.is_(False))
    if default_queue_only and not statuses and not management_categories and not queue_keys:
        q = q.where(Accident.parse_status != "success")
    q = q.order_by(Accident.accident_datetime.desc().nullslast(), Accident.created_at.desc()).limit(limit)
    return list(db.scalars(q).all())


def get_accident(db: Session, accident_id: int) -> Accident | None:
    return db.get(Accident, accident_id)


def update_accident(db: Session, row: Accident, **fields) -> Accident:
    for key, value in fields.items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_accident(db: Session, row: Accident) -> None:
    db.delete(row)
    db.commit()


def add_attachment(
    db: Session,
    *,
    accident_id_fk: int,
    file_name: str,
    stored_path: str,
    content_type: str | None,
    file_size: int | None,
) -> AccidentAttachment:
    row = AccidentAttachment(
        accident_id_fk=accident_id_fk,
        file_name=file_name,
        stored_path=stored_path,
        content_type=content_type,
        file_size=file_size,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_site_standards(db: Session) -> list[AccidentSiteStandard]:
    q = select(AccidentSiteStandard).where(AccidentSiteStandard.is_active.is_(True)).order_by(
        func.lower(AccidentSiteStandard.site_name).asc()
    )
    return list(db.scalars(q).all())


def ensure_site_standard(db: Session, site_name: str) -> AccidentSiteStandard | None:
    normalized = (site_name or "").strip()
    if not normalized:
        return None
    existing = (
        db.execute(
            select(AccidentSiteStandard).where(func.lower(AccidentSiteStandard.site_name) == normalized.lower())
        )
        .scalar_one_or_none()
    )
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.add(existing)
            db.commit()
            db.refresh(existing)
        return existing
    row = AccidentSiteStandard(site_name=normalized, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_accident_by_accident_code(db: Session, accident_code: str) -> Accident | None:
    return db.execute(select(Accident).where(Accident.accident_id == accident_code)).scalar_one_or_none()


def get_attachment(db: Session, attachment_id: int) -> AccidentAttachment | None:
    return db.get(AccidentAttachment, attachment_id)
