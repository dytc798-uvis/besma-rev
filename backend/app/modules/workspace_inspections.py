"""Explicit publication of assigned inspections; preserves drafts and audit history."""
import json,re
from pathlib import Path
from datetime import date,timedelta
from fastapi import Depends,Header,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy import update
from app.core.auth import DbDep,get_current_user
from app.core.datetime_utils import utc_now,kst_today
from app.modules.safety_features.team_schedule_models import TeamScheduleItem,TeamScheduleEvent
from app.modules.safety_features.team_schedule_routes import _require_write,_member_or_403,_snapshot
from app.modules.safety_features.inspection_plan import INSPECTION_SOURCE
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.config.settings import settings

EVENT='INSPECTION_CONFIRMED'

def enabled():
    path=Path(settings.storage_root)/'headquarters-workspace'/'workspace-feature-flags.json'
    try:
        if path.exists() and json.loads(path.read_text()).get('inspection_publication',True) is not True:raise HTTPException(503,'점검계획 현장 반영 기능이 중지되어 있습니다.')
    except (OSError,ValueError):raise HTTPException(503,'점검계획 설정을 확인해 주세요.')

def binding(db,row):
    from app.modules.inspection_reports.site_identity import resolve
    site=resolve(db,row)
    if site is None:raise HTTPException(409,'점검계획의 원문 현장명과 현장 코드를 확인해 주세요.')
    return site

def records(db,site_id=None):
    # Read-only projection: never creates a zero/complete fallback on source errors.
    rows=db.query(TeamScheduleEvent,TeamScheduleItem).join(TeamScheduleItem,TeamScheduleEvent.item_id==TeamScheduleItem.id).filter(TeamScheduleEvent.event_type==EVENT,TeamScheduleItem.source==INSPECTION_SOURCE).order_by(TeamScheduleEvent.id.desc()).all()
    seen=set();out=[]
    for event,row in rows:
        if row.id in seen:continue
        seen.add(row.id);snap=json.loads(event.after_json);sid=snap.get('published_site_id')
        if site_id is not None and sid!=site_id:continue
        site=binding(db,row)
        if site.id!=sid:raise HTTPException(409,'점검계획의 현장 연결이 변경되었습니다.')
        owner=db.get(User,snap['assigned_user_id'])
        out.append({'public_id':row.public_id,'site_code':site.site_code,'site_name':site.site_name,'scheduled_date':snap['scheduled_date'],'due_date':snap.get('due_date'),'title':snap['title'],'detail_text':snap.get('detail_text'),'owner_name':owner.name if owner else '담당 확인 중','confirmed_at':event.created_at.isoformat()+'Z','confirmed_revision':event.to_revision,'current_revision':row.revision,'draft_changed':row.revision!=event.to_revision,'status':row.status,'archived':bool(row.archived_at)})
    return out

class Confirm(BaseModel):revision:int=Field(ge=1)

def install(router,authorized,result):
    @router.get('/inspection-publications')
    def publications(db:DbDep,user=Depends(authorized)):
        enabled();_member_or_403(db,user);today=kst_today();return result({'items':records(db),'date':today.isoformat(),'upcoming_through':(today+timedelta(days=7)).isoformat(),'available':True})
    @router.post('/inspection-publications/{public_id}/confirm')
    def confirm(public_id:str,body:Confirm,db:DbDep,user=Depends(authorized),surface:str|None=Header(None,alias='X-BESMA-Client-Surface')):
        enabled();_require_write(db,user,surface)
        row=db.query(TeamScheduleItem).filter(TeamScheduleItem.public_id==public_id).one_or_none()
        if row is None:raise HTTPException(404,'점검계획을 찾을 수 없습니다.')
        if row.source!=INSPECTION_SOURCE or row.assigned_user_id!=user.id:raise HTTPException(403,'본인의 점검계획만 확정할 수 있습니다.')
        if row.archived_at or row.status not in {'PLANNED','IN_PROGRESS'}:raise HTTPException(409,'예정 또는 진행 중인 점검만 확정할 수 있습니다.')
        previous=db.query(TeamScheduleEvent).filter(TeamScheduleEvent.item_id==row.id,TeamScheduleEvent.event_type==EVENT).order_by(TeamScheduleEvent.id.desc()).first()
        if previous and previous.to_revision==row.revision and body.revision in {row.revision,row.revision-1}:
            return result({'confirmed':True,'revision':row.revision,'item':next(r for r in records(db) if r['public_id']==public_id)})
        if row.revision!=body.revision:raise HTTPException(409,'다른 곳에서 수정된 계획입니다. 새로고침 후 확정해 주세요.')
        site=binding(db,row);before=_snapshot(row);now=utc_now()
        changed=db.execute(update(TeamScheduleItem).where(TeamScheduleItem.id==row.id,TeamScheduleItem.revision==body.revision,TeamScheduleItem.assigned_user_id==user.id,TeamScheduleItem.archived_at.is_(None)).values(revision=body.revision+1,updated_at=now,updated_by_user_id=user.id).execution_options(synchronize_session=False)).rowcount
        if changed!=1:db.rollback();raise HTTPException(409,'계획이 변경되었습니다. 새로고침 후 확정해 주세요.')
        db.expire(row);after=_snapshot(row);after['published_site_id']=site.id;after['published_site_code']=site.site_code
        db.add(TeamScheduleEvent(item_id=row.id,event_type=EVENT,actor_user_id=user.id,from_revision=body.revision,to_revision=row.revision,before_json=json.dumps(before,ensure_ascii=False),after_json=json.dumps(after,ensure_ascii=False),created_at=now));db.commit()
        return result({'confirmed':True,'revision':row.revision,'item':next(r for r in records(db) if r['public_id']==public_id)})
    @router.get('/my-site-inspections')
    def site_inspections(db:DbDep,user=Depends(get_current_user)):
        enabled()
        if not user.is_active or getattr(user.role,'value',user.role)!='SITE' or getattr(user,'ui_type','')!='SITE' or not user.site_id:raise HTTPException(403,'현장 계정으로 이용해 주세요.')
        return result({'items':records(db,user.site_id),'available':True})
