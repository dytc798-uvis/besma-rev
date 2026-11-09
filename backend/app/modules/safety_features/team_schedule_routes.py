from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import update, and_, or_, func
from sqlalchemy.exc import IntegrityError

from app.core.auth import DbDep, get_current_user
from app.core.datetime_utils import utc_now
from app.modules.safety_features.team_schedule_access import (
    SURFACE_MOBILE_WEB,
    SURFACE_PC_WEB,
    SURFACE_SAFETY_WORKBENCH,
    find_team_schedule_member,
    normalize_team_schedule_surface,
    team_schedule_capabilities,
)
from app.modules.safety_features.team_assignment_flow import (
    ASSIGNMENT_MODE_SELF,
    ASSIGNMENT_STATUS_ACCEPTED,
    ASSIGNMENT_STATUS_COMPLETED,
    ASSIGNMENT_STATUS_PENDING,
    ASSIGNMENT_STATUS_REJECTED,
    assignment_badge_color,
    can_issue_directive,
    is_unread_assignment,
    parties_or_completed_can_read,
    resolve_assignment_mode,
)
from app.modules.safety_features.team_personal_request_models import TeamPersonalRequest
from app.modules.safety_features.team_schedule_models import (
    TeamCollaborationComment,
    TeamScheduleEvent,
    TeamScheduleItem,
    TeamScheduleMember,
    TeamWorkItem,
    WorkbenchUpdateEvent,
)
from app.modules.safety_features.team_schedule_schemas import (
    TeamCommentCreate,
    TeamScheduleCreate,
    TeamSchedulePcWriteConsent,
    TeamScheduleTransition,
    TeamScheduleUpdate,
    TeamWorkItemCreate,
    TeamWorkAssignmentAcknowledge,
    TeamWorkAssignmentDecision,
    TeamWorkItemUpdate,
    WorkbenchUpdateEventCreate,
)
from app.modules.users.models import User
from app.modules.safety_features.inspection_plan import (
    INSPECTION_SOURCE, schedule_owner_id, schedule_owner_name, build_trip_application_draft,
)


router = APIRouter(prefix="/safety-features/team-schedule", tags=["team-schedule"])
CurrentUserDep = Annotated[User, Depends(get_current_user)]
SurfaceHeader = Annotated[str | None, Header(alias="X-BESMA-Client-Surface")]

_SOURCE_BY_SURFACE = {
    SURFACE_PC_WEB: "WEB_PC",
    SURFACE_SAFETY_WORKBENCH: "SAFETY_WORKBENCH",
    SURFACE_MOBILE_WEB: "WEB_MOBILE",
}
PC_WRITE_CONSENT_VERSION = "jsi.team-desk.pc-write.v1"


def _member_or_403(db, current_user: User) -> TeamScheduleMember:
    member = find_team_schedule_member(db, current_user.id)
    if member is None or not member.can_read:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_SCHEDULE_NOT_ALLOWED",
        )
    return member


def _surface_or_400(raw: str | None) -> str:
    surface = normalize_team_schedule_surface(raw)
    if surface is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TEAM_SCHEDULE_CLIENT_SURFACE_REQUIRED",
        )
    return surface


def _require_write(db, current_user: User, raw_surface: str | None) -> tuple[TeamScheduleMember, str]:
    member = _member_or_403(db, current_user)
    surface = _surface_or_400(raw_surface)
    capabilities = team_schedule_capabilities(member, surface)
    if not capabilities.can_write:
        detail = (
            "TEAM_SCHEDULE_MOBILE_READ_ONLY"
            if surface == SURFACE_MOBILE_WEB
            else "TEAM_SCHEDULE_PC_WRITE_DISABLED"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return member, surface


def _clean_text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _utc_isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return aware.isoformat().replace("+00:00", "Z")


def _serialize_workbench_update_event(row: WorkbenchUpdateEvent, actor: User) -> dict:
    return {
        "id": row.id,
        "client_event_id": row.client_event_id,
        "actor_user_id": row.actor_user_id,
        "actor_name": actor.name,
        "actor_login_id": actor.login_id,
        "from_version": row.from_version,
        "target_version": row.target_version,
        "product_version": row.product_version,
        "release_notes": row.release_notes,
        "event_status": row.event_status,
        "error_code": row.error_code,
        "occurred_at": _utc_isoformat(row.client_occurred_at),
        "received_at": _utc_isoformat(row.received_at),
    }


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = tuple(int(part) for part in value.split("."))
    return parts + (0,) * (4 - len(parts))


def _validate_assignee(db, assigned_user_id: int | None) -> None:
    if assigned_user_id is None:
        return
    row = (
        db.query(TeamScheduleMember, User)
        .join(User, User.id == TeamScheduleMember.user_id)
        .filter(
            TeamScheduleMember.user_id == assigned_user_id,
            TeamScheduleMember.is_active.is_(True),
            TeamScheduleMember.can_read.is_(True),
            User.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TEAM_SCHEDULE_ASSIGNEE_NOT_MEMBER",
        )


def _snapshot(row: TeamScheduleItem) -> dict:
    return {
        "public_id": row.public_id,
        "client_item_key": row.client_item_key,
        "scheduled_date": row.scheduled_date.isoformat(),
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "title": row.title,
        "detail_text": row.detail_text,
        "status": row.status,
        "color_key": row.color_key,
        "assigned_user_id": row.assigned_user_id,
        "source": row.source,
        "revision": row.revision,
        "completed_at": _utc_isoformat(row.completed_at),
        "archived_at": _utc_isoformat(row.archived_at),
    }


def _json(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _record_event(
    db,
    *,
    item_id: int,
    event_type: str,
    actor_user_id: int,
    before: dict | None,
    after: dict,
) -> None:
    db.add(
        TeamScheduleEvent(
            item_id=item_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            from_revision=before.get("revision") if before else None,
            to_revision=int(after["revision"]),
            before_json=_json(before),
            after_json=_json(after) or "{}",
        )
    )


def _names_for_items(db, rows: list[TeamScheduleItem]) -> dict[int, str]:
    ids: set[int] = set()
    for row in rows:
        ids.update(
            value
            for value in (
                row.assigned_user_id,
                row.created_by_user_id,
                row.updated_by_user_id,
            )
            if value is not None
        )
    if not ids:
        return {}
    return {user.id: user.name for user in db.query(User).filter(User.id.in_(ids)).all()}


def _serialize_item(
    row: TeamScheduleItem,
    names: dict[int, str],
    current_user_id: int | None = None,
) -> dict:
    return {
        **_snapshot(row),
        "owner_user_id": schedule_owner_id(row),
        "owner_name": schedule_owner_name(row, names),
        "can_edit": current_user_id == schedule_owner_id(row) if current_user_id is not None else False,
        "assigned_user_name": names.get(row.assigned_user_id) if row.assigned_user_id else None,
        "created_by_user_id": row.created_by_user_id,
        "created_by_name": names.get(row.created_by_user_id),
        "updated_by_user_id": row.updated_by_user_id,
        "updated_by_name": names.get(row.updated_by_user_id),
        "created_at": _utc_isoformat(row.created_at),
        "updated_at": _utc_isoformat(row.updated_at),
    }


def _assert_schedule_owner(row: TeamScheduleItem, current_user: User) -> None:
    if schedule_owner_id(row) != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_SCHEDULE_OWNER_REQUIRED",
        )


def _user_names(db, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    return {user.id: user.name for user in db.query(User).filter(User.id.in_(user_ids)).all()}


def _serialize_work_item(
    row: TeamWorkItem,
    names: dict[int, str],
    current_user_id: int,
    schedule_public_id: str | None = None,
) -> dict:
    return {
        "public_id": row.public_id,
        "owner_user_id": row.owner_user_id,
        "owner_name": names.get(row.owner_user_id),
        "assignee_user_id": row.owner_user_id,
        "assignee_user_name": names.get(row.owner_user_id),
        "requested_by_user_id": row.requested_by_user_id,
        "requested_by_name": names.get(row.requested_by_user_id),
        "assignment_mode": row.assignment_mode,
        "assignment_status": row.assignment_status,
        "can_edit": (
            row.owner_user_id == current_user_id
            if row.assignment_status != ASSIGNMENT_STATUS_PENDING
            else row.requested_by_user_id == current_user_id
        ),
        "can_acknowledge": (
            row.owner_user_id == current_user_id
            and row.assignment_status == ASSIGNMENT_STATUS_PENDING
            and row.acknowledged_at is None
        ),
        "can_accept": (
            row.owner_user_id == current_user_id
            and row.assignment_status == ASSIGNMENT_STATUS_PENDING
        ),
        "can_reject": (
            row.owner_user_id == current_user_id
            and row.assignment_status == ASSIGNMENT_STATUS_PENDING
        ),
        "can_complete": (
            row.owner_user_id == current_user_id
            and row.assignment_status == ASSIGNMENT_STATUS_ACCEPTED
        ),
        "is_unread": is_unread_assignment(
            status=row.assignment_status,
            acknowledged_at=row.acknowledged_at,
            recipient_user_id=row.owner_user_id,
            current_user_id=current_user_id,
        ),
        "badge_color": (
            None
            if row.assignment_mode == ASSIGNMENT_MODE_SELF
            else assignment_badge_color(
                status=row.assignment_status,
                acknowledged_at=row.acknowledged_at,
                recipient_user_id=row.owner_user_id,
                current_user_id=current_user_id,
            )
        ),
        "category": row.category,
        "title": row.title,
        "detail_text": row.detail_text,
        "status": row.status,
        "color_key": row.color_key,
        "due_date": row.due_date.isoformat() if row.due_date else None,
        "roadmap_period": row.roadmap_period,
        "display_order": row.display_order,
        "revision": row.revision,
        "acknowledged_at": _utc_isoformat(row.acknowledged_at),
        "decision_comment": row.decision_comment,
        "decided_at": _utc_isoformat(row.decided_at),
        "completed_at": _utc_isoformat(row.completed_at),
        "schedule_item_public_id": schedule_public_id,
        "archived_at": _utc_isoformat(row.archived_at),
        "created_at": _utc_isoformat(row.created_at),
        "updated_at": _utc_isoformat(row.updated_at),
    }


def _serialize_comment(row: TeamCollaborationComment, names: dict[int, str]) -> dict:
    return {
        "public_id": row.public_id,
        "target_type": row.target_type,
        "author_user_id": row.author_user_id,
        "author_name": names.get(row.author_user_id),
        "body_text": row.body_text,
        "created_at": _utc_isoformat(row.created_at),
    }


def _load_work_item_or_404(db, public_id: str, *, include_archived: bool = False) -> TeamWorkItem:
    query = db.query(TeamWorkItem).filter(TeamWorkItem.public_id == public_id)
    if not include_archived:
        query = query.filter(TeamWorkItem.archived_at.is_(None))
    row = query.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TEAM_WORK_ITEM_NOT_FOUND")
    return row


def _assert_work_owner(row: TeamWorkItem, current_user: User) -> None:
    expected_user_id = (
        row.requested_by_user_id
        if row.assignment_status == ASSIGNMENT_STATUS_PENDING
        else row.owner_user_id
    )
    if expected_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_WORK_ITEM_OWNER_REQUIRED",
        )


def _can_read_work_item(row: TeamWorkItem, current_user_id: int) -> bool:
    if row.assignment_mode == ASSIGNMENT_MODE_SELF:
        return True
    return parties_or_completed_can_read(
        issuer_user_id=row.requested_by_user_id,
        assignee_user_id=row.owner_user_id,
        status=row.assignment_status,
        current_user_id=current_user_id,
    )


def _assert_can_read_work_item(row: TeamWorkItem, current_user_id: int) -> None:
    if not _can_read_work_item(row, current_user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TEAM_WORK_ITEM_NOT_FOUND",
        )


def _linked_schedule_access(db, row: TeamScheduleItem, current_user_id: int) -> bool:
    personal_request = (
        db.query(TeamPersonalRequest)
        .filter(TeamPersonalRequest.schedule_item_id == row.id)
        .first()
    )
    if personal_request is not None:
        if personal_request.request_kind != "WORK":
            return current_user_id in {
                personal_request.sender_user_id,
                personal_request.recipient_user_id,
            }
        return parties_or_completed_can_read(
            issuer_user_id=personal_request.sender_user_id,
            assignee_user_id=personal_request.recipient_user_id,
            status=personal_request.status,
            current_user_id=current_user_id,
        )
    work_item = (
        db.query(TeamWorkItem)
        .filter(TeamWorkItem.schedule_item_id == row.id)
        .first()
    )
    if work_item is not None:
        return _can_read_work_item(work_item, current_user_id)
    if row.source in {"TEAM_REQUEST", "TEAM_WORK_ASSIGNMENT"}:
        # An orphaned private-derived schedule must fail closed instead of
        # publishing copied request/work text to the whole team.
        return current_user_id in {row.created_by_user_id, row.assigned_user_id}
    return True


def _assert_can_read_schedule(db, row: TeamScheduleItem, current_user_id: int) -> None:
    if not _linked_schedule_access(db, row, current_user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TEAM_SCHEDULE_ITEM_NOT_FOUND",
        )


def _is_completed_assignment_schedule(db, schedule_item_id: int) -> bool:
    if (
        db.query(TeamPersonalRequest.id)
        .filter(
            TeamPersonalRequest.schedule_item_id == schedule_item_id,
            TeamPersonalRequest.status == ASSIGNMENT_STATUS_COMPLETED,
        )
        .first()
        is not None
    ):
        return True
    return (
        db.query(TeamWorkItem.id)
        .filter(
            TeamWorkItem.schedule_item_id == schedule_item_id,
            TeamWorkItem.assignment_status == ASSIGNMENT_STATUS_COMPLETED,
        )
        .first()
        is not None
    )


def _complete_linked_assignments(db, schedule_item_id: int, now: datetime) -> None:
    personal = (
        db.query(TeamPersonalRequest)
        .filter(
            TeamPersonalRequest.schedule_item_id == schedule_item_id,
            TeamPersonalRequest.request_kind == "WORK",
            TeamPersonalRequest.status == ASSIGNMENT_STATUS_ACCEPTED,
        )
        .first()
    )
    if personal is not None:
        personal.status = ASSIGNMENT_STATUS_COMPLETED
        personal.completed_at = personal.completed_at or now
        personal.revision += 1
        personal.updated_at = now
    work = (
        db.query(TeamWorkItem)
        .filter(
            TeamWorkItem.schedule_item_id == schedule_item_id,
            TeamWorkItem.assignment_status == ASSIGNMENT_STATUS_ACCEPTED,
        )
        .first()
    )
    if work is not None:
        work.assignment_status = ASSIGNMENT_STATUS_COMPLETED
        work.status = "COMPLETED"
        work.completed_at = work.completed_at or now
        work.revision += 1
        work.updated_at = now


def _load_item_or_404(db, public_id: str, *, include_archived: bool = False) -> TeamScheduleItem:
    query = db.query(TeamScheduleItem).filter(TeamScheduleItem.public_id == public_id)
    if not include_archived:
        query = query.filter(TeamScheduleItem.archived_at.is_(None))
    row = query.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TEAM_SCHEDULE_ITEM_NOT_FOUND")
    return row


def _assert_revision(row: TeamScheduleItem, expected_revision: int) -> None:
    if row.revision != expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TEAM_SCHEDULE_REVISION_CONFLICT",
                "current_revision": row.revision,
            },
        )


def _after_snapshot(before: dict, **changes) -> dict:
    result = dict(before)
    result.update(changes)
    return result


def _serialize_capabilities(member: TeamScheduleMember, surface: str) -> dict:
    capabilities = team_schedule_capabilities(member, surface)
    return {
        "schedule_planning_version": 1,
        "can_read": capabilities.can_read,
        "can_write": capabilities.can_write,
        "surface": capabilities.surface,
        "pc_writes_enabled": capabilities.pc_writes_enabled,
        "mobile_writes_enabled": capabilities.mobile_writes_enabled,
        "pc_write_consent_required": (
            surface in {SURFACE_PC_WEB, SURFACE_SAFETY_WORKBENCH}
            and not bool(member.can_write_pc)
        ),
        "pc_write_consent_version": PC_WRITE_CONSENT_VERSION,
        "pc_write_consented_at": _utc_isoformat(member.pc_write_consented_at),
    }


@router.get("/capabilities")
def get_team_schedule_capabilities(
    db: DbDep,
    current_user: CurrentUserDep,
    surface: str = Query(...),
):
    member = _member_or_403(db, current_user)
    normalized = _surface_or_400(surface)
    return _serialize_capabilities(member, normalized)


@router.post("/capabilities/pc-write-consent")
def consent_to_pc_writes(
    body: TeamSchedulePcWriteConsent,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    member = _member_or_403(db, current_user)
    surface = _surface_or_400(surface_header)
    if surface == SURFACE_MOBILE_WEB:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_SCHEDULE_PC_CONSENT_PC_ONLY",
        )
    if not body.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TEAM_SCHEDULE_PC_CONSENT_REQUIRED",
        )
    if body.consent_version != PC_WRITE_CONSENT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "TEAM_SCHEDULE_PC_CONSENT_VERSION_MISMATCH",
                "current_version": PC_WRITE_CONSENT_VERSION,
            },
        )
    if not member.can_write_pc or member.pc_write_consented_at is None:
        member.can_write_pc = True
        member.pc_write_consented_at = utc_now()
        member.pc_write_consent_version = PC_WRITE_CONSENT_VERSION
        member.updated_at = utc_now()
        db.commit()
        db.refresh(member)
    return _serialize_capabilities(member, surface)


@router.get("/members")
def list_team_schedule_members(db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    rows = (
        db.query(TeamScheduleMember, User)
        .join(User, User.id == TeamScheduleMember.user_id)
        .filter(
            TeamScheduleMember.is_active.is_(True),
            TeamScheduleMember.can_read.is_(True),
            User.is_active.is_(True),
        )
        .order_by(User.name.asc(), User.id.asc())
        .all()
    )
    return {
        "items": [
            {
                "user_id": user.id,
                "name": user.name,
                "login_id": user.login_id,
                "can_write_pc": bool(member.can_write_pc),
                "can_write_mobile": bool(member.can_write_mobile),
                "assignment_mode_from_me": resolve_assignment_mode(
                    current_user.login_id,
                    user.login_id,
                ),
                "can_direct_from_me": can_issue_directive(
                    current_user.login_id,
                    user.login_id,
                ),
            }
            for member, user in rows
        ]
    }


@router.get("/items")
def list_team_schedule_items(
    db: DbDep,
    current_user: CurrentUserDep,
    from_date: date = Query(...),
    to_date: date = Query(...),
    include_archived: bool = Query(False),
    include_completed_in_range: bool = Query(False),
    inspection_only: bool = Query(False),
    mine_only: bool = Query(False),
):
    _member_or_403(db, current_user)
    if to_date < from_date or (to_date - from_date).days > 366:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TEAM_SCHEDULE_DATE_RANGE_INVALID")
    query = db.query(TeamScheduleItem).filter(
        or_(
            and_(TeamScheduleItem.scheduled_date <= to_date,
                 func.coalesce(TeamScheduleItem.due_date, TeamScheduleItem.scheduled_date) >= from_date),
            and_(include_completed_in_range,
                 TeamScheduleItem.completed_at >= datetime.combine(from_date, datetime.min.time()) - timedelta(hours=9),
                 TeamScheduleItem.completed_at < datetime.combine(to_date + timedelta(days=1), datetime.min.time()) - timedelta(hours=9)),
        ),
    )
    if not include_archived:
        query = query.filter(TeamScheduleItem.archived_at.is_(None))
    from app.modules.half_year_reviews.demo import SOURCE as DEMO_SOURCE, KEY as DEMO_KEY, PUBLIC_ID as DEMO_ID, OWNER as DEMO_OWNER
    own_demo = and_(TeamScheduleItem.source == DEMO_SOURCE, TeamScheduleItem.client_item_key == DEMO_KEY, TeamScheduleItem.public_id == DEMO_ID, TeamScheduleItem.assigned_user_id == current_user.id, TeamScheduleItem.created_by_user_id == current_user.id, current_user.id == DEMO_OWNER)
    if inspection_only:
        query = query.filter(or_(TeamScheduleItem.source == INSPECTION_SOURCE, own_demo) if mine_only else TeamScheduleItem.source == INSPECTION_SOURCE)
    else:
        query = query.filter(TeamScheduleItem.source != DEMO_SOURCE)
    if mine_only:
        query = query.filter(or_(
            and_(TeamScheduleItem.source == INSPECTION_SOURCE, TeamScheduleItem.assigned_user_id == current_user.id),
            and_(TeamScheduleItem.source != INSPECTION_SOURCE, TeamScheduleItem.created_by_user_id == current_user.id),
        ))
    rows = [
        row
        for row in query.order_by(
            TeamScheduleItem.scheduled_date.asc(), TeamScheduleItem.id.asc()
        ).all()
        if _linked_schedule_access(db, row, current_user.id)
    ]
    names = _names_for_items(db, rows)
    counts = dict(db.query(TeamCollaborationComment.schedule_item_id, func.count(TeamCollaborationComment.id))
                  .filter(TeamCollaborationComment.schedule_item_id.in_([row.id for row in rows]))
                  .group_by(TeamCollaborationComment.schedule_item_id).all()) if rows else {}
    return {"items": [{**_serialize_item(row, names, current_user.id), "is_demo": row.source == DEMO_SOURCE, "comment_count": counts.get(row.id, 0)} for row in rows]}


@router.get("/inspection-trip-draft")
def get_inspection_trip_draft(
    db: DbDep,
    current_user: CurrentUserDep,
    from_date: date = Query(...),
    to_date: date = Query(...),
):
    _member_or_403(db, current_user)
    if to_date < from_date or (to_date - from_date).days > 30:
        raise HTTPException(status_code=400, detail="INSPECTION_TRIP_DATE_RANGE_INVALID")
    rows = db.query(TeamScheduleItem).filter(
        TeamScheduleItem.source == INSPECTION_SOURCE,
        TeamScheduleItem.assigned_user_id == current_user.id,
        TeamScheduleItem.archived_at.is_(None),
        TeamScheduleItem.status.in_(["PLANNED", "IN_PROGRESS"]),
        TeamScheduleItem.scheduled_date <= to_date,
        func.coalesce(TeamScheduleItem.due_date, TeamScheduleItem.scheduled_date) >= from_date,
    ).order_by(TeamScheduleItem.scheduled_date, TeamScheduleItem.id).all()
    if not rows:
        raise HTTPException(status_code=404, detail="INSPECTION_PLAN_NOT_FOUND_IN_RANGE")
    if any(r.scheduled_date < from_date or (r.due_date or r.scheduled_date) > to_date for r in rows):
        raise HTTPException(status_code=409, detail="INSPECTION_TRIP_RANGE_SPLITS_VISIT")
    return build_trip_application_draft(rows, owner_name=current_user.name, from_date=from_date, to_date=to_date)


@router.get("/item-by-client-key")
def get_team_schedule_item_by_client_key(
    db: DbDep,
    current_user: CurrentUserDep,
    client_item_key: str = Query(..., min_length=1, max_length=200),
):
    _member_or_403(db, current_user)
    row = (
        db.query(TeamScheduleItem)
        .filter(
            TeamScheduleItem.client_item_key == client_item_key,
            TeamScheduleItem.created_by_user_id == current_user.id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="TEAM_SCHEDULE_CLIENT_ITEM_KEY_NOT_FOUND",
        )
    return _serialize_item(row, _names_for_items(db, [row]), current_user.id)


@router.get("/items/{public_id}")
def get_team_schedule_item(public_id: str, db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    row = _load_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_schedule(db, row, current_user.id)
    return _serialize_item(row, _names_for_items(db, [row]), current_user.id)


def _same_create_payload(row: TeamScheduleItem, body: TeamScheduleCreate, current_user_id: int) -> bool:
    return (
        row.archived_at is None
        and row.created_by_user_id == current_user_id
        and row.scheduled_date == body.scheduled_date
        and row.due_date == body.due_date
        and row.title == body.title.strip()
        and row.detail_text == _clean_text(body.detail_text)
        and row.status == body.status
        and row.color_key == body.color_key
        and row.assigned_user_id == current_user_id
    )


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_team_schedule_item(
    body: TeamScheduleCreate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _, surface = _require_write(db, current_user, surface_header)
    if body.assigned_user_id not in (None, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_SCHEDULE_SELF_ASSIGNMENT_REQUIRED",
        )
    if body.due_date is not None and body.due_date < body.scheduled_date:
        raise HTTPException(status_code=400, detail="TEAM_SCHEDULE_DUE_DATE_INVALID")
    title = body.title.strip()
    detail = _clean_text(body.detail_text)
    client_key = _clean_text(body.client_item_key)

    if client_key:
        existing = db.query(TeamScheduleItem).filter(TeamScheduleItem.client_item_key == client_key).first()
        if existing is not None:
            if not _same_create_payload(existing, body, current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="TEAM_SCHEDULE_CLIENT_ITEM_KEY_CONFLICT",
                )
            payload = _serialize_item(existing, _names_for_items(db, [existing]), current_user.id)
            payload["idempotent_replay"] = True
            return payload

    now = utc_now()
    row = TeamScheduleItem(
        public_id=str(uuid4()),
        client_item_key=client_key,
        scheduled_date=body.scheduled_date,
        due_date=body.due_date,
        title=title,
        detail_text=detail,
        status=body.status,
        color_key=body.color_key,
        assigned_user_id=current_user.id,
        source=_SOURCE_BY_SURFACE[surface],
        revision=1,
        created_by_user_id=current_user.id,
        updated_by_user_id=current_user.id,
        completed_at=now if body.status == "COMPLETED" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    try:
        db.flush()
        _record_event(
            db,
            item_id=row.id,
            event_type="CREATED",
            actor_user_id=current_user.id,
            before=None,
            after=_snapshot(row),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if client_key:
            existing = db.query(TeamScheduleItem).filter(TeamScheduleItem.client_item_key == client_key).first()
            if existing is not None and _same_create_payload(existing, body, current_user.id):
                payload = _serialize_item(existing, _names_for_items(db, [existing]), current_user.id)
                payload["idempotent_replay"] = True
                return payload
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TEAM_SCHEDULE_CREATE_CONFLICT",
        ) from exc
    db.refresh(row)
    payload = _serialize_item(row, _names_for_items(db, [row]), current_user.id)
    payload["idempotent_replay"] = False
    return payload


@router.put("/items/{public_id}")
def update_team_schedule_item(
    public_id: str,
    body: TeamScheduleUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_item_or_404(db, public_id)
    _assert_schedule_owner(row, current_user)
    if body.assigned_user_id not in (None, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_SCHEDULE_SELF_ASSIGNMENT_REQUIRED",
        )
    _assert_revision(row, body.revision)
    if (
        row.status == "COMPLETED"
        and body.status != "COMPLETED"
        and (row.source == INSPECTION_SOURCE or _is_completed_assignment_schedule(db, row.id))
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TEAM_ASSIGNMENT_COMPLETION_IMMUTABLE",
        )
    before = _snapshot(row)
    now = utc_now()
    completed_at = (row.completed_at or now) if body.status == "COMPLETED" else None
    due_date = body.due_date if "due_date" in body.model_fields_set else row.due_date
    if due_date is not None and due_date < body.scheduled_date:
        raise HTTPException(status_code=400, detail="TEAM_SCHEDULE_DUE_DATE_INVALID")
    if row.source == INSPECTION_SOURCE and (row.client_item_key or "").startswith("inspection:202611:"):
        if not date(2026, 11, 2) <= body.scheduled_date <= (due_date or body.scheduled_date) <= date(2026, 12, 31):
            raise HTTPException(status_code=400, detail="INSPECTION_PLAN_PERIOD_REQUIRED")
    color_key = body.color_key if body.color_key is not None else row.color_key
    values = {
        "scheduled_date": body.scheduled_date,
        "due_date": due_date,
        "title": body.title.strip(),
        "detail_text": _clean_text(body.detail_text),
        "status": body.status,
        "color_key": color_key,
        "assigned_user_id": current_user.id,
        "updated_by_user_id": current_user.id,
        "updated_at": now,
        "completed_at": completed_at,
        "revision": body.revision + 1,
    }
    result = db.execute(
        update(TeamScheduleItem)
        .where(
            TeamScheduleItem.id == row.id,
            TeamScheduleItem.revision == body.revision,
            TeamScheduleItem.archived_at.is_(None),
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.rollback()
        current = _load_item_or_404(db, public_id, include_archived=True)
        _assert_revision(current, body.revision)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TEAM_SCHEDULE_UPDATE_CONFLICT")
    after = _after_snapshot(
        before,
        scheduled_date=body.scheduled_date.isoformat(),
        due_date=due_date.isoformat() if due_date else None,
        title=body.title.strip(),
        detail_text=_clean_text(body.detail_text),
        status=body.status,
        color_key=color_key,
        assigned_user_id=current_user.id,
        revision=body.revision + 1,
        completed_at=completed_at.isoformat() if completed_at else None,
    )
    _record_event(
        db,
        item_id=row.id,
        event_type="UPDATED",
        actor_user_id=current_user.id,
        before=before,
        after=after,
    )
    if body.status == "COMPLETED":
        _complete_linked_assignments(db, row.id, now)
    from .inspection_schedule_sync import synchronize
    db.flush()
    synchronize(db, row, before, current_user, now, _snapshot, _after_snapshot, _record_event)
    db.commit()
    updated = _load_item_or_404(db, public_id)
    return _serialize_item(updated, _names_for_items(db, [updated]), current_user.id)


@router.post("/items/{public_id}/complete")
def complete_team_schedule_item(
    public_id: str,
    body: TeamScheduleTransition,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_item_or_404(db, public_id)
    if row.source == INSPECTION_SOURCE:
        _assert_schedule_owner(row, current_user)
    _assert_revision(row, body.revision)
    if row.status == "COMPLETED":
        return _serialize_item(row, _names_for_items(db, [row]), current_user.id)
    before = _snapshot(row)
    now = utc_now()
    result = db.execute(
        update(TeamScheduleItem)
        .where(
            TeamScheduleItem.id == row.id,
            TeamScheduleItem.revision == body.revision,
            TeamScheduleItem.archived_at.is_(None),
        )
        .values(
            status="COMPLETED",
            completed_at=row.completed_at or now,
            updated_by_user_id=current_user.id,
            updated_at=now,
            revision=body.revision + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        current = _load_item_or_404(db, public_id, include_archived=True)
        _assert_revision(current, body.revision)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TEAM_SCHEDULE_UPDATE_CONFLICT")
    completed_at = row.completed_at or now
    after = _after_snapshot(
        before,
        status="COMPLETED",
        completed_at=completed_at.isoformat(),
        revision=body.revision + 1,
    )
    _record_event(
        db,
        item_id=row.id,
        event_type="COMPLETED",
        actor_user_id=current_user.id,
        before=before,
        after=after,
    )
    _complete_linked_assignments(db, row.id, now)
    db.commit()
    updated = _load_item_or_404(db, public_id)
    return _serialize_item(updated, _names_for_items(db, [updated]), current_user.id)


@router.post("/items/{public_id}/archive")
def archive_team_schedule_item(
    public_id: str,
    body: TeamScheduleTransition,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_item_or_404(db, public_id)
    _assert_schedule_owner(row, current_user)
    _assert_revision(row, body.revision)
    before = _snapshot(row)
    now = utc_now()
    result = db.execute(
        update(TeamScheduleItem)
        .where(
            TeamScheduleItem.id == row.id,
            TeamScheduleItem.revision == body.revision,
            TeamScheduleItem.archived_at.is_(None),
        )
        .values(
            archived_at=now,
            updated_by_user_id=current_user.id,
            updated_at=now,
            revision=body.revision + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        current = _load_item_or_404(db, public_id, include_archived=True)
        _assert_revision(current, body.revision)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="TEAM_SCHEDULE_UPDATE_CONFLICT")
    after = _after_snapshot(
        before,
        archived_at=now.isoformat(),
        revision=body.revision + 1,
    )
    _record_event(
        db,
        item_id=row.id,
        event_type="ARCHIVED",
        actor_user_id=current_user.id,
        before=before,
        after=after,
    )
    db.commit()
    archived = _load_item_or_404(db, public_id, include_archived=True)
    return _serialize_item(archived, _names_for_items(db, [archived]), current_user.id)


@router.get("/items/{public_id}/events")
def list_team_schedule_events(public_id: str, db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    row = _load_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_schedule(db, row, current_user.id)
    events = (
        db.query(TeamScheduleEvent, User)
        .join(User, User.id == TeamScheduleEvent.actor_user_id)
        .filter(TeamScheduleEvent.item_id == row.id)
        .order_by(TeamScheduleEvent.id.asc())
        .all()
    )
    return {
        "items": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "actor_user_id": event.actor_user_id,
                "actor_name": actor.name,
                "from_revision": event.from_revision,
                "to_revision": event.to_revision,
                "before": json.loads(event.before_json) if event.before_json else None,
                "after": json.loads(event.after_json),
                "created_at": _utc_isoformat(event.created_at),
            }
            for event, actor in events
        ]
    }


@router.post("/workbench-updates/events", status_code=status.HTTP_201_CREATED)
def create_workbench_update_event(
    body: WorkbenchUpdateEventCreate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _member_or_403(db, current_user)
    if _surface_or_400(surface_header) != SURFACE_SAFETY_WORKBENCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WORKBENCH_UPDATE_CLIENT_SURFACE_REQUIRED",
        )
    # A failed availability check has no target release yet. Record it against
    # the installed version so the team history can show the failure.
    if (_version_tuple(body.target_version) < _version_tuple(body.from_version)
            or (body.event_status != "FAILED"
                and _version_tuple(body.target_version) == _version_tuple(body.from_version))):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WORKBENCH_UPDATE_VERSION_RANGE_INVALID",
        )
    if body.event_status != "FAILED" and body.error_code is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WORKBENCH_UPDATE_ERROR_CODE_INVALID",
        )

    existing = (
        db.query(WorkbenchUpdateEvent)
        .filter(WorkbenchUpdateEvent.client_event_id == body.client_event_id)
        .first()
    )
    if existing is not None:
        exact_replay = (
            existing.actor_user_id == current_user.id
            and existing.from_version == body.from_version
            and existing.target_version == body.target_version
            and existing.product_version == body.product_version
            and existing.release_notes == body.release_notes
            and existing.event_status == body.event_status
            and existing.error_code == body.error_code
        )
        if not exact_replay:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="WORKBENCH_UPDATE_EVENT_CONFLICT",
            )
        return _serialize_workbench_update_event(existing, current_user)

    occurred_at = body.occurred_at
    if occurred_at.tzinfo is not None:
        occurred_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
    row = WorkbenchUpdateEvent(
        client_event_id=body.client_event_id,
        actor_user_id=current_user.id,
        from_version=body.from_version,
        target_version=body.target_version,
        product_version=body.product_version,
        release_notes=body.release_notes,
        event_status=body.event_status,
        error_code=body.error_code,
        client_occurred_at=occurred_at,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        replay = (
            db.query(WorkbenchUpdateEvent)
            .filter(WorkbenchUpdateEvent.client_event_id == body.client_event_id)
            .first()
        )
        if replay is None or replay.actor_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="WORKBENCH_UPDATE_EVENT_CONFLICT",
            )
        return _serialize_workbench_update_event(replay, current_user)
    db.refresh(row)
    return _serialize_workbench_update_event(row, current_user)


@router.get("/workbench-updates/history")
def list_workbench_update_history(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(default=100, ge=1, le=500),
):
    _member_or_403(db, current_user)
    rows = (
        db.query(WorkbenchUpdateEvent, User)
        .join(User, User.id == WorkbenchUpdateEvent.actor_user_id)
        .order_by(WorkbenchUpdateEvent.id.desc())
        .limit(limit)
        .all()
    )
    return {"items": [_serialize_workbench_update_event(row, actor) for row, actor in rows]}


def _list_comments(db, *, schedule_item_id: int | None = None, work_item_id: int | None = None) -> list:
    query = db.query(TeamCollaborationComment)
    if schedule_item_id is not None:
        query = query.filter(
            TeamCollaborationComment.target_type == "SCHEDULE",
            TeamCollaborationComment.schedule_item_id == schedule_item_id,
        )
    elif work_item_id is not None:
        query = query.filter(
            TeamCollaborationComment.target_type == "WORK_ITEM",
            TeamCollaborationComment.work_item_id == work_item_id,
        )
    else:
        raise ValueError("a comment target is required")
    return query.order_by(TeamCollaborationComment.id.asc()).all()


@router.get("/items/{public_id}/comments")
def list_team_schedule_comments(public_id: str, db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    row = _load_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_schedule(db, row, current_user.id)
    comments = _list_comments(db, schedule_item_id=row.id)
    names = _user_names(db, {comment.author_user_id for comment in comments})
    return {"items": [_serialize_comment(comment, names) for comment in comments]}


@router.post("/items/{public_id}/comments", status_code=status.HTTP_201_CREATED)
def create_team_schedule_comment(
    public_id: str,
    body: TeamCommentCreate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_schedule(db, row, current_user.id)
    comment = TeamCollaborationComment(
        public_id=str(uuid4()),
        target_type="SCHEDULE",
        schedule_item_id=row.id,
        work_item_id=None,
        author_user_id=current_user.id,
        body_text=body.body_text.strip(),
        created_at=utc_now(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _serialize_comment(comment, {current_user.id: current_user.name})


def _team_member_user_or_400(db, user_id: int) -> User:
    user = (
        db.query(User)
        .join(TeamScheduleMember, TeamScheduleMember.user_id == User.id)
        .filter(
            User.id == user_id,
            User.is_active.is_(True),
            TeamScheduleMember.is_active.is_(True),
            TeamScheduleMember.can_read.is_(True),
        )
        .first()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TEAM_WORK_ASSIGNEE_NOT_MEMBER",
        )
    return user


def _work_schedule_public_ids(db, rows: list[TeamWorkItem]) -> dict[int, str]:
    schedule_ids = {row.schedule_item_id for row in rows if row.schedule_item_id is not None}
    if not schedule_ids:
        return {}
    return {
        row.id: row.public_id
        for row in db.query(TeamScheduleItem).filter(TeamScheduleItem.id.in_(schedule_ids)).all()
    }


def _serialize_work_rows(db, rows: list[TeamWorkItem], current_user_id: int) -> list[dict]:
    names = _user_names(
        db,
        {
            user_id
            for row in rows
            for user_id in (row.owner_user_id, row.requested_by_user_id)
        },
    )
    schedules = _work_schedule_public_ids(db, rows)
    return [
        _serialize_work_item(
            row,
            names,
            current_user_id,
            schedules.get(row.schedule_item_id),
        )
        for row in rows
    ]


def _work_revision_conflict(row: TeamWorkItem) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "TEAM_WORK_REVISION_CONFLICT", "current_revision": row.revision},
    )


def _assert_work_recipient(row: TeamWorkItem, current_user: User) -> None:
    if row.owner_user_id == current_user.id:
        return
    if row.requested_by_user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="TEAM_WORK_ASSIGNEE_REQUIRED",
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TEAM_WORK_ITEM_NOT_FOUND")


def _new_schedule_for_work_item(
    row: TeamWorkItem,
    *,
    scheduled_date: date,
    actor_user_id: int,
    decision_comment: str | None,
    now: datetime,
) -> TeamScheduleItem:
    detail_text = row.detail_text
    if decision_comment:
        detail_text = (
            f"{detail_text}\n\n수락 코멘트: {decision_comment}"
            if detail_text
            else f"수락 코멘트: {decision_comment}"
        )
    return TeamScheduleItem(
        public_id=str(uuid4()),
        client_item_key=f"team-work:{row.public_id}",
        scheduled_date=scheduled_date,
        title=row.title,
        detail_text=detail_text,
        status="PLANNED",
        color_key=row.color_key,
        assigned_user_id=row.owner_user_id,
        source="TEAM_WORK_ASSIGNMENT",
        revision=1,
        created_by_user_id=actor_user_id,
        updated_by_user_id=actor_user_id,
        completed_at=None,
        archived_at=None,
        created_at=now,
        updated_at=now,
    )


@router.get("/work-items")
def list_team_work_items(
    db: DbDep,
    current_user: CurrentUserDep,
    owner_user_id: int | None = Query(default=None, ge=1),
    category: str | None = Query(default=None),
    include_archived: bool = Query(False),
):
    _member_or_403(db, current_user)
    if category is not None and category not in {"IDEA", "ROADMAP", "CURRENT_WORK"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TEAM_WORK_CATEGORY_INVALID")
    query = db.query(TeamWorkItem)
    if owner_user_id is not None:
        query = query.filter(TeamWorkItem.owner_user_id == owner_user_id)
    if category is not None:
        query = query.filter(TeamWorkItem.category == category)
    if not include_archived:
        query = query.filter(TeamWorkItem.archived_at.is_(None))
    rows = [
        row
        for row in query.order_by(
            TeamWorkItem.updated_at.desc(),
            TeamWorkItem.id.desc(),
        ).limit(2_000).all()
        if _can_read_work_item(row, current_user.id)
    ]
    rows.sort(
        key=lambda row: (
            not is_unread_assignment(
                status=row.assignment_status,
                acknowledged_at=row.acknowledged_at,
                recipient_user_id=row.owner_user_id,
                current_user_id=current_user.id,
            ),
            row.owner_user_id,
            row.category,
            row.display_order,
            -row.id,
        )
    )
    return {"items": _serialize_work_rows(db, rows, current_user.id)}


@router.get("/assignment-summary")
def get_team_assignment_summary(db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    received = (
        db.query(TeamWorkItem)
        .filter(
            TeamWorkItem.owner_user_id == current_user.id,
            TeamWorkItem.assignment_mode != ASSIGNMENT_MODE_SELF,
            TeamWorkItem.archived_at.is_(None),
        )
        .all()
    )
    unread = [
        row
        for row in received
        if is_unread_assignment(
            status=row.assignment_status,
            acknowledged_at=row.acknowledged_at,
            recipient_user_id=row.owner_user_id,
            current_user_id=current_user.id,
        )
    ]
    unread_by_category = {
        category: sum(1 for row in unread if row.category == category)
        for category in ("IDEA", "ROADMAP", "CURRENT_WORK")
    }
    accepted_received = sum(
        1 for row in received if row.assignment_status == ASSIGNMENT_STATUS_ACCEPTED
    )
    return {
        "unread_received": len(unread),
        "accepted_received": accepted_received,
        "unread_by_category": unread_by_category,
        "menu_badge_count": len(unread),
        "menu_badge_color": "RED" if unread else None,
    }


@router.get("/work-items/weekly")
def list_weekly_team_work(
    db: DbDep,
    current_user: CurrentUserDep,
    week_start: date = Query(...),
    include_unscheduled: bool = Query(True),
):
    _member_or_403(db, current_user)
    normalized_start = week_start - timedelta(days=week_start.weekday())
    week_end = normalized_start + timedelta(days=6)
    rows = [
        row
        for row in (
        db.query(TeamWorkItem)
        .filter(
            TeamWorkItem.due_date >= normalized_start,
            TeamWorkItem.due_date <= week_end,
            TeamWorkItem.archived_at.is_(None),
        )
        .order_by(TeamWorkItem.due_date.asc(), TeamWorkItem.id.asc())
        .limit(2_000)
        .all()
        )
        if _can_read_work_item(row, current_user.id)
    ]
    unscheduled_rows = []
    if include_unscheduled:
        unscheduled_rows = [
            row
            for row in (
                db.query(TeamWorkItem)
                .filter(
                    TeamWorkItem.due_date.is_(None),
                    TeamWorkItem.archived_at.is_(None),
                )
                .order_by(TeamWorkItem.updated_at.desc(), TeamWorkItem.id.desc())
                .limit(2_000)
                .all()
            )
            if _can_read_work_item(row, current_user.id)
        ]
    items = _serialize_work_rows(db, rows, current_user.id)
    unscheduled = _serialize_work_rows(db, unscheduled_rows, current_user.id)
    completed_request_rows = (
        db.query(TeamPersonalRequest)
        .filter(
            TeamPersonalRequest.request_kind == "WORK",
            TeamPersonalRequest.status == ASSIGNMENT_STATUS_COMPLETED,
            TeamPersonalRequest.proposed_date >= normalized_start,
            TeamPersonalRequest.proposed_date <= week_end,
        )
        .order_by(TeamPersonalRequest.proposed_date.asc(), TeamPersonalRequest.id.asc())
        .limit(2_000)
        .all()
    )
    request_names = _user_names(
        db,
        {
            user_id
            for request in completed_request_rows
            for user_id in (request.sender_user_id, request.recipient_user_id)
        },
    )
    completed_requests = [
        {
            "public_id": request.public_id,
            "request_kind": request.request_kind,
            "sender_user_id": request.sender_user_id,
            "sender_name": request_names.get(request.sender_user_id),
            "recipient_user_id": request.recipient_user_id,
            "recipient_name": request_names.get(request.recipient_user_id),
            "body_text": request.body_text,
            "scheduled_date": request.proposed_date.isoformat() if request.proposed_date else None,
            "status": request.status,
            "completed_at": _utc_isoformat(request.completed_at),
        }
        for request in completed_request_rows
    ]
    copy_lines = [
        f"{item['due_date']} [{item['category']}] "
        f"{item['assignee_user_name'] or item['assignee_user_id']} - {item['title']} "
        f"({item['assignment_status']})"
        for item in items
    ]
    copy_lines.extend(
        f"{item['scheduled_date']} [요청업무] "
        f"{item['recipient_name'] or item['recipient_user_id']} - "
        f"{next((line.strip() for line in item['body_text'].splitlines() if line.strip()), '')} (완료)"
        for item in completed_requests
    )
    return {
        "week_start": normalized_start.isoformat(),
        "week_end": week_end.isoformat(),
        "items": items,
        "unscheduled": unscheduled,
        "completed_requests": completed_requests,
        "copy_text": "\n".join(copy_lines),
    }


@router.post("/work-items", status_code=status.HTTP_201_CREATED)
def create_team_work_item(
    body: TeamWorkItemCreate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    assignee = _team_member_user_or_400(db, body.assignee_user_id or current_user.id)
    mode = resolve_assignment_mode(current_user.login_id, assignee.login_id)
    now = utc_now()
    assignment_status = (
        ASSIGNMENT_STATUS_ACCEPTED
        if mode == ASSIGNMENT_MODE_SELF
        else ASSIGNMENT_STATUS_PENDING
    )
    row = TeamWorkItem(
        public_id=str(uuid4()),
        owner_user_id=assignee.id,
        requested_by_user_id=current_user.id,
        assignment_mode=mode,
        assignment_status=assignment_status,
        category=body.category,
        title=body.title.strip(),
        detail_text=_clean_text(body.detail_text),
        status=body.status if mode == ASSIGNMENT_MODE_SELF else "PLANNED",
        color_key=body.color_key,
        due_date=body.due_date,
        roadmap_period=body.roadmap_period,
        display_order=body.display_order,
        revision=1,
        acknowledged_at=now if mode == ASSIGNMENT_MODE_SELF else None,
        decision_comment=None,
        decided_at=now if mode == ASSIGNMENT_MODE_SELF else None,
        completed_at=None,
        schedule_item_id=None,
        created_at=now,
        updated_at=now,
    )
    if row.status == "COMPLETED":
        row.assignment_status = ASSIGNMENT_STATUS_COMPLETED
        row.completed_at = now
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.get("/work-items/{public_id}")
def get_team_work_item(public_id: str, db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    row = _load_work_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_work_item(row, current_user.id)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.put("/work-items/{public_id}")
def update_team_work_item(
    public_id: str,
    body: TeamWorkItemUpdate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_can_read_work_item(row, current_user.id)
    _assert_work_owner(row, current_user)
    if body.assignee_user_id not in (None, row.owner_user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TEAM_WORK_ASSIGNEE_IMMUTABLE",
        )
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    if (
        row.assignment_status == ASSIGNMENT_STATUS_PENDING
        and row.acknowledged_at is not None
    ):
        raise HTTPException(status_code=409, detail="TEAM_WORK_ITEM_NOT_EDITABLE")
    if (
        row.assignment_mode != ASSIGNMENT_MODE_SELF
        and row.assignment_status == ASSIGNMENT_STATUS_PENDING
        and body.status != "PLANNED"
    ):
        raise HTTPException(status_code=409, detail="TEAM_WORK_ACCEPT_REQUIRED")
    if row.assignment_status == ASSIGNMENT_STATUS_REJECTED:
        raise HTTPException(status_code=409, detail="TEAM_WORK_ASSIGNMENT_REJECTED")
    if (
        row.assignment_status == ASSIGNMENT_STATUS_COMPLETED
        and body.status != "COMPLETED"
    ):
        raise HTTPException(status_code=409, detail="TEAM_WORK_COMPLETION_IMMUTABLE")
    now = utc_now()
    assignment_status = row.assignment_status
    completed_at = row.completed_at
    if body.status == "COMPLETED":
        assignment_status = ASSIGNMENT_STATUS_COMPLETED
        completed_at = completed_at or now
    result = db.execute(
        update(TeamWorkItem)
        .where(
            TeamWorkItem.id == row.id,
            TeamWorkItem.revision == body.revision,
            TeamWorkItem.archived_at.is_(None),
        )
        .values(
            category=body.category,
            title=body.title.strip(),
            detail_text=_clean_text(body.detail_text),
            status=body.status,
            color_key=body.color_key,
            due_date=body.due_date,
            roadmap_period=body.roadmap_period if "roadmap_period" in body.model_fields_set else row.roadmap_period,
            display_order=body.display_order,
            assignment_status=assignment_status,
            completed_at=completed_at,
            revision=body.revision + 1,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise _work_revision_conflict(_load_work_item_or_404(db, public_id, include_archived=True))
    if body.status == "COMPLETED" and row.schedule_item_id is not None:
        schedule = _load_item_or_404(db, _work_schedule_public_ids(db, [row])[row.schedule_item_id])
        if schedule.status != "COMPLETED":
            before = _snapshot(schedule)
            schedule.status = "COMPLETED"
            schedule.completed_at = schedule.completed_at or now
            schedule.updated_by_user_id = current_user.id
            schedule.updated_at = now
            schedule.revision += 1
            _record_event(
                db,
                item_id=schedule.id,
                event_type="COMPLETED",
                actor_user_id=current_user.id,
                before=before,
                after=_snapshot(schedule),
            )
    db.commit()
    updated = _load_work_item_or_404(db, public_id)
    return _serialize_work_rows(db, [updated], current_user.id)[0]


@router.post("/work-items/{public_id}/acknowledge")
def acknowledge_team_work_item(
    public_id: str,
    body: TeamWorkAssignmentAcknowledge,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_work_recipient(row, current_user)
    if row.assignment_status != ASSIGNMENT_STATUS_PENDING:
        raise HTTPException(status_code=409, detail="TEAM_WORK_ASSIGNMENT_ALREADY_DECIDED")
    if row.acknowledged_at is not None and body.revision in {row.revision, row.revision - 1}:
        return _serialize_work_rows(db, [row], current_user.id)[0]
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    row.acknowledged_at = utc_now()
    row.updated_at = row.acknowledged_at
    row.revision += 1
    db.commit()
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.post("/work-items/{public_id}/accept")
def accept_team_work_item(
    public_id: str,
    body: TeamWorkAssignmentDecision,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_work_recipient(row, current_user)
    if row.assignment_status == ASSIGNMENT_STATUS_ACCEPTED and body.revision in {row.revision, row.revision - 1}:
        return _serialize_work_rows(db, [row], current_user.id)[0]
    if row.assignment_status != ASSIGNMENT_STATUS_PENDING:
        raise HTTPException(status_code=409, detail="TEAM_WORK_ASSIGNMENT_ALREADY_DECIDED")
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    scheduled_date = body.scheduled_date or row.due_date
    if scheduled_date is None:
        raise HTTPException(status_code=400, detail="TEAM_WORK_SCHEDULED_DATE_REQUIRED")
    now = utc_now()
    schedule = _new_schedule_for_work_item(
        row,
        scheduled_date=scheduled_date,
        actor_user_id=current_user.id,
        decision_comment=body.decision_comment,
        now=now,
    )
    try:
        db.add(schedule)
        db.flush()
        row.assignment_status = ASSIGNMENT_STATUS_ACCEPTED
        row.acknowledged_at = row.acknowledged_at or now
        row.decision_comment = body.decision_comment
        row.decided_at = now
        row.due_date = scheduled_date
        row.schedule_item_id = schedule.id
        row.revision += 1
        row.updated_at = now
        _record_event(
            db,
            item_id=schedule.id,
            event_type="CREATED_FROM_WORK_ASSIGNMENT",
            actor_user_id=current_user.id,
            before=None,
            after=_snapshot(schedule),
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        current = _load_work_item_or_404(db, public_id)
        if current.assignment_status == ASSIGNMENT_STATUS_ACCEPTED and current.schedule_item_id:
            return _serialize_work_rows(db, [current], current_user.id)[0]
        raise HTTPException(status_code=409, detail="TEAM_WORK_SCHEDULE_CONFLICT") from exc
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.post("/work-items/{public_id}/reject")
def reject_team_work_item(
    public_id: str,
    body: TeamWorkAssignmentDecision,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_work_recipient(row, current_user)
    if row.assignment_status == ASSIGNMENT_STATUS_REJECTED and body.revision in {row.revision, row.revision - 1}:
        return _serialize_work_rows(db, [row], current_user.id)[0]
    if row.assignment_status != ASSIGNMENT_STATUS_PENDING:
        raise HTTPException(status_code=409, detail="TEAM_WORK_ASSIGNMENT_ALREADY_DECIDED")
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    if not body.decision_comment:
        raise HTTPException(status_code=400, detail="TEAM_WORK_REJECTION_COMMENT_REQUIRED")
    now = utc_now()
    row.assignment_status = ASSIGNMENT_STATUS_REJECTED
    row.acknowledged_at = row.acknowledged_at or now
    row.decision_comment = body.decision_comment
    row.decided_at = now
    row.revision += 1
    row.updated_at = now
    db.commit()
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.post("/work-items/{public_id}/complete")
def complete_team_work_item(
    public_id: str,
    body: TeamScheduleTransition,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_can_read_work_item(row, current_user.id)
    if row.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="TEAM_WORK_ASSIGNEE_REQUIRED")
    if row.assignment_status == ASSIGNMENT_STATUS_COMPLETED:
        return _serialize_work_rows(db, [row], current_user.id)[0]
    if row.assignment_status not in {ASSIGNMENT_STATUS_ACCEPTED}:
        raise HTTPException(status_code=409, detail="TEAM_WORK_ACCEPT_REQUIRED")
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    now = utc_now()
    row.assignment_status = ASSIGNMENT_STATUS_COMPLETED
    row.status = "COMPLETED"
    row.completed_at = row.completed_at or now
    row.revision += 1
    row.updated_at = now
    if row.schedule_item_id is not None:
        schedule = db.query(TeamScheduleItem).filter(TeamScheduleItem.id == row.schedule_item_id).one()
        if schedule.status != "COMPLETED":
            before = _snapshot(schedule)
            schedule.status = "COMPLETED"
            schedule.completed_at = schedule.completed_at or now
            schedule.updated_by_user_id = current_user.id
            schedule.updated_at = now
            schedule.revision += 1
            _record_event(
                db,
                item_id=schedule.id,
                event_type="COMPLETED",
                actor_user_id=current_user.id,
                before=before,
                after=_snapshot(schedule),
            )
    db.commit()
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.post("/work-items/{public_id}/archive")
def archive_team_work_item(
    public_id: str,
    body: TeamScheduleTransition,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_can_read_work_item(row, current_user.id)
    _assert_work_owner(row, current_user)
    if (
        row.assignment_status == ASSIGNMENT_STATUS_PENDING
        and row.acknowledged_at is not None
    ):
        raise HTTPException(status_code=409, detail="TEAM_WORK_ITEM_NOT_EDITABLE")
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    row.archived_at = utc_now()
    row.updated_at = row.archived_at
    row.revision += 1
    db.commit()
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]


@router.get("/work-items/{public_id}/comments")
def list_team_work_comments(public_id: str, db: DbDep, current_user: CurrentUserDep):
    _member_or_403(db, current_user)
    row = _load_work_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_work_item(row, current_user.id)
    comments = _list_comments(db, work_item_id=row.id)
    names = _user_names(db, {comment.author_user_id for comment in comments})
    return {"items": [_serialize_comment(comment, names) for comment in comments]}


@router.post("/work-items/{public_id}/comments", status_code=status.HTTP_201_CREATED)
def create_team_work_comment(
    public_id: str,
    body: TeamCommentCreate,
    db: DbDep,
    current_user: CurrentUserDep,
    surface_header: SurfaceHeader = None,
):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id, include_archived=True)
    _assert_can_read_work_item(row, current_user.id)
    comment = TeamCollaborationComment(
        public_id=str(uuid4()),
        target_type="WORK_ITEM",
        schedule_item_id=None,
        work_item_id=row.id,
        author_user_id=current_user.id,
        body_text=body.body_text.strip(),
        created_at=utc_now(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _serialize_comment(comment, {current_user.id: current_user.name})


@router.post("/work-items/{public_id}/schedule")
def schedule_roadmap_item(public_id: str, body: TeamWorkAssignmentDecision,
                          db: DbDep, current_user: CurrentUserDep, surface_header: SurfaceHeader = None):
    _require_write(db, current_user, surface_header)
    row = _load_work_item_or_404(db, public_id)
    _assert_work_owner(row, current_user)
    if row.category != "ROADMAP" or row.assignment_mode != "SELF" or row.status == "COMPLETED":
        raise HTTPException(status_code=409, detail="TEAM_ROADMAP_NOT_SCHEDULABLE")
    if row.schedule_item_id is not None:
        return _serialize_work_rows(db, [row], current_user.id)[0]
    if row.revision != body.revision:
        raise _work_revision_conflict(row)
    if body.scheduled_date is None:
        raise HTTPException(status_code=400, detail="TEAM_WORK_SCHEDULED_DATE_REQUIRED")
    now = utc_now()
    schedule = _new_schedule_for_work_item(row, scheduled_date=body.scheduled_date,
                  actor_user_id=current_user.id, decision_comment=None, now=now)
    try:
        db.add(schedule)
        db.flush()
        result = db.execute(update(TeamWorkItem).where(TeamWorkItem.id == row.id,
                    TeamWorkItem.revision == body.revision, TeamWorkItem.schedule_item_id.is_(None))
                    .values(schedule_item_id=schedule.id, due_date=body.scheduled_date,
                            revision=body.revision + 1, updated_at=now))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="TEAM_WORK_SCHEDULE_CONFLICT")
        _record_event(db, item_id=schedule.id, event_type="CREATED_FROM_ROADMAP",
                      actor_user_id=current_user.id, before=None, after=_snapshot(schedule))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="TEAM_WORK_SCHEDULE_CONFLICT") from exc
    db.refresh(row)
    return _serialize_work_rows(db, [row], current_user.id)[0]
