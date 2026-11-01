from pathlib import Path
from typing import Annotated
from urllib.parse import quote
import os,json
from fastapi import APIRouter,Depends,HTTPException,Form,File,UploadFile
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field,ConfigDict
from app.core.auth import DbDep,get_current_user
from app.config.settings import settings
from app.modules.users.models import User
from app.modules.inspection_reports.routes import plan,actor
from .catalog import CATALOG,context_key,period_value,Conflict
from .store import ReviewStore
from . import jobs,exports,monthly_sources
from .catalog import FORMS
router=APIRouter(prefix='/safety-features/half-year-reviews',tags=['half-year-reviews'])
Current=Annotated[User,Depends(get_current_user)]
class Change(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_key:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    revision:int=Field(ge=0)
    period:str=Field(pattern=r'^20\d{2}-H[12]$')
    action:str=Field(pattern=r'^(evidence|subject|assessment|caption|parse|apply_parse|monthly-link|monthly-links|monthly-unlink|walk-start|walk-item|walk-report)$')
    data:dict
def enabled(db,user):
    if os.environ.get('BESMA_HALF_YEAR_REVIEWS_ENABLED','').casefold()not in {'1','true'}:raise HTTPException(404,'반기평가를 준비하고 있습니다.')
    actor(db,user)
def store():return ReviewStore(Path(settings.storage_root).parent/'half-year-reviews-private')
def selected(db,user,public_id,period):
    enabled(db,user);row=plan(db,user,public_id);return row,context_key(row,period)
def fail(error):
    if isinstance(error,Conflict):raise HTTPException(409,'다른 화면에서 자료가 변경되었습니다. 입력 내용을 보존했으니 새로 확인해 주세요.')
    if isinstance(error,KeyError):raise HTTPException(404,'이 현장·반기의 자료를 찾을 수 없습니다.')
    messages={'SIGNED_TABLE_REQUIRED':'해당 최종 평가표 사진을 업로드하고 원본 기준 서명·전체 쪽 확인을 체크해 주세요.','WALK_FOUR_FORMS_REQUIRED':'4종 각각의 최종 평가표 사진 업로드·확인을 먼저 완료해 주세요.','WALK_REPORT_URL_INVALID':'네이버웍스 게시글 주소를 확인해 주세요.','SIGNED_PHOTO_ALREADY_USED':'다른 평가표에 사용한 사진입니다. 이 평가표 사진을 따로 연결해 주세요.','WALK_REASON_REQUIRED':'해당없음 사유를 입력해 주세요.','WALK_DATE_MISMATCH':'점검기록과 평가일이 다릅니다. 점검일과 연결 기록을 확인해 주세요.','MONTHLY_SOURCE_INVALID':'이 현장·반기의 취합자료를 다시 선택해 주세요.','MONTHLY_SOURCE_LIMIT':'연결할 수 있는 취합자료 수를 넘었습니다.','UNREVIEWED_ITEMS_REMAIN':'미평가 항목과 점검사진을 확인해 주세요.','COMPLETE_FIRST':'평가 항목을 입력하고 완료 저장한 뒤 받을 수 있습니다.','SUBJECT_REQUIRED':'평가대상자를 먼저 추가해 주세요.','SUBJECT_EXISTS':'이미 등록된 평가대상자입니다.','NOTE_TOO_LONG':'비고는 두 줄 이내로 짧게 입력해 주세요.','VERDICT_INVALID':'해당없음 사유와 적합 여부를 확인해 주세요.','SCORE_INVALID':'평가표의 배점 범위 안에서 점수를 입력해 주세요.','TEMPLATE_CHANGED':'평가표 원본이 변경되어 확인이 필요합니다.','DATE_PERIOD_MISMATCH':'점검일이 선택한 반기와 다릅니다.','PDF_REQUIRED':'평가한 PDF 파일을 선택해 주세요.','PARSE_REVIEW_REQUIRED':'현장·대상자·점검일·합계와 판독 내용을 확인해 주세요.'}
    raise HTTPException(422,messages.get(str(error),'입력 내용과 첨부자료를 확인해 주세요.'))
@router.get('/capabilities')
def capabilities(db:DbDep,user:Current):
    enabled(db,user);return {'enabled':True,'catalog':CATALOG,'shared_by':'site_and_half_year','max_file_bytes':15*1024*1024,'photo_long_edge':1600,'mobile_photo_version':1,'walkthrough_version':1,'signed_table_completion':True,'monthly_batch_links_version':1}
@router.get('/plans/{public_id}')
def read(public_id:str,period:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);return {**store().load(key),'paper_jobs':jobs.listing(store(),key),'site_name':row.title.removeprefix('[점검] ').strip(),'period':period,'plan_revision':row.revision}
    except(ValueError,KeyError,OSError)as e:fail(e)
@router.get('/plans/{public_id}/monthly-sources')
def monthly_candidates(public_id:str,period:str,db:DbDep,user:Current,response:Response):
    try:
        row,key=selected(db,user,public_id,period);response.headers['Cache-Control']='no-store'
        return monthly_sources.sources(monthly_sources.monthly.load(),monthly_sources.site_for_plan(db,row),period)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
@router.get('/plans/{public_id}/walkthrough-collection')
def walkthrough_collection(public_id:str,period:str,month:str,db:DbDep,user:Current,response:Response):
    import re
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',month):raise HTTPException(422,'자료월을 확인해 주세요.')
    try:
        row,key=selected(db,user,public_id,period);site=monthly_sources.site_for_plan(db,row)
        source_period=month[:4]+('-H1'if int(month[5:])<=6 else'-H2')
        value=monthly_sources.sources(monthly_sources.monthly.load(),site,source_period)
        value['items']=[r for r in value['items']if r['month']==month]
        value.update(month=month,count=len(value['items']),submission_rate=None,rate_state='DENOMINATOR_UNCONFIRMED',site_code=site.get('code')if site else None)
        response.headers['Cache-Control']='no-store';return value
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
@router.post('/plans/{public_id}/changes')
def change(public_id:str,body:Change,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,body.period);request=body.model_dump()
        if body.action=='monthly-link':request['data']=monthly_sources.resolve(db,row,body.period,body.data)
        if body.action=='monthly-links':request['data']=monthly_sources.resolve_many(db,row,body.period,body.data)
        return store().mutate(key,user.id,user.name,request,context_meta={'public_id':public_id,'site_name':row.title.removeprefix('[점검] ').strip()})
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
@router.get('/plans/{public_id}/receipts/{request_key}')
def receipt(public_id:str,period:str,request_key:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);return store().receipt(key,user.id,request_key)
    except(ValueError,KeyError,OSError)as e:fail(e)
@router.post('/plans/{public_id}/files',status_code=201)
async def upload(public_id:str,db:DbDep,user:Current,period:Annotated[str,Form()],revision:Annotated[int,Form()],request_key:Annotated[str,Form()],evidence_id:Annotated[str,Form()],caption:Annotated[str,Form()]='',walk_run_id:Annotated[str,Form()]='',criterion_id:Annotated[str,Form()]='',photo_stage:Annotated[str,Form()]='EVIDENCE',file:UploadFile=File()):
    try:
        row,key=selected(db,user,public_id,period)
        if revision<0:raise ValueError('REVISION_INVALID')
        raw=await file.read(15*1024*1024+1);actor_id=user.id;name=user.name;db.rollback()
        request={'revision':revision,'request_key':request_key,'period':period,'action':'attach','data':{'evidence_id':evidence_id,'caption':caption,'filename':file.filename or'자료'}}
        if walk_run_id or criterion_id:request['data'].update(walk_run_id=walk_run_id,criterion_id=criterion_id,photo_stage=photo_stage)
        return await run_in_threadpool(store().mutate,key,actor_id,name,request,(raw,file.content_type or''),{'public_id':public_id})
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
@router.get('/plans/{public_id}/files/{file_id}')
def download_file(public_id:str,period:str,file_id:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);content,meta=store().file(key,file_id)
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='image/jpeg'if meta['kind']=='image'else'application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(meta['filename']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
@router.get('/plans/{public_id}/drafts/{form}/{subject_id}')
def draft_copy(public_id:str,form:str,subject_id:str,period:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period)
        snapshot=store().load(key)['data']['assessments'].get(form+':'+subject_id,{}).get('draft')
        if not snapshot or form not in FORMS:raise KeyError('DRAFT_MISSING')
        if snapshot['result'].get('missing'):raise ValueError('DRAFT_REVIEW_REQUIRED')
        site=row.title.removeprefix('[점검] ').strip()
        if form=='report':
            photos=[]
            for file_id in snapshot['data']['photo_ids']:
                raw,meta=store().file(key,file_id);photos.append({'data':raw,'width':meta['width'],'height':meta['height'],'sha256':meta['sha256'],'caption':snapshot['data']['photo_captions'].get(file_id,meta['caption'])})
            content=exports.pptx(snapshot,site,snapshot['inspector'],photos,period)
        elif form=='law':content=exports.hwpx(snapshot,site,snapshot['inspector'])
        else:content=exports.xlsx(form,snapshot,site,snapshot['inspector'])
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote('서명용_'+FORMS[form]['title']+'.'+FORMS[form]['format']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
@router.post('/plans/{public_id}/exports/{form}/{subject_id}')
async def export(public_id:str,form:str,subject_id:str,period:str,snapshot_id:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);site=row.title.removeprefix('[점검] ').strip();db.rollback();result=await run_in_threadpool(store().export,key,form,subject_id,site,period,snapshot_id)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return {'id':result['id'],'filename':result['filename'],'bytes':result['size'],'sha256':result['sha256'],'snapshot_id':result['snapshot_id']}
@router.get('/plans/{public_id}/outputs/{output_id}')
def output(public_id:str,period:str,output_id:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);content,meta=store().output_file(key,output_id)
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(meta['filename']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@router.get('/plans/{public_id}/templates/{form}')
def blank_template(public_id:str,period:str,form:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period)
        if form not in FORMS:raise KeyError('FORM_MISSING')
        name=FORMS[form].get('template','반기평가표.pptx');content=exports.template(name)
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(FORMS[form]['title']+'_출력용.'+FORMS[form]['format']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
