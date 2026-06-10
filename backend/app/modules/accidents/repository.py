# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.accidents.models import Accident, AccidentAttachment, AccidentSiteStandard

_ATTACHMENT_EXISTS = exists(
    select(1).select_from(AccidentAttachment).where(AccidentAttachment.accident_id_fk == Accident.id)
)


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


def _apply_list_filters(
    stmt,
    *,
    queue_keys: list[str] | None = None,
    statuses: list[str] | None = None,
    management_categories: list[str] | None = None,
    only_incomplete: bool = False,
    default_queue_only: bool = True,
    parse_status_not: str | None = None,
    missing_attachments_only: bool = False,
    updated_since: datetime | None = None,
):
    if queue_keys:
        queue_filters = []
        if "신규" in queue_keys:
            queue_filters.append(Accident.status == "신규")
        if "미완성" in queue_keys:
            queue_filters.append(Accident.is_complete.is_(False))
        if "별도관리" in queue_keys:
            queue_filters.append(Accident.management_category == "별도관리")
        if queue_filters:
            stmt = stmt.where(or_(*queue_filters))
    if statuses:
        stmt = stmt.where(Accident.status.in_(statuses))
    if management_categories:
        stmt = stmt.where(Accident.management_category.in_(management_categories))
    if only_incomplete:
        stmt = stmt.where(Accident.is_complete.is_(False))
    if default_queue_only and not statuses and not management_categories and not queue_keys:
        stmt = stmt.where(Accident.parse_status != "success")
    if parse_status_not:
        stmt = stmt.where(Accident.parse_status != parse_status_not)
    if missing_attachments_only:
        stmt = stmt.where(~_ATTACHMENT_EXISTS)
    if updated_since is not None:
        stmt = stmt.where(Accident.updated_at > updated_since)
    return stmt


def list_accidents(
    db: Session,
    *,
    queue_keys: list[str] | None = None,
    statuses: list[str] | None = None,
    management_categories: list[str] | None = None,
    only_incomplete: bool = False,
    default_queue_only: bool = True,
    parse_status_not: str | None = None,
    missing_attachments_only: bool = False,
    updated_since: datetime | None = None,
    order_by: str = "accident_datetime",
    limit: int = 500,
    with_attachments: bool = False,
) -> list[Accident]:
    q = select(Accident)
    q = _apply_list_filters(
        q,
        queue_keys=queue_keys,
        statuses=statuses,
        management_categories=management_categories,
        only_incomplete=only_incomplete,
        default_queue_only=default_queue_only,
        parse_status_not=parse_status_not,
        missing_attachments_only=missing_attachments_only,
        updated_since=updated_since,
    )
    if order_by == "created_at":
        q = q.order_by(Accident.created_at.desc(), Accident.id.desc())
    else:
        q = q.order_by(Accident.accident_datetime.desc().nullslast(), Accident.created_at.desc())
    if limit:
        q = q.limit(limit)
    if with_attachments:
        q = q.options(selectinload(Accident.attachments))
    return list(db.scalars(q).all())


def count_accidents(
    db: Session,
    *,
    queue_keys: list[str] | None = None,
    statuses: list[str] | None = None,
    management_categories: list[str] | None = None,
    only_incomplete: bool = False,
    default_queue_only: bool = False,
    parse_status_not: str | None = None,
    missing_attachments_only: bool = False,
) -> int:
    q = select(func.count()).select_from(Accident)
    q = _apply_list_filters(
        q,
        queue_keys=queue_keys,
        statuses=statuses,
        management_categories=management_categories,
        only_incomplete=only_incomplete,
        default_queue_only=default_queue_only,
        parse_status_not=parse_status_not,
        missing_attachments_only=missing_attachments_only,
    )
    return int(db.scalar(q) or 0)


def list_accidents_with_attachment_flags(
    db: Session,
    *,
    queue_keys: list[str] | None = None,
    statuses: list[str] | None = None,
    management_categories: list[str] | None = None,
    only_incomplete: bool = False,
    default_queue_only: bool = True,
    parse_status_not: str | None = None,
    missing_attachments_only: bool = False,
    updated_since: datetime | None = None,
    order_by: str = "accident_datetime",
    limit: int = 500,
) -> list[tuple[Accident, bool]]:
    stmt = select(Accident, _ATTACHMENT_EXISTS.label("has_attachments"))
    stmt = _apply_list_filters(
        stmt,
        queue_keys=queue_keys,
        statuses=statuses,
        management_categories=management_categories,
        only_incomplete=only_incomplete,
        default_queue_only=default_queue_only,
        parse_status_not=parse_status_not,
        missing_attachments_only=missing_attachments_only,
        updated_since=updated_since,
    )
    if order_by == "created_at":
        stmt = stmt.order_by(Accident.created_at.desc(), Accident.id.desc())
    else:
        stmt = stmt.order_by(Accident.accident_datetime.desc().nullslast(), Accident.created_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    return [(row, bool(has_att)) for row, has_att in db.execute(stmt).all()]


def get_accident(db: Session, accident_id: int) -> Accident | None:
    stmt = (
        select(Accident)
        .where(Accident.id == accident_id)
        .options(selectinload(Accident.attachments))
    )
    return db.scalar(stmt)


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
