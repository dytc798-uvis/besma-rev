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
from app.modules.government_contact.models import GovernmentContactTestMessage
from app.modules.document_settings.models import DocumentRequirement
from types import SimpleNamespace
from app.modules.sites.models import Site
from app.modules.users.models import User

router = APIRouter(prefix="/government-contact", tags=["government-contact"])
HQ_ROLES = {Role.HQ_SAFE, Role.HQ_SAFE_ADMIN, Role.SUPER_ADMIN}
SITE_ROLES = {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}


class MessageBody(BaseModel):
    site_id: int | None = None
    body: str = Field(min_length=1, max_length=4000)
    document_code: str | None = Field(None, min_length=1, max_length=64)


def _test_user(db, user):
    site=db.get(Site,user.site_id) if user.site_id else None
    return user.role in SITE_ROLES and user.login_id in {'test01','test02'} and site is not None and site.site_code=='TEST-BESMA'


def _test_sites(db):
    sites={s.site_code:s for s in db.query(Site).all() if in_active_scope(s,today_kst(),'government')}
    return [SimpleNamespace(id=-(n+1),site_name=f'test{n+1} · {sites[code].site_name}',source_site_id=sites[code].id,test_mode=True) for n,code in enumerate(('24028','25037','25040')) if code in sites]


def _messages_model(site):return GovernmentContactTestMessage if getattr(site,'test_mode',False) else GovernmentContactMessage


def _subjects(db,site):
    rows=db.query(DocumentRequirement).filter(DocumentRequirement.site_id==getattr(site,'source_site_id',site.id),DocumentRequirement.is_enabled.is_(True)).order_by(DocumentRequirement.display_order,DocumentRequirement.id).all()
    return {r.code:r.title for r in rows if r.code.startswith('GOV_')}


def _filter(query,model,document_code,general_only):
    if general_only and document_code is not None:raise HTTPException(422,'Choose one communication category')
    if general_only:return query.filter(model.document_code.is_(None))
    return query.filter(model.document_code==document_code) if document_code is not None else query


def _actor_side(user: User) -> str:
    if user.role in HQ_ROLES:
        return "HQ"
    if user.role in SITE_ROLES:
        return "SITE"
    raise HTTPException(403, "Not allowed")


def _authorized_site(db: DbDep, user: User, site_id: int | None) -> tuple[Site, str]:
    side = _actor_side(user)
    if (site_id is not None and site_id<0) or (side=='SITE' and _test_user(db,user)):
        if side!='HQ' and not _test_user(db,user):raise HTTPException(403,'Test only')
        selected=site_id or -1
        site=next((s for s in _test_sites(db) if s.id==selected),None)
        if site is None:raise HTTPException(404,'Test site not found')
        return site,side
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
    site=db.get(Site,current_user.site_id) if current_user.site_id else None
    legacy_hidden=bool(site and site.site_code in {'SITE002','24025'}) or current_user.role==Role.HQ_OTHER
    try:
        side = _actor_side(current_user)
    except HTTPException:
        return {"allowed": False,"legacy_contact_hidden":legacy_hidden}
    if side == "HQ":
        return {"allowed": True, "side": "HQ","legacy_contact_hidden":True}
    if _test_user(db,current_user):return {'allowed':True,'side':'SITE','site_id':-1,'site_name':'관급 소통 검증','test_mode':True,'legacy_contact_hidden':True}
    try:
        site, _ = _authorized_site(db, current_user, None)
    except HTTPException:
        return {"allowed": False,"legacy_contact_hidden":legacy_hidden}
    return {"allowed": True, "side": "SITE", "site_id": site.id, "site_name": site.site_name,"legacy_contact_hidden":True}


@router.get('/test-sites')
def test_sites(db:DbDep,current_user:CurrentUserDep):
    side=_actor_side(current_user)
    if side!='HQ' and not _test_user(db,current_user):raise HTTPException(403,'Test only')
    return {'items':[{'site_id':s.id,'site_name':s.site_name,'test_mode':True,'unread_count':db.query(GovernmentContactTestMessage).filter(GovernmentContactTestMessage.site_id==s.id,GovernmentContactTestMessage.sender_side==('SITE' if side=='HQ' else 'HQ'),GovernmentContactTestMessage.read_at.is_(None)).count()} for s in _test_sites(db)]}


@router.get('/subjects')
def subjects(db:DbDep,current_user:CurrentUserDep,site_id:int|None=None):
    site,_=_authorized_site(db,current_user,site_id)
    return {'items':[{'code':None,'title':'일반 소통 (문서 없음)'}]+[{'code':code,'title':title} for code,title in _subjects(db,site).items()]}


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
    if side=='SITE' and _test_user(db,current_user):return {'count':db.query(GovernmentContactTestMessage).filter(GovernmentContactTestMessage.site_id.in_([s.id for s in _test_sites(db)]),GovernmentContactTestMessage.sender_side=='HQ',GovernmentContactTestMessage.read_at.is_(None)).count()}
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
             before_id: int | None = Query(None, ge=1),document_code:str|None=None,general_only:bool=False):
    site, side = _authorized_site(db, current_user, site_id)
    model=_messages_model(site)
    query = db.query(model, User).join(
        User, User.id == model.sender_user_id
    ).filter(
        model.site_id == site.id,
    )
    if before_id is not None:
        query = query.filter(model.id < before_id)
    query=_filter(query,model,document_code,general_only)
    rows = query.order_by(model.id.desc()).limit(501).all()
    has_more = len(rows) > 500
    rows = list(reversed(rows[:500]))
    labels=_subjects(db,site)
    return {"site_id": site.id, "site_name": site.site_name, "side": side, "has_more": has_more, "items": [
        {"id": m.id, "sender_side": m.sender_side, "sender_name": u.name,
         "body": m.body, "document_code":m.document_code,"document_title":labels.get(m.document_code,m.document_code) if m.document_code else '일반 소통 (문서 없음)',"created_at": m.created_at, "read_at": m.read_at}
        for m, u in rows
    ]}


@router.post("/messages", status_code=201)
def send_message(body: MessageBody, db: DbDep, current_user: CurrentUserDep):
    site, side = _authorized_site(db, current_user, body.site_id)
    content = body.body.strip()
    if not content:
        raise HTTPException(422, "Message is empty")
    if body.document_code and body.document_code not in _subjects(db,site):raise HTTPException(422,'Document not available for this site')
    message = _messages_model(site)(site_id=site.id, sender_user_id=current_user.id,
                                       sender_side=side, body=content,document_code=body.document_code)
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "site_id": site.id, "created_at": message.created_at}


@router.post("/read")
def mark_read(db: DbDep, current_user: CurrentUserDep, site_id: int | None = None,
              through_id: int = Query(..., ge=1),document_code:str|None=None,general_only:bool=False):
    site, side = _authorized_site(db, current_user, site_id)
    opposite = "SITE" if side == "HQ" else "HQ"
    model=_messages_model(site)
    count = _filter(db.query(model).filter(
        model.site_id == site.id,
        model.sender_side == opposite,
        model.id <= through_id,
        model.read_at.is_(None),
    ),model,document_code,general_only).update({model.read_at: utc_now()}, synchronize_session=False)
    db.commit()
    return {"read_count": count}
