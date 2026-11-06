"""Keep exact copies of the same planned half-year visit on the shared calendar."""
from datetime import date,datetime
import re
from sqlalchemy import update
from fastapi import HTTPException
from .team_schedule_models import TeamScheduleItem

def identity(title,meeting=False):
    value=re.sub(r'\s+','',title or'')
    if value.startswith('[점검]'):value=value[len('[점검]'):]
    for suffix in ['반기평가점검','안전보건평가점검','반기평가']:
        if value.endswith(suffix):return value[:-len(suffix)]
    return ''if meeting else value

def synchronize(db,plan,before,actor,now,snapshot,after_snapshot,record_event):
    if plan.source!='INSPECTION_PLAN':return []
    start=date.fromisoformat(before['scheduled_date'])
    end=date.fromisoformat(before['due_date'])if before.get('due_date')else None
    if plan.scheduled_date==start and plan.due_date==end:return []
    name=identity(before['title']);changed=[]
    candidates=db.query(TeamScheduleItem).filter(TeamScheduleItem.source=='WEEKLY_MEETING',TeamScheduleItem.scheduled_date==start,TeamScheduleItem.archived_at.is_(None)).all()
    for row in candidates:
        owner=row.assigned_user_id or row.created_by_user_id
        if owner!=actor.id or row.status=='COMPLETED' or row.due_date!=end or identity(row.title,True)!=name:continue
        old=snapshot(row);revision=row.revision
        result=db.execute(update(TeamScheduleItem).where(TeamScheduleItem.id==row.id,TeamScheduleItem.revision==revision,TeamScheduleItem.archived_at.is_(None)).values(scheduled_date=plan.scheduled_date,due_date=plan.due_date,revision=revision+1,updated_at=now,updated_by_user_id=actor.id))
        if result.rowcount!=1:
            db.rollback();raise HTTPException(409,'TEAM_SCHEDULE_UPDATE_CONFLICT')
        new=after_snapshot(old,scheduled_date=plan.scheduled_date.isoformat(),due_date=plan.due_date.isoformat()if plan.due_date else None,revision=revision+1)
        record_event(db,item_id=row.id,event_type='UPDATED',actor_user_id=actor.id,before=old,after=new)
        changed.append(row.public_id)
    return changed
