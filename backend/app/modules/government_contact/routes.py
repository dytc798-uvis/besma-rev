"""A site-scoped, two-way HQ safety correspondence stream."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import DbDep
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.document_explorer.government_access import is_government_site_record
from app.modules.documents.active_site_scope import in_active_scope, today_kst
from app.modules.government_contact.models import GovernmentContactMessage
from app.modules.sites.models import Site
from app.modules.users.models import User

router = APIRouter(prefix="/government-contact", tags=["government-contact"])
HQ_ROLES = {Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN}
SITE_ROLES = {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}


class MessageBody(BaseModel):
    site_id: int | None = None
    body: str = Field(min_length=1, max_length=4000)


def _actor_side(user: User) -> str:
    if user.role in HQ_ROLES:
        return "HQ"
    if user.role in SITE_ROLES:
        return "SITE"
    raise HTTPException(403, "Not allowed")


def _authorized_site(db: DbDep, user: User, site_id: int | None) -> tuple[Site, str]:
    side = _actor_side(user)
    selected_id = site_id if side == "HQ" else user.site_id
    if selected_id is None or (side == "SITE" and site_id not in {None, selected_id}):
        raise HTTPException(403, "Site not allowed")
    site = db.query(Site).filter(Site.id == selected_id).first()
    if site is None:
        raise HTTPException(404, "Site not found")
    if not is_government_site_record(site) or not in_active_scope(site, today_kst(), "government"):
        raise HTTPException(403, "Government active site required")
    return site, side


@router.get("/access")
def access(db: DbDep, current_user: CurrentUserDep):
    try:
        side = _actor_side(current_user)
    except HTTPException:
        return {"allowed": False}
    if side == "HQ":
        return {"allowed": True, "side": "HQ"}
    try:
        site, _ = _authorized_site(db, current_user, None)
    except HTTPException:
        return {"allowed": False}
    return {"allowed": True, "side": "SITE", "site_id": site.id, "site_name": site.site_name}


@router.get("/sites")
def sites(db: DbDep, current_user: CurrentUserDep):
    if _actor_side(current_user) != "HQ":
        raise HTTPException(403, "HQ safety only")
    rows = db.query(Site).order_by(Site.site_name).all()
    active = [site for site in rows if in_active_scope(site, today_kst(), "government")]
    messages = db.query(GovernmentContactMessage).filter(
        GovernmentContactMessage.site_id.in_([site.id for site in active])
    ).order_by(GovernmentContactMessage.id).all() if active else []
    last_by_site: dict[int, GovernmentContactMessage] = {}
    unread_by_site: dict[int, int] = {}
    for message in messages:
        last_by_site[message.site_id] = message
        if message.sender_side == "SITE" and message.read_at is None:
            unread_by_site[message.site_id] = unread_by_site.get(message.site_id, 0) + 1
    return {"items": [
        {"site_id": site.id, "site_code": site.site_code, "site_name": site.site_name,
         "unread_count": unread_by_site.get(site.id, 0),
         "last_message_at": last_by_site[site.id].created_at if site.id in last_by_site else None}
        for site in active
    ]}


@router.get("/unread")
def unread(db: DbDep, current_user: CurrentUserDep):
    side = _actor_side(current_user)
    if side == "SITE":
        site, _ = _authorized_site(db, current_user, None)
        site_ids = [site.id]
        opposite = "HQ"
    else:
        site_ids = [s.id for s in db.query(Site).all() if in_active_scope(s, today_kst(), "government")]
        opposite = "SITE"
    if not site_ids:
        return {"count": 0}
    return {"count": db.query(GovernmentContactMessage).filter(
        GovernmentContactMessage.site_id.in_(site_ids),
        GovernmentContactMessage.sender_side == opposite,
        GovernmentContactMessage.read_at.is_(None),
    ).count()}


@router.get("/messages")
def messages(db: DbDep, current_user: CurrentUserDep, site_id: int | None = None,
             before_id: int | None = Query(None, ge=1)):
    site, side = _authorized_site(db, current_user, site_id)
    query = db.query(GovernmentContactMessage, User).join(
        User, User.id == GovernmentContactMessage.sender_user_id
    ).filter(
        GovernmentContactMessage.site_id == site.id,
    )
    if before_id is not None:
        query = query.filter(GovernmentContactMessage.id < before_id)
    rows = query.order_by(GovernmentContactMessage.id.desc()).limit(501).all()
    has_more = len(rows) > 500
    rows = list(reversed(rows[:500]))
    return {"site_id": site.id, "site_name": site.site_name, "side": side, "has_more": has_more, "items": [
        {"id": m.id, "sender_side": m.sender_side, "sender_name": u.name,
         "body": m.body, "created_at": m.created_at, "read_at": m.read_at}
        for m, u in rows
    ]}


@router.post("/messages", status_code=201)
def send_message(body: MessageBody, db: DbDep, current_user: CurrentUserDep):
    site, side = _authorized_site(db, current_user, body.site_id)
    content = body.body.strip()
    if not content:
        raise HTTPException(422, "Message is empty")
    message = GovernmentContactMessage(site_id=site.id, sender_user_id=current_user.id,
                                       sender_side=side, body=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "site_id": site.id, "created_at": message.created_at}


@router.post("/read")
def mark_read(db: DbDep, current_user: CurrentUserDep, site_id: int | None = None,
              through_id: int = Query(..., ge=1)):
    site, side = _authorized_site(db, current_user, site_id)
    opposite = "SITE" if side == "HQ" else "HQ"
    count = db.query(GovernmentContactMessage).filter(
        GovernmentContactMessage.site_id == site.id,
        GovernmentContactMessage.sender_side == opposite,
        GovernmentContactMessage.id <= through_id,
        GovernmentContactMessage.read_at.is_(None),
    ).update({GovernmentContactMessage.read_at: utc_now()}, synchronize_session=False)
    db.commit()
    return {"read_count": count}
