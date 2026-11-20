"""Authenticated hq01 evaluation viewing. No schedule membership or write endpoints."""
from contextlib import closing
from copy import deepcopy
from pathlib import Path
import hashlib,json,os,re,sqlite3
from typing import Annotated
from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Response
from app.core.auth import DbDep,get_current_user
from app.config.settings import settings
from app.modules.users.models import User
from app.modules.safety_features.team_schedule_models import TeamScheduleItem
from app.modules.safety_features.team_schedule_routes import _linked_schedule_access
from .catalog import CATALOG,FORMS,blank,context_key,period_value,validate_assessment
from . import supervisor_group,site_profile
from .overview import summarize
from .routes import fail

router=APIRouter(prefix='/safety-features/half-year-reader',tags=['half-year-reader'])
Current=Annotated[User,Depends(get_current_user)]

def review_root():
    return Path(settings.storage_root).parent/'half-year-reviews-private'

def allowed(user):
    return (bool(getattr(user,'is_active',False)) and
            str(getattr(user.role,'value',user.role))=='HQ_SAFE' and
            str(getattr(user,'login_id','')).casefold()=='hq01')

def authorize(user):
    if not allowed(user):raise HTTPException(403,'조회 전용 계정을 확인해 주세요.')
    if os.environ.get('BESMA_HALF_YEAR_REVIEWS_ENABLED','').casefold()not in {'1','true'}:
        raise HTTPException(404,'반기평가를 준비하고 있습니다.')

def registered(row):
    return (row is not None and row.source=='INSPECTION_PLAN' and row.archived_at is None and
            re.fullmatch(r'inspection:\d{6}:site-\d{1,6}(?::[A-Za-z0-9_-]+)?',row.client_item_key or'')is not None)

def selected(db,user,public_id,period):
    authorize(user)
    try:period_value(period)
    except ValueError as error:fail(error)
    row=db.query(TeamScheduleItem).filter_by(public_id=public_id).first()
    if not registered(row)or not _linked_schedule_access(db,row,user.id):
        raise HTTPException(404,'반기평가 현장을 찾을 수 없습니다.')
    return row,context_key(row,period)

def states(keys):
    path=review_root()/'reviews.sqlite3'
    if not path.exists():raise HTTPException(503,'반기평가 자료를 확인하지 못했습니다.')
    result={}
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10))as db:
        for start in range(0,len(keys),300):
            group=keys[start:start+300]
            for key,revision,raw in db.execute('SELECT id,revision,data FROM contexts WHERE id IN ('+','.join('?'for _ in group)+')',group):
                result[key]=supervisor_group.project({'revision':revision,'data':json.loads(raw)})
    return result

def state(key):
    return states([key]).get(key,{'revision':0,'data':blank()})

def private(response):
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'

@router.get('/capabilities')
def capabilities(user:Current,response:Response):
    authorize(user);private(response)
    return {'can_read':True,'can_write':False,'headquarters_reader':True}

@router.get('/calendar')
def calendar(db:DbDep,user:Current,response:Response,from_date:date,to_date:date):
    authorize(user)
    if to_date<from_date or (to_date-from_date).days>62:
        raise HTTPException(400,'달력 조회기간을 확인해 주세요.')
    # hq01 can read official inspections and this verified shared evaluation period.
    # Personal requests, team work and other meeting text retain their original ACL.
    rows=db.query(TeamScheduleItem).filter(TeamScheduleItem.archived_at.is_(None),
        TeamScheduleItem.scheduled_date<=to_date).order_by(TeamScheduleItem.scheduled_date,TeamScheduleItem.id).all()
    items=[]
    for row in rows:
        is_period=(row.public_id=='51b34f1a-d783-4745-aee7-d101f784469a' and row.source=='WEEKLY_MEETING'
            and row.title=='26년 하반기 현장소장, 관리감독자 평가 및 반기평가 점검 : 안전보건실')
        if not (registered(row)or is_period)or (row.due_date or row.scheduled_date)<from_date:continue
        if not _linked_schedule_access(db,row,user.id):continue
        items.append({'public_id':row.public_id,'title':row.title,'scheduled_date':row.scheduled_date.isoformat(),
            'due_date':row.due_date.isoformat()if row.due_date else None,'source':row.source,
            'status':row.status,'owner_user_id':row.assigned_user_id if row.source=='INSPECTION_PLAN'else row.created_by_user_id})
    private(response)
    return {'can_read':True,'can_write':False,'items':items}

@router.get('/overview')
def overview(db:DbDep,user:Current,response:Response,period:str='2026-H2'):
    authorize(user)
    try:period_value(period)
    except ValueError as error:fail(error)
    rows=db.query(TeamScheduleItem).filter(TeamScheduleItem.source=='INSPECTION_PLAN',TeamScheduleItem.archived_at.is_(None)).order_by(TeamScheduleItem.scheduled_date,TeamScheduleItem.id).all()
    latest={context_key(row,period):row for row in rows if registered(row)and _linked_schedule_access(db,row,user.id)}
    values=states(list(latest));items=[]
    for key,row in latest.items():
        value=summarize(values.get(key,{'data':blank()})['data'])
        done=bool(value.get('paper_completion')or value.get('reported_completion')or(value.get('screen_completed')and value.get('signature_completed')))
        status='COMPLETED'if done else'IN_PROGRESS'if(value.get('status')=='IN_PROGRESS'or value.get('screen_completed')or value.get('completed'))else'NOT_STARTED'
        items.append({'public_id':row.public_id,'site':row.title.removeprefix('[점검] ').strip(),'status':status,'can_write':False})
    private(response)
    return {'can_read':True,'can_write':False,'headquarters_reader':True,'period':period,'items':sorted(items,key=lambda item:item['site']),'catalog':CATALOG}

@router.get('/plans/{public_id}')
def read(public_id:str,period:str,db:DbDep,user:Current,response:Response):
    row,key=selected(db,user,public_id,period);value=state(key)
    allowed_keys={'assessments','subjects','files','evidence','site_details','prior_assessments','paper_completion','reported_completion'}
    private(response)
    return {'revision':value['revision'],'site_name':row.title.removeprefix('[점검] ').strip(),'period':period,'can_write':False,
            'data':{name:content for name,content in value['data'].items()if name in allowed_keys}}

@router.get('/plans/{public_id}/preview/{form}/{subject_id}')
def preview(public_id:str,form:str,subject_id:str,period:str,db:DbDep,user:Current):
    from .printing import document
    try:
        row,key=selected(db,user,public_id,period);value=state(key)
        if form not in FORMS:raise KeyError('FORM_MISSING')
        saved=value['data']['assessments'].get(form+':'+subject_id,{})
        source=deepcopy(saved.get('draft')or saved.get('completed')or{})
        if not source.get('data'):
            return Response('<!doctype html><html lang="ko"><meta charset="utf-8"><body><p>저장된 평가내용이 없습니다. 첨부자료에서 평가서를 확인하세요.</p></body></html>',media_type='text/html',headers={'Cache-Control':'private, no-store','Vary':'Authorization'})
        data,result=validate_assessment(form,source['data'],value['data']['files'],value['data']['subjects'],subject_id,False)
        name=next((p['name']for p in value['data']['subjects'].get(form,[])if p['id']==subject_id),'')if form=='manager'else''
        snapshot={**source,'form':form,'criteria_version':source.get('criteria_version',CATALOG['version']),'evaluation_scope_version':1,'data':data,'result':result,'subject_name':name,'inspector':source.get('inspector')or''}
        profile=site_profile.resolve(db,row,value['data'].get('site_details',{}));snapshot=site_profile.enrich(snapshot,profile)
        html=document(form,snapshot,row.title.removeprefix('[점검] ').strip(),period,blind=bool(result['missing']))
        return Response(html,media_type='text/html',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"})
    except(ValueError,KeyError,OSError,TypeError)as error:fail(error)

@router.get('/plans/{public_id}/files/{file_id}')
def file(public_id:str,file_id:str,period:str,db:DbDep,user:Current):
    _,key=selected(db,user,public_id,period);value=state(key)
    meta=next((item for item in value['data'].get('files',[])if item['id']==file_id),None)
    if meta is None or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',file_id):raise HTTPException(404,'자료를 찾을 수 없습니다.')
    types={'.pdf':'application/pdf','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp'}
    if meta.get('extension')not in types:raise HTTPException(415,'PDF·이미지 형식만 화면에서 볼 수 있습니다.')
    root=review_root()/'files'/hashlib.sha256(key.encode()).hexdigest();path=root/(file_id+meta['extension'])
    if path.is_symlink()or not path.resolve().is_relative_to(root.resolve()):raise HTTPException(409,'파일 원본을 확인해 주세요.')
    try:content=path.read_bytes()
    except OSError:raise HTTPException(404,'자료를 찾을 수 없습니다.')
    if len(content)!=meta['bytes']or hashlib.sha256(content).hexdigest()!=meta['sha256']:raise HTTPException(409,'파일 원본을 확인해 주세요.')
    return Response(content,media_type=types[meta['extension']],headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})
