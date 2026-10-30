"""Own inspection report artifacts; does not change calendar/document permissions."""
from datetime import date
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
import json,os
from fastapi import APIRouter,Depends,File,Form,HTTPException,UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from app.core.auth import DbDep,get_current_user
from app.config.settings import settings
from app.modules.safety_features.team_schedule_models import TeamScheduleItem
from app.modules.safety_features.inspection_plan import INSPECTION_SOURCE,schedule_owner_id
from app.modules.safety_features.team_schedule_routes import _member_or_403,_linked_schedule_access
from app.modules.users.models import User
from .store import ReportStore,ReportConflict

router=APIRouter(prefix='/safety-features/inspection-reports',tags=['inspection-reports'])
CurrentUser=Annotated[User,Depends(get_current_user)]
class Payload(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    revision:int=Field(ge=1)
    inspection_date:str=Field(pattern=r'^20\d{2}-\d{2}-\d{2}$')
    summary:str=Field(default='',max_length=240)
    captions:list[str]=Field(min_length=1,max_length=24)
def actor(db,user):
    if os.environ.get('BESMA_INSPECTION_REPORTS_ENABLED','').casefold()not in {'1','true'}:raise HTTPException(404,'평가표 작성을 준비하고 있습니다.')
    _member_or_403(db,user)
    if str(getattr(user.role,'value',user.role))not in {'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN'}:raise HTTPException(403,'평가표 작성 권한을 확인해 주세요.')
def plan(db,user,public_id):
    actor(db,user);row=db.query(TeamScheduleItem).filter_by(public_id=public_id).first()
    if row is None or row.source!=INSPECTION_SOURCE or row.archived_at is not None or schedule_owner_id(row)!=user.id or not _linked_schedule_access(db,row,user.id):raise HTTPException(404,'본인 점검계획을 찾을 수 없습니다.')
    return row
def store():return ReportStore(Path(settings.storage_root).parent/'inspection-reports-private',Path(__file__).parent/'assets/반기평가표.pptx')
def fail(error):
    if isinstance(error,KeyError):raise HTTPException(404,'작성한 평가표를 찾을 수 없습니다.')
    if isinstance(error,ReportConflict):raise HTTPException(409,'내용이 바뀌었습니다. 앞선 작성 결과를 확인해 주세요.')
    if str(error)=='TEMPLATE_CHANGED':raise HTTPException(503,'평가표 양식이 변경되어 확인이 필요합니다.')
    raise HTTPException(422,'사진과 입력 내용을 확인해 주세요.')
@router.get('/capabilities')
def capabilities(db:DbDep,user:CurrentUser):
    actor(db,user);return {'enabled':True,'max_photos':24,'photo_long_edge':1600,'max_caption':60,'own_inspections_only':True}
@router.get('/receipts/{request_key}')
def receipt(request_key:str,db:DbDep,user:CurrentUser):
    actor(db,user)
    try:return store().receipt(user.id,request_key)
    except(KeyError,ValueError,OSError)as e:fail(e)
@router.get('/plans/{public_id}')
def history(public_id:str,db:DbDep,user:CurrentUser):
    plan(db,user,public_id);return {'items':store().history(user.id,public_id)}
@router.post('/plans/{public_id}',status_code=201)
async def create(public_id:str,db:DbDep,user:CurrentUser,request_key:Annotated[str,Form()],payload:Annotated[str,Form()],photos:list[UploadFile]=File()):
    row=plan(db,user,public_id)
    try:body=Payload.model_validate_json(payload);day=date.fromisoformat(body.inspection_date)
    except(ValidationError,ValueError):raise HTTPException(422,'점검일과 입력 내용을 확인해 주세요.')
    if row.revision!=body.revision:raise HTTPException(409,'점검계획이 변경되었습니다. 입력 내용을 보존했으니 현재 일정을 확인해 주세요.')
    if not 1<=len(photos)<=24 or len(photos)!=len(body.captions)or any(len(c)>60 for c in body.captions):raise HTTPException(422,'사진 수와 설명을 확인해 주세요. 사진은 24장, 설명은 60자까지입니다.')
    inputs=[]
    for photo,caption in zip(photos,body.captions):
        if photo.content_type not in {'image/jpeg','image/png','image/webp'}:raise HTTPException(422,'JPG, PNG, WEBP 사진을 사용해 주세요.')
        inputs.append((await photo.read(15*1024*1024+1),caption.strip()))
    fields={'site_name':row.title.removeprefix('[점검] ').strip(),'inspection_date':day.isoformat(),'summary':body.summary.strip(),'inspector':user.name,'plan_revision':row.revision}
    user_id=user.id;plan_id=row.public_id;db.rollback()
    try:return await run_in_threadpool(store().save,user_id,plan_id,request_key,fields,inputs)
    except(KeyError,ValueError,OSError)as e:fail(e)
@router.get('/{rid}/file')
def download(rid:str,db:DbDep,user:CurrentUser):
    actor(db,user)
    try:data,name=store().file(user.id,rid)
    except(KeyError,ValueError,OSError)as e:fail(e)
    return Response(data,media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name),'Cache-Control':'no-store'})
