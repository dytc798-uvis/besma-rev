from pathlib import Path
from typing import Annotated
from urllib.parse import quote
import os,json
from datetime import date
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
from . import jobs,exports,monthly_sources,mobile_pilot
from .catalog import FORMS
from . import site_profile
router=APIRouter(prefix='/safety-features/half-year-reviews',tags=['half-year-reviews'])
Current=Annotated[User,Depends(get_current_user)]
class Change(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_key:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    revision:int=Field(ge=0)
    base:dict|None=None
    period:str=Field(pattern=r'^20\d{2}-H[12]$')
    action:str=Field(pattern=r'^(evidence|subject|assessment|assessment-summary|assessment-comment|assessment-improvements|site-details|manager-default|prior-assessment|caption|parse|apply_parse|monthly-link|monthly-links|monthly-unlink|walk-start|walk-item|walk-report|walk-guidance|criterion-check|evidence-photo|prepare-defaults)$')
    data:dict
def enabled(db,user):
    if os.environ.get('BESMA_HALF_YEAR_REVIEWS_ENABLED','').casefold()not in {'1','true'}:raise HTTPException(404,'반기평가를 준비하고 있습니다.')
    if not mobile_pilot.allowed(user):actor(db,user)
def store():return ReviewStore(Path(settings.storage_root).parent/'half-year-reviews-private')

def collection_defaults_for(db,row,period):
    from .prepared_defaults import for_plan
    try:return for_plan(db,row,period)
    except (HTTPException,OSError,ValueError,TypeError,KeyError):return {'state':'UNAVAILABLE','sources':[],'fingerprint':None,'opinion':{'state':'CHECK_REQUIRED','count':None,'score':None,'sources':[]}}

def profile_for(db,row,key):return site_profile.resolve(db,row,store().load(key)['data'].get('site_details',{}))
def selected(db,user,public_id,period):
    enabled(db,user);row=mobile_pilot.own_plan(db,user,public_id)if mobile_pilot.allowed(user)else plan(db,user,public_id);return row,context_key(row,period)
def fail(error):
    if isinstance(error,Conflict):raise HTTPException(409,'다른 화면에서 자료가 변경되었습니다. 입력 내용을 보존했으니 새로 확인해 주세요.')
    if isinstance(error,KeyError):raise HTTPException(404,'이 현장·반기의 자료를 찾을 수 없습니다.')
    messages={'PACKAGE_TOO_LARGE':'자료가 많아 한 번에 묶을 수 없습니다. 평가서와 증빙자료를 나누어 받아 주세요.','PACKAGE_INCOMPLETE':'4종 평가와 지정서에 등록한 관리감독자 평가를 마친 뒤 현장 자료를 받을 수 있습니다.','CRITERIA_UPDATED':'평가항목이 바뀌었습니다. 작성내용을 보관한 뒤 화면을 새로 열어 주세요.','SITE_DETAILS_INVALID':'공정률은 0~100 사이 숫자로 입력하고 기준일을 확인해 주세요.','SUMMARY_TOO_LONG':'총평은 240자·6줄 이내로 작성해 주세요.','PDF_PREVIEW_UNAVAILABLE':'원문을 미리 볼 수 없습니다. 원본 파일을 받아 확인해 주세요.','PDF_PREVIEW_SOURCE_CHANGED':'원문 파일 확인이 필요합니다. 다시 조회해 주세요.','SIGNED_TABLE_REQUIRED':'해당 최종 평가표 사진을 업로드하고 원본 기준 서명·전체 쪽 확인을 체크해 주세요.','WALK_FOUR_FORMS_REQUIRED':'4종 각각의 최종 평가표 사진 업로드·확인을 먼저 완료해 주세요.','WALK_REPORT_URL_INVALID':'네이버웍스 게시글 주소를 확인해 주세요.','SIGNED_PHOTO_ALREADY_USED':'다른 평가표에 사용한 사진입니다. 이 평가표 사진을 따로 연결해 주세요.','WALK_REASON_REQUIRED':'해당없음 사유를 입력해 주세요.','WALK_DATE_MISMATCH':'점검기록과 평가일이 다릅니다. 점검일과 연결 기록을 확인해 주세요.','MONTHLY_SOURCE_INVALID':'이 현장·반기의 취합자료를 다시 선택해 주세요.','MONTHLY_SOURCE_LIMIT':'연결할 수 있는 취합자료 수를 넘었습니다.','UNREVIEWED_ITEMS_REMAIN':'아직 입력하지 않은 평가 문항을 확인해 주세요.','SIGNATURE_INCOMPLETE_CONFIRM':'아직 작성하지 않은 부분이 있습니다. 확인 후 다운로드해 주세요.','SIGNATURE_SOURCE_CHANGED':'평가내용이 변경되었습니다. 다시 확인한 뒤 다운로드해 주세요.','COMPLETE_FIRST':'평가 항목을 입력하고 완료 저장한 뒤 받을 수 있습니다.','SUBJECT_REQUIRED':'평가대상자를 먼저 추가해 주세요.','SUBJECT_EXISTS':'이미 등록된 평가대상자입니다.','NOTE_TOO_LONG':'비고는 두 줄 이내로 짧게 입력해 주세요.','VERDICT_INVALID':'해당없음 사유와 적합 여부를 확인해 주세요.','SCORE_INVALID':'평가표의 배점 범위 안에서 점수를 입력해 주세요.','TEMPLATE_CHANGED':'평가표 원본이 변경되어 확인이 필요합니다.','DATE_PERIOD_MISMATCH':'점검일이 선택한 반기와 다릅니다.','PDF_REQUIRED':'수기로 작성한 평가 PDF 파일을 선택해 주세요.','PARSE_REVIEW_REQUIRED':'현장·대상자·점검일·합계와 판독 내용을 확인해 주세요.'}
    raise HTTPException(422,messages.get(str(error),'입력 내용과 첨부자료를 확인해 주세요.'))
@router.get('/capabilities')
def capabilities(db:DbDep,user:Current):
    enabled(db,user);return {'enabled':True,'concurrent_merge_version':1,'inline_evidence_photos':True,'catalog':CATALOG,'shared_by':'site_and_half_year','max_file_bytes':15*1024*1024,'photo_long_edge':1600,'mobile_photo_version':1,'walkthrough_version':1,'signed_table_completion':False,'question_completion_version':1,'print_preview_version':1,'overview_version':1,'paper_completion_version':1,'prior_assessment_version':1,'evaluation_first_version':1,'shared_criterion_evidence_version':1,'mobile_review_pilot':mobile_pilot.allowed(user),'monthly_batch_links_version':1,'template_bundle_version':1,'pdf_preview_version':1,'field_outbox_version':1,'guidance_version':1,'criterion_check_version':1,'evidence_only_photos':True,'signature_output_version':1,'signature_delivery_connected':False,'linked_navigation_version':1,'summary_autosave_version':1,'comment_autosave_version':1,'site_profile_version':1,'director_report_version':1,'collection_defaults_version':1}
@router.get('/mobile-pilot/capabilities')
def mobile_capabilities(db:DbDep,user:Current,response:Response):
    enabled(db,user)
    if not mobile_pilot.allowed(user):raise HTTPException(403,'휴대폰 평가 대상 계정을 확인해 주세요.')
    response.headers['Cache-Control']='private, no-store'
    return {'can_read':True,'can_write':False,'own_evaluations_only':True,'mobile_review_pilot':True}

@router.get('/mobile-pilot/plans')
def mobile_plans(db:DbDep,user:Current,response:Response,from_date:date,to_date:date):
    enabled(db,user);response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    return mobile_pilot.plans(db,user,from_date,to_date)

@router.get('/overview')
def overview(db:DbDep,user:Current,response:Response,from_date:date,to_date:date):
    from app.modules.safety_features.team_schedule_routes import list_team_schedule_items
    from .overview import summaries
    enabled(db,user)
    if mobile_pilot.allowed(user):rows=mobile_pilot.rows(db,user,from_date,to_date)
    else:
        value=list_team_schedule_items(db,user,from_date,to_date,False,False,True,True)
        rows=[plan(db,user,item['public_id'])for item in value['items']]
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    return {'items':summaries(store().root,rows)}

@router.get('/plans/{public_id}/print/{form}/{subject_id}')
def print_assessment(public_id:str,form:str,subject_id:str,period:str,snapshot_id:str,db:DbDep,user:Current):
    from .printing import document
    try:
        row,key=selected(db,user,public_id,period)
        if form not in FORMS:raise KeyError('FORM_MISSING')
        assessment=store().load(key)['data']['assessments'].get(form+':'+subject_id,{});snapshot=assessment.get('completed')
        if not snapshot:raise ValueError('COMPLETE_FIRST')
        if snapshot['id']!=snapshot_id:raise Conflict('COMPLETED_VERSION_CHANGED')
        snapshot=site_profile.enrich(snapshot,profile_for(db,row,key),assessment)
        content=document(form,snapshot,row.title.removeprefix('[점검] ').strip(),period)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(content,media_type='text/html',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src 'none'; base-uri 'none'; form-action 'none'"})

@router.get('/plans/{public_id}')
def read(public_id:str,period:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);defaults=collection_defaults_for(db,row,period);return {**store().load(key),'paper_jobs':jobs.listing(store(),key),'site_name':row.title.removeprefix('[점검] ').strip(),'period':period,'plan_revision':row.revision,'site_profile':profile_for(db,row,key),'collection_defaults':defaults,'opinion_default':defaults['opinion']}
    except(ValueError,KeyError,OSError)as e:fail(e)
@router.get('/plans/{public_id}/visit-info')
def visit_info(public_id:str,period:str,db:DbDep,user:Current,response:Response):
    try:
        row,key=selected(db,user,public_id,period);profile=profile_for(db,row,key)
        response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
        return {'address':profile.get('visit_address',''),'contacts':profile.get('visit_contacts',[])}
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
        if body.action=='prepare-defaults':
            if body.data:raise ValueError('REQUEST_INVALID')
            request['data']=collection_defaults_for(db,row,body.period)
            if not request['data'].get('fingerprint'):raise ValueError('MONTHLY_SOURCE_INVALID')
        if body.action=='manager-default':
            if body.data:raise ValueError('SUBJECT_INVALID')
            request['data']={'form':'manager','name':profile_for(db,row,key)['manager_default']}
        if body.action=='monthly-link':request['data']=monthly_sources.resolve(db,row,body.period,body.data)
        if body.action=='monthly-links':request['data']=monthly_sources.resolve_many(db,row,body.period,body.data)
        return {**store().mutate(key,user.id,user.name,request,context_meta={'public_id':public_id,'site_name':row.title.removeprefix('[점검] ').strip()}),'site_profile':profile_for(db,row,key)}
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
@router.get('/plans/{public_id}/receipts/{request_key}')
def receipt(public_id:str,period:str,request_key:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);return store().receipt(key,user.id,request_key)
    except(ValueError,KeyError,OSError)as e:fail(e)
@router.post('/plans/{public_id}/files',status_code=201)
async def upload(public_id:str,db:DbDep,user:Current,period:Annotated[str,Form()],revision:Annotated[int,Form()],request_key:Annotated[str,Form()],evidence_id:Annotated[str,Form()],caption:Annotated[str,Form()]='',walk_run_id:Annotated[str,Form()]='',criterion_id:Annotated[str,Form()]='',photo_stage:Annotated[str,Form()]='EVIDENCE',evidence_note:Annotated[str,Form()]='',file:UploadFile=File()):
    try:
        row,key=selected(db,user,public_id,period)
        if revision<0:raise ValueError('REVISION_INVALID')
        raw=await file.read(15*1024*1024+1);actor_id=user.id;name=user.name;db.rollback()
        request={'revision':revision,'request_key':request_key,'period':period,'action':'attach','data':{'evidence_id':evidence_id,'caption':caption,'filename':file.filename or'자료'}}
        if walk_run_id or criterion_id:request['data'].update(walk_run_id=walk_run_id,criterion_id=criterion_id,photo_stage=photo_stage,evidence_note=evidence_note)
        return await run_in_threadpool(store().mutate,key,actor_id,name,request,(raw,file.content_type or''),{'public_id':public_id})
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
@router.get('/plans/{public_id}/files/{file_id}')
def download_file(public_id:str,period:str,file_id:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);content,meta=store().file(key,file_id)
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='image/jpeg'if meta['kind']=='image'else'application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(meta['filename']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
@router.get('/plans/{public_id}/files/{file_id}/preview')
async def pdf_information(public_id:str,period:str,file_id:str,db:DbDep,user:Current):
    from . import pdf_preview
    try:
        row,key=selected(db,user,public_id,period);content,meta=store().file(key,file_id);db.rollback()
        value=await run_in_threadpool(pdf_preview.information,content,meta)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(json.dumps(value),media_type='application/json',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})

@router.get('/plans/{public_id}/files/{file_id}/preview/{page_number}')
async def pdf_page(public_id:str,period:str,file_id:str,page_number:int,db:DbDep,user:Current):
    from . import pdf_preview
    try:
        row,key=selected(db,user,public_id,period);content,meta=store().file(key,file_id);db.rollback()
        image,proof=await run_in_threadpool(pdf_preview.render,content,meta,page_number)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(image,media_type='image/png',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Source-SHA256':proof['source_sha256'],'X-Page-Number':str(proof['page_number']),'X-Preview-SHA256':proof['sha256'],'Access-Control-Expose-Headers':'X-Source-SHA256, X-Page-Number, X-Preview-SHA256, Content-Length'})

@router.get('/plans/{public_id}/drafts/{form}/{subject_id}')
def draft_copy(public_id:str,form:str,subject_id:str,period:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period)
        snapshot=store().load(key)['data']['assessments'].get(form+':'+subject_id,{}).get('draft')
        if not snapshot or form not in FORMS:raise KeyError('DRAFT_MISSING')
        if snapshot['result'].get('missing'):raise ValueError('DRAFT_REVIEW_REQUIRED')
        site=row.title.removeprefix('[점검] ').strip();snapshot=site_profile.enrich(snapshot,profile_for(db,row,key))
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
        row,key=selected(db,user,public_id,period);site=row.title.removeprefix('[점검] ').strip();profile=profile_for(db,row,key);db.rollback();result=await run_in_threadpool(store().export,key,form,subject_id,site,period,snapshot_id,profile)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return {'id':result['id'],'filename':result['filename'],'bytes':result['size'],'sha256':result['sha256'],'snapshot_id':result['snapshot_id']}
@router.get('/plans/{public_id}/outputs/{output_id}')
def output(public_id:str,period:str,output_id:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);content,meta=store().output_file(key,output_id)
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(meta['filename']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@router.get('/plans/{public_id}/templates')
def blank_templates(public_id:str,period:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period);content=exports.template_bundle()
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='application/zip',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote('반기평가_출력용_4종.zip'),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@router.get('/plans/{public_id}/templates/{form}')
def blank_template(public_id:str,period:str,form:str,db:DbDep,user:Current):
    try:
        row,key=selected(db,user,public_id,period)
        if form not in FORMS:raise KeyError('FORM_MISSING')
        name=FORMS[form].get('template','반기평가표.pptx');content=exports.template(name)
    except(ValueError,KeyError,OSError)as e:fail(e)
    return Response(content,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(FORMS[form]['title']+'_출력용.'+FORMS[form]['format']),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

class SignatureRequest(BaseModel):
    purpose:str=Field(default='SIGNATURE',pattern=r'^(SIGNATURE|REPORT)$')
    model_config=ConfigDict(extra='forbid',strict=True)
    request_key:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    form:str=Field(pattern=r'^(report|law|manager|supervisor)$')
    subject_id:str=Field(pattern=r'^(site|[0-9a-f]{32})$')
    snapshot_id:str=Field(pattern=r'^[0-9a-f]{32}$')

@router.post('/plans/{public_id}/signature-prints')
def signature_print(public_id:str,period:str,body:SignatureRequest,db:DbDep,user:Current,response:Response):
    from .signature_jobs import queue
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    try:
        row,key=selected(db,user,public_id,period);return queue(store(),key,user,row,period,body.model_dump(),profile_for(db,row,key))
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)

@router.get('/plans/{public_id}/signature-prints')
def signature_prints(public_id:str,period:str,db:DbDep,user:Current,response:Response):
    from .signature_jobs import listing
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    row,key=selected(db,user,public_id,period)
    return {'items':listing(store(),key,user.id)}

@router.get('/plans/{public_id}/signature-prints/{job_id}/file')
def signature_file(public_id:str,period:str,job_id:str,db:DbDep,user:Current):
    from .signature_jobs import output
    try:
        row,key=selected(db,user,public_id,period);raw,meta=output(store(),key,user.id,job_id)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(raw,media_type='application/pdf',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Disposition':"inline; filename*=UTF-8''"+quote(meta['filename'])})

@router.get('/plans/{public_id}/signature-prints/{job_id}/preview')
async def signature_preview(public_id:str,period:str,job_id:str,db:DbDep,user:Current,response:Response):
    from .signature_jobs import output
    from .pdf_preview import information
    try:
        row,key=selected(db,user,public_id,period);raw,meta=output(store(),key,user.id,job_id);db.rollback()
        result=await run_in_threadpool(information,raw,{**meta,'extension':'.pdf'})
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    return result

@router.get('/plans/{public_id}/signature-prints/{job_id}/preview/{page_number}')
async def signature_preview_page(public_id:str,period:str,job_id:str,page_number:int,db:DbDep,user:Current):
    from .signature_jobs import output
    from .pdf_preview import render
    try:
        row,key=selected(db,user,public_id,period);raw,meta=output(store(),key,user.id,job_id);db.rollback()
        image,proof=await run_in_threadpool(render,raw,{**meta,'extension':'.pdf'},page_number)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(image,media_type='image/png',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Source-SHA256':proof['source_sha256'],'X-Page-Number':str(proof['page_number']),'X-Preview-SHA256':proof['sha256'],'Access-Control-Expose-Headers':'X-Source-SHA256, X-Page-Number, X-Preview-SHA256, Content-Length'})


class NavigationRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    form:str=Field(pattern=r'^(report|law|manager|supervisor)$')
    subject:str=Field(pattern=r'^(site|[0-9a-f]{32})$')
    criterion:str=Field(min_length=1,max_length=40)
    version:int=Field(ge=0)
    device:str=Field(pattern=r'^[0-9a-f-]{36}$')
    sequence:int=Field(ge=1,le=9007199254740991)

@router.get('/plans/{public_id}/navigation')
def navigation_read(public_id:str,period:str,db:DbDep,user:Current,response:Response):
    from . import navigation
    row,key=selected(db,user,public_id,period)
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    return navigation.read(store().root,key,user.id)

@router.post('/plans/{public_id}/navigation')
def navigation_write(public_id:str,period:str,body:NavigationRequest,db:DbDep,user:Current,response:Response):
    from . import navigation
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    try:
        row,key=selected(db,user,public_id,period);review=store()
        position={k:getattr(body,k) for k in ['form','subject','criterion']}
        navigation.validate(position,review.load(key)['data'])
        return navigation.write(review.root,key,user.id,position,body.version,body.device,body.sequence)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)


@router.get('/plans/{public_id}/package')
def package(public_id:str,period:str,db:DbDep,user:Current):
    from .site_package import build
    try:
        row,key=selected(db,user,public_id,period)
        raw,filename=build(store(),key,row.title.removeprefix('[점검] ').strip(),period,profile_for(db,row,key))
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
    return Response(raw,media_type='application/zip',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename),'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})


class SigningBundleRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_key:str=Field(pattern=r'^[A-Za-z0-9_-]{8,80}$')
    fingerprint:str=Field(pattern=r'^[a-f0-9]{64}$')
    allow_incomplete:bool=False

@router.get('/plans/{public_id}/signature-bundle')
def signing_bundle_prepare(public_id:str,period:str,db:DbDep,user:Current,response:Response):
    from . import signature_bundle as bundle
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    try:
        row,key=selected(db,user,public_id,period);return bundle.public(bundle.prepare(store(),key,row,period,user,profile_for(db,row,key)))
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)

@router.post('/plans/{public_id}/signature-bundle')
def signing_bundle_queue(public_id:str,period:str,body:SigningBundleRequest,db:DbDep,user:Current,response:Response):
    from . import signature_bundle as bundle
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    try:
        row,key=selected(db,user,public_id,period);return bundle.queue(store(),key,user,row,period,body.model_dump(),profile_for(db,row,key))
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)

@router.get('/plans/{public_id}/signature-bundle/{bundle_id}')
def signing_bundle_status(public_id:str,bundle_id:str,period:str,db:DbDep,user:Current,response:Response):
    from . import signature_bundle as bundle
    response.headers['Cache-Control']='private, no-store';response.headers['Vary']='Authorization'
    try:
        row,key=selected(db,user,public_id,period);return bundle.status(store(),key,user.id,bundle_id)
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)

@router.get('/plans/{public_id}/signature-bundle/{bundle_id}/file')
def signing_bundle_file(public_id:str,bundle_id:str,period:str,db:DbDep,user:Current):
    from . import signature_bundle as bundle
    try:
        row,key=selected(db,user,public_id,period);status=bundle.status(store(),key,user.id,bundle_id)
        if status['status']!='READY':raise KeyError('SIGNATURE_MISSING')
        raw=bundle.merged(store(),key,user.id,bundle_id)
        return Response(raw,media_type='application/pdf',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(status['filename']),'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})
    except(ValueError,KeyError,OSError,TypeError)as e:fail(e)
