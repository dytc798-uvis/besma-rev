"""Two explicitly requested inspectors: their assigned evaluations only."""
from fastapi import HTTPException
from sqlalchemy import func
from app.modules.safety_features.team_schedule_models import TeamScheduleItem
from app.modules.safety_features.inspection_plan import INSPECTION_SOURCE,schedule_owner_id
from app.modules.safety_features.team_schedule_routes import _linked_schedule_access,_serialize_item,_names_for_items

PILOT_USERS=frozenset({95,523})
def allowed(user):
    return user.id in PILOT_USERS and bool(getattr(user,'is_active',False)) and str(getattr(user.role,'value',user.role))=='HQ_SAFE'

def own_plan(db,user,public_id):
    if not allowed(user):raise HTTPException(403,'휴대폰 평가 대상 계정을 확인해 주세요.')
    row=db.query(TeamScheduleItem).filter_by(public_id=public_id).first()
    if row is None or row.source!=INSPECTION_SOURCE or row.archived_at is not None or schedule_owner_id(row)!=user.id or not _linked_schedule_access(db,row,user.id):
        raise HTTPException(404,'본인 점검계획을 찾을 수 없습니다.')
    return row

def rows(db,user,from_date,to_date):
    if not allowed(user):raise HTTPException(403,'휴대폰 평가 대상 계정을 확인해 주세요.')
    if to_date<from_date or(to_date-from_date).days>366:raise HTTPException(422,'조회 기간을 확인해 주세요.')
    return [r for r in db.query(TeamScheduleItem).filter(TeamScheduleItem.source==INSPECTION_SOURCE,
        TeamScheduleItem.assigned_user_id==user.id,TeamScheduleItem.archived_at.is_(None),
        TeamScheduleItem.scheduled_date<=to_date,func.coalesce(TeamScheduleItem.due_date,TeamScheduleItem.scheduled_date)>=from_date).order_by(TeamScheduleItem.scheduled_date,TeamScheduleItem.id).all()
        if schedule_owner_id(r)==user.id and _linked_schedule_access(db,r,user.id)]

def plans(db,user,from_date,to_date):
    result=rows(db,user,from_date,to_date);names=_names_for_items(db,result)
    return {'items':[{**_serialize_item(r,names,user.id),'can_edit':False}for r in result]}
