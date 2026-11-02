from starlette.responses import StreamingResponse
from starlette.background import BackgroundTask
"""BESMA-authenticated private request API; no remote shell or model tools."""
import json
import sqlite3
from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .store import Conflict, MAX_BYTES, MAX_ORIGINAL_BYTES
from .access import headquarters_user


@dataclass(frozen=True)
class RequestConfig:
    enabled: bool = False
    members: tuple = ()
    owner: tuple = ()
    nas_files_enabled: bool = False
    naver_delivery_enabled: bool = False
    source_lookup_enabled: bool = False
    source_generation_enabled: bool = False
    workbook_edit_enabled: bool = False
    owner_result_followup_enabled: bool = False
    image_source_comparison_enabled: bool = False
    registered_forms_enabled: bool = False


class CreateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    request_key: str = Field(min_length=8,max_length=80,pattern=r'^[a-zA-Z0-9_-]+$')
    kind: Literal['QUESTION','FILE','EDIT']
    title: str = Field(min_length=1,max_length=100)
    body: str = Field(min_length=1,max_length=6000)
    nas_file_id: str|None = Field(default=None,pattern=r'^[0-9a-f]{64}$')
    form_file_id: str|None = Field(default=None,pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def one_source(self):
        if self.form_file_id and(self.nas_file_id or self.input_attachment_id or self.result_file_id):raise ValueError('한 개의 원본을 선택해 주세요.')
        return self
    parent_request_id: str|None = Field(default=None,pattern=r'^[0-9a-f]{32}$')
    input_attachment_id: str|None = Field(default=None,pattern=r'^[0-9a-f]{32}$')
    result_file_id: str|None = Field(default=None,pattern=r'^[0-9a-f]{32}$')


class NasQuery(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    q: str=Field(min_length=0,max_length=100)
    offset: int=Field(default=0,ge=0,le=1_000_000)
    sort: Literal['relevance','newest','name']='relevance'
    snapshot: str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')

    @model_validator(mode='after')
    def empty_recent_only(self):
        if not self.q.strip() and (self.q != '' or self.sort != 'newest'):
            raise ValueError('RECENT_ORDER_REQUIRED_FOR_EMPTY_QUERY')
        return self

class DiscoveryQuery(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    text:str=Field(min_length=1,max_length=6000)


class WorkerCapabilities(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    capabilities: list[Literal['NAS_ORIGINAL_V1','NAS_REVIEW_V1','NAS_EDIT_V1','GENERATED_PDF_V1','UPLOADED_IMAGE_V1','REQUEST_SOURCE_LOOKUP_V1','NAS_SOURCE_CREATE_V1','NAS_WORKBOOK_EDIT_V1','OWNER_SOURCE_CHOICES_V1','OWNER_SOURCE_CHOICES_V2','UPLOADED_IMAGE_SOURCE_V1','REGISTERED_FORM_SOURCE_V1']]=Field(default_factory=list,max_length=12)


class InputImageRead(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    lease:str=Field(min_length=64,max_length=64,pattern=r'^[0-9a-f]{64}$')
    attachment_id:str=Field(pattern=r'^[0-9a-f]{32}$')


class ReviewVersion(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    review_version:int=Field(ge=0)
    source_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')


class ReleaseFile(ReviewVersion):
    file_id:str=Field(pattern=r'^[0-9a-f]{32}$')
    file_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')


class DenyFile(ReviewVersion):
    reason:str=Field(min_length=1,max_length=500)


class Lease(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    lease: str = Field(pattern=r'^[0-9a-f]{64}$')


class Heartbeat(Lease):
    phase: Literal['SMALL','LARGE','DOCUMENT_BUILDING','SOURCE_READING']|None = None


class ReadResult(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    completion_token:str=Field(pattern=r'^[0-9a-f]{64}$')


def create_router(auth, config_provider, store_provider, eligible_provider, nas=None, forms=None):
    router=APIRouter(prefix='/work-requests',tags=['work-requests'])
    from .registered_forms import RegisteredForms,SCOPE as FORM_SCOPE,CAP as FORM_CAP
    forms=forms or RegisteredForms()

    def config():
        try:return config_provider()
        except (OSError,ValueError,TypeError,RuntimeError):raise HTTPException(503,'업무 요청 설정을 확인하고 있습니다.') from None

    def actor(user=Depends(auth)):
        cfg=config();pair=(getattr(user,'id',None),getattr(user,'login_id',None))
        if (not cfg.enabled or not headquarters_user(user)
                or pair not in {*cfg.members,cfg.owner}):
            raise HTTPException(404,'요청한 항목을 찾을 수 없습니다.')
        return {'id':pair[0],'login_id':pair[1],'owner':pair==cfg.owner}

    def worker(user=Depends(actor)):
        if not user['owner']:raise HTTPException(404,'요청한 항목을 찾을 수 없습니다.')
        return user

    def store():
        try:return store_provider()
        except (OSError,ValueError,RuntimeError):raise HTTPException(503,'업무 요청을 준비하고 있습니다.') from None

    def call(fn,*args,**kwargs):
        try:return fn(*args,**kwargs)
        except KeyError:raise HTTPException(404,'요청한 항목을 찾을 수 없습니다.') from None
        except Conflict as error:
            if str(error)=='RESULT_SELECTION_UNAVAILABLE':raise HTTPException(409,'질문할 파일의 연결을 다시 확인해 주세요. 최근 결과에서 파일을 선택할 수 있습니다.') from None
            raise HTTPException(409,'처리 상태가 바뀌었습니다. 목록을 다시 확인해 주세요.') from None
        except ValueError:raise HTTPException(422,'입력 내용과 파일을 확인해 주세요.') from None
        except (OSError,RuntimeError):raise HTTPException(503,'처리하지 못했습니다. 잠시 후 다시 확인해 주세요.') from None

    def result(value):
        return JSONResponse(value,headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})

    def source_valid(user,source):
        if source.get('scope')==FORM_SCOPE:return config().registered_forms_enabled and forms.valid(user,source)
        return config().nas_files_enabled and nas is not None and nas.valid(user,source)

    def file_access(item,user):
        source=item.get('source')
        if not source:return True
        if source.get('scope')==FORM_SCOPE:
            if not config().registered_forms_enabled:return False
            if item['status']=='COMPLETED'and item.get('review_phase')in {'OWN','SHARED','RELEASED'}:return forms.member_valid(user)
            return forms.valid(user,source)
        if not config().nas_files_enabled or nas is None:return False
        # A confirmed immutable copy is a request-specific grant. Moving/re-indexing
        # the NAS source alone does not erase it; current account membership still gates it.
        if user['owner']or item['status']=='COMPLETED'and item.get('review_phase')in {'RELEASED','OWN'}:
            return getattr(nas,'member_valid',lambda actor:nas.valid(actor,source))(user)
        return source_valid(user,source)

    def retained_result_access(user,anchor):
        return file_access({'source':json.loads(anchor['source_json']),
                            'status':anchor['status'],'review_phase':anchor['review_phase']},user)

    def consent_context(user,rid):
        """Read the exact prior request, without granting or applying consent."""
        queue=store()
        try:
            with queue.connection()as connection:
                row=connection.execute('SELECT rowid AS sequence,* FROM requests WHERE id=? AND user_id=? AND login_id=?',
                                       (rid,user['id'],user['login_id'])).fetchone()
                if row is None or row['kind']!='QUESTION' or not row['parent_request_id']:return None
                prior=connection.execute('SELECT * FROM requests WHERE id=? AND user_id=? AND login_id=? AND conversation_id=? AND rowid<?',
                                         (row['parent_request_id'],user['id'],user['login_id'],row['conversation_id'],row['sequence'])).fetchone()
                if prior is None:return None
                view=visible(queue._public(connection,prior,False),user,with_consent=False)
                if view.get('source_access')is False or prior['status']=='ACCESS_REVOKED' or prior['review_phase']=='DENIED':
                    return {'status':'UNAVAILABLE'}
                return {'request_id':prior['id'],'status':prior['status'],
                        'files_available':prior['status']=='COMPLETED'and bool(view.get('files'))}
        except (sqlite3.Error,KeyError,ValueError,OSError,HTTPException):
            return None

    def visible(item,user,*,with_consent=True):
        source=item.get('source')
        if item.get('can_retry')and(item.get('review_phase')=='OWN'and not user['owner']or source and not source_valid(user,source)):
            item['can_retry']=False;item['retry_unavailable_reason']='원본 자료와 이용 권한을 확인해 주세요.'
        item['source_access']=file_access(item,user)
        if source and not item['source_access']:
            item={**item,'source':None,'files':[],'reply':'원본 자료와 이용 권한을 확인해 주세요.'}
        elif source and not user['owner'] and item.get('review_phase') not in {'OWN','SHARED','RELEASED'}:
            item={**item,'files':[],'reply':'자료와 답변의 제공 확인을 기다리고 있습니다.'}
        # A query hint opens the existing requester-scoped search. It is never
        # a file grant, a saved selection, or proof of latest approval.
        if (item['kind']=='QUESTION' and item['status']=='COMPLETED' and not source
                and not item.get('input_attachments') and config().nas_files_enabled and nas is not None):
            from .grounding import recent_request
            lookup=recent_request(item['body'])
            if lookup is not None:item={**item,'nas_lookup':{'q':lookup['query'],'sort':'newest'}}
        from . import result_followup
        if user['owner']and config().source_lookup_enabled and config().owner_result_followup_enabled:
            queue=store()
            with queue.connection() as connection:
                if result_followup.requested(connection,item['id']):
                    row=connection.execute('SELECT * FROM requests WHERE id=?',(item['id'],)).fetchone()
                    try:
                        reference=result_followup.validate(connection,queue,user,row,config(),eligible_provider(),source_valid,retained_access=retained_result_access)
                        item={**item,'result_reference':{key:reference[key]for key in ['file_name','bytes','sha256']}}
                    except (Conflict,KeyError,ValueError,OSError,RuntimeError):
                        item={**item,'result_reference_unavailable':True}
        if with_consent and item['kind']=='QUESTION'and not source and not item.get('input_attachments'):
            from .grounding import current_text,untargeted_consent
            if untargeted_consent(current_text(item['body'])):
                context=consent_context(user,item['id'])
                if context and context.get('request_id')and context['status']!='UNAVAILABLE':
                    item={**item,'reply_context':{'request_id':context['request_id'],
                          'label':'준비된 파일 보기'if context['files_available']else'요청 상태 보기'}}
        return item

    def require_nas_gate():
        if not config().nas_files_enabled:raise HTTPException(404,'NAS 자료 요청을 준비하고 있습니다.')

    @router.get('/availability')
    def availability(user=Depends(auth)):
        try:identity=actor(user)
        except HTTPException as error:
            if error.status_code==404:return result({'enabled':False})
            raise
        from .input_images import available
        return result({'enabled':True,'original_max_bytes':MAX_ORIGINAL_BYTES,'analysis_max_bytes':MAX_BYTES,'question_retry':True,'owner_result_followup':bool(identity['owner']and config().source_lookup_enabled and config().owner_result_followup_enabled),'owner_source_choices':bool(identity['owner']and config().source_lookup_enabled),'owner_choices_allowed_sources':['NAS','PC']if config().nas_files_enabled else['PC'],'scope_exempt':identity['owner'],'nas_files':bool(config().nas_files_enabled and nas and nas.available(user)),'source_edit':bool(config().nas_files_enabled and nas and nas.available(user)),'workbook_edit':bool(config().workbook_edit_enabled and config().nas_files_enabled and nas and nas.available(user)),'source_choices':bool(config().source_lookup_enabled and config().nas_files_enabled and nas and nas.available(user)),'source_lookup':bool(config().source_lookup_enabled and config().nas_files_enabled and nas and nas.available(user)),'source_generation':bool(config().source_generation_enabled and config().source_lookup_enabled and config().nas_files_enabled and nas and nas.available(user)),'image_source_comparison':bool(config().image_source_comparison_enabled and config().source_lookup_enabled and config().nas_files_enabled and nas and nas.available(user)),'input_images':available(store_provider()),'registered_forms_enabled':bool(config().registered_forms_enabled and forms.member_valid(identity)),'registered_forms':bool(config().registered_forms_enabled and forms.member_valid(identity)and form_worker_ready()),'naver_delivery':bool(config().naver_delivery_enabled and identity['owner'])})

    def form_worker_ready():
        queue=store_provider()
        with queue.connection()as connection:row=connection.execute('SELECT seen_at,capabilities FROM worker_state WHERE id=1').fetchone()
        if row is None:return False
        try:return 0<=queue.clock()-row['seen_at']<=120 and FORM_CAP in json.loads(row['capabilities'])
        except(ValueError,TypeError):return False

    class FormSelection(BaseModel):
        model_config=ConfigDict(extra='forbid',strict=True)
        relative_path:str=Field(min_length=6,max_length=1600)

    class FormRead(BaseModel):
        model_config=ConfigDict(extra='forbid',strict=True)
        lease:str=Field(pattern=r'^[a-f0-9]{64}$')

    @router.post('/form-selections',status_code=201)
    def select_form(body:FormSelection,user=Depends(actor),db=Depends(store)):
        if not config().registered_forms_enabled:raise HTTPException(404,'등록 양식 연결을 준비하고 있습니다.')
        if not form_worker_ready():raise HTTPException(503,'양식 처리기 연결을 확인하고 있습니다. 잠시 후 다시 확인해 주세요.')
        source,_=call(forms.snapshot,user,body.relative_path)
        response=result({**source,'form_file_id':call(db.register_selection,user,source)});response.status_code=201;return response

    @router.post('/worker/{rid}/form-source')
    def read_form(rid:str,body:FormRead,user=Depends(worker),db=Depends(store)):
        if not config().registered_forms_enabled:raise HTTPException(404,'등록 양식 연결을 준비하고 있습니다.')
        with db.connection()as connection:
            row=call(db._lease,connection,rid,body.lease)
            source=json.loads(row['source_json']or'null')
            requester={'id':row['user_id'],'login_id':row['login_id']}
        allowed={(x['id'],x['login_id'])for x in eligible_provider()}
        if(not source or source.get('scope')!=FORM_SCOPE or (requester['id'],requester['login_id'])not in allowed
                or not forms.member_valid(user)):raise HTTPException(404,'원본 자료 이용 권한을 확인해 주세요.')
        content=call(forms.read,requester,source)
        return Response(content,media_type='application/octet-stream',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})

    @router.post('/input-attachments',status_code=201)
    async def upload_input(file:UploadFile=File(...),request_key:str=Form(...,min_length=8,max_length=80),user=Depends(actor),db=Depends(store)):
        from .input_images import register,MAX_IMAGE_BYTES
        raw=await file.read(MAX_IMAGE_BYTES+1)
        if len(raw)>MAX_IMAGE_BYTES:raise HTTPException(413,'사진은 8MB 이하로 첨부해 주세요.')
        response=result(call(register,db,user,request_key,file.filename,raw));response.status_code=201;return response

    @router.post('/input-attachments/{identity}/remove')
    def remove_input(identity:str,user=Depends(actor),db=Depends(store)):
        from .input_images import retire
        return result(call(retire,db,user,identity))

    def image_response(value):
        info,raw=value
        return Response(raw,media_type=info['media_type'],headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff','Content-Disposition':"attachment; filename*=UTF-8''"+quote(info['filename'])})

    @router.get('/{rid}/inputs/{identity}')
    def get_input(rid:str,identity:str,user=Depends(actor),db=Depends(store)):
        from .input_images import read
        return image_response(call(read,db,rid,identity,user,allow_context=config().image_source_comparison_enabled))

    @router.post('/worker/{rid}/input-image')
    def worker_input(rid:str,body:InputImageRead,user=Depends(worker),db=Depends(store)):
        from .input_images import read
        return image_response(call(read,db,rid,body.attachment_id,None,body.lease,eligible_provider(),allow_context=config().image_source_comparison_enabled))

    @router.post('/nas/search')
    def nas_search(body:NasQuery,user=Depends(auth),db=Depends(store)):
        identity=actor(user)
        if not config().nas_files_enabled or nas is None:raise HTTPException(404,'NAS 자료 요청을 준비하고 있습니다.')
        state=call(nas.search_state,user,body.q,offset=body.offset,sort=body.sort,snapshot=body.snapshot) if body.offset or body.sort!='relevance' or body.snapshot else call(nas.search_state,user,body.q)
        return result({'items':[{**source,'nas_file_id':call(db.register_selection,identity,source)}for source in state['items']],
            'unavailable_count':state.get('unavailable_count',0),'original_max_bytes':MAX_ORIGINAL_BYTES,
            **{key:state.get(key)for key in ['total_count','complete','offset','next_offset','scanned_count','excluded_count','snapshot','sort']}})

    @router.post('/nas/discover')
    def discover_files(body:DiscoveryQuery,user=Depends(auth),db=Depends(store)):
        identity=actor(user)
        if not config().nas_files_enabled or nas is None:raise HTTPException(404,'NAS 자료 요청을 준비하고 있습니다.')
        from .discovery import discover
        value=call(discover,user,body.text,nas.search_state,source_workflow=config().source_lookup_enabled,source_choices_workflow=config().source_lookup_enabled and not identity['owner'],owner_sources=config().source_lookup_enabled and identity['owner'])
        value['items']=[{**source,'nas_file_id':call(db.register_selection,identity,source)}for source in value['items']]
        return result(value)

    @router.get('')
    def listing(before:str|None=Query(default=None,pattern=r'^[0-9a-f]{32}$'),user=Depends(actor),db=Depends(store)):
        value=call(db.list,user,before);value['items']=[visible(item,user)for item in value['items']]
        return result(value)

    @router.get('/notifications')
    def notifications(user=Depends(actor),db=Depends(store)):
        items=[visible(item,user)for item in call(db.notifications,user)]
        items=[item for item in items if item['source_access']and(not item.get('source')or item.get('review_phase')in {'OWN','SHARED','RELEASED'})]
        return result({'unread_count':len(items),'items':[{'id':item['id'],'title':item['title'],'has_files':bool(item['files']),'updated_at':item['updated_at']}for item in items[:20]]})

    @router.get('/conversations')
    def conversations(before:str|None=Query(default=None,pattern=r'^[0-9a-f]{32}$'),user=Depends(actor),db=Depends(store)):
        return result(call(db.conversations,user,before))

    @router.get('/conversations/{rid}')
    def conversation(rid:str,before:str|None=Query(default=None,pattern=r'^[0-9a-f]{32}$'),user=Depends(actor),db=Depends(store)):
        value=call(db.conversation,user,rid,before);value['items']=[visible(item,user)for item in value['items']]
        return result(value)

    @router.post('/{rid}/read')
    def read_result(rid:str,body:ReadResult,user=Depends(actor),db=Depends(store)):
        item=visible(call(db.get,user,rid),user)
        if not item['source_access']or item.get('source')and item.get('review_phase')not in {'OWN','SHARED','RELEASED'}:raise HTTPException(404,'요청한 답변을 확인할 수 없습니다.')
        return result(visible(call(db.mark_read,user,rid,body.completion_token),user))

    @router.post('',status_code=201)
    def create(body:CreateRequest,user=Depends(actor),db=Depends(store)):
        source=None
        selection_id=body.form_file_id or body.nas_file_id
        if body.form_file_id and not config().registered_forms_enabled:raise HTTPException(404,'등록 양식 연결을 준비하고 있습니다.')
        if selection_id:
            if body.kind not in {'FILE','QUESTION','EDIT'}:raise HTTPException(422,'자료 요청 내용을 확인해 주세요.')
            replay=call(db.replay,user,body.request_key,body.kind,body.title,body.body,selection_id,body.parent_request_id,result_file_id=body.result_file_id)
            if replay is not None:
                response=result(visible(replay,user));response.status_code=201;return response
            source=call(db.selection,user,selection_id)
            if bool(body.form_file_id)!=(source.get('scope')==FORM_SCOPE):raise HTTPException(409,'선택한 원본의 저장 위치를 다시 확인해 주세요.')
            if not source_valid(user,source):raise HTTPException(409,'자료를 다시 찾아 선택해 주세요.')
        if body.kind=='EDIT'and source and source.get('extension')=='.xlsx'and not config().workbook_edit_enabled:raise HTTPException(404,'엑셀 문구 수정 사본을 준비하고 있습니다.')
        if body.kind=='EDIT'and(not source or source.get('extension')not in {'.txt','.docx','.xlsx'}):raise HTTPException(422,'수정할 TXT·DOCX·XLSX 원본을 선택해 주세요.')
        response=result(visible(call(db.create,user,body.request_key,body.kind,body.title,body.body,source,selection_id,body.parent_request_id,input_attachment_id=body.input_attachment_id,result_file_id=body.result_file_id,result_followup_enabled=config().owner_result_followup_enabled and config().source_lookup_enabled and user['owner'],image_comparison_enabled=config().image_source_comparison_enabled and config().source_lookup_enabled and config().nas_files_enabled),user));response.status_code=201;return response

    @router.get('/owner/inbox')
    def inbox(user=Depends(worker),db=Depends(store)):
        if not config().nas_files_enabled:return result({'enabled':False,'items':[]})
        eligible={(x['id'],x['login_id']):x for x in eligible_provider()};items=[]
        for item in call(db.inbox):
            requester=item.pop('_requester');person=eligible.get((requester['id'],requester['login_id']))
            item['requester_name']=(person.get('display_name')or'팀원')if person else'요청자 권한 확인 필요'
            ready=bool(person and source_valid(requester,item['source'])and source_valid(user,item['source']))
            item['source_available']=ready
            item['can_prepare']=ready and item['status']in {'AWAITING_REVIEW','NEEDS_INFO','INTERRUPTED'}
            item['can_release']=ready and item['review_phase']in {'READY','LEGACY_READY'}and item['status']in {'AWAITING_RELEASE','COMPLETED'}
            item['can_deny']=item['review_phase']not in {'OWN','SHARED','RELEASED','DENIED'}and item['status']not in {'CANCELLED','ACCESS_REVOKED'}
            if not file_access(item,user):item['files']=[]
            items.append(item)
        return result({'enabled':True,'items':items})

    @router.post('/owner/{rid}/prepare')
    def prepare_review(rid:str,body:ReviewVersion,user=Depends(worker),db=Depends(store)):
        require_nas_gate()
        return result(call(db.prepare_review,user,rid,body.review_version,body.source_sha256,eligible_provider(),source_valid))

    @router.post('/owner/{rid}/release')
    def release_original(rid:str,body:ReleaseFile,user=Depends(worker),db=Depends(store)):
        require_nas_gate()
        return result(call(db.release_original,user,rid,body.review_version,body.source_sha256,body.file_id,body.file_sha256,eligible_provider(),source_valid))

    @router.post('/owner/{rid}/deny')
    def deny_original(rid:str,body:DenyFile,user=Depends(worker),db=Depends(store)):
        require_nas_gate()
        return result(call(db.deny_original,user,rid,body.review_version,body.source_sha256,body.reason))

    @router.post('/worker/claim')
    def claim(body:WorkerCapabilities=Body(default=WorkerCapabilities()),user=Depends(worker),db=Depends(store)):
        capabilities=[c for c in body.capabilities if c in {'GENERATED_PDF_V1','UPLOADED_IMAGE_V1','OWNER_SOURCE_CHOICES_V1','OWNER_SOURCE_CHOICES_V2',FORM_CAP}or config().nas_files_enabled]
        if not config().registered_forms_enabled:capabilities=[c for c in capabilities if c!=FORM_CAP]
        if not config().source_generation_enabled:capabilities=[c for c in capabilities if c!='NAS_SOURCE_CREATE_V1']
        if not config().source_lookup_enabled:capabilities=[c for c in capabilities if c not in {'OWNER_SOURCE_CHOICES_V1','OWNER_SOURCE_CHOICES_V2'}]
        if not config().workbook_edit_enabled:capabilities=[c for c in capabilities if c!='NAS_WORKBOOK_EDIT_V1']
        if not config().owner_result_followup_enabled:capabilities=[c for c in capabilities if c!='OWNER_SOURCE_CHOICES_V2']
        if not (config().image_source_comparison_enabled and config().source_lookup_enabled and config().nas_files_enabled):capabilities=[c for c in capabilities if c!='UPLOADED_IMAGE_SOURCE_V1']
        from . import result_followup
        def result_validator(connection,row,who):return result_followup.validate(connection,db,who,row,config(),eligible_provider(),source_valid,retained_access=retained_result_access)
        item=call(db.claim,eligible_provider(),source_valid,capabilities,user,result_validator,image_comparison_enabled=config().image_source_comparison_enabled and config().source_lookup_enabled and config().nas_files_enabled)
        if item is not None:
            if config().image_source_comparison_enabled and 'UPLOADED_IMAGE_SOURCE_V1'in capabilities:
                with db.connection()as connection:
                    from .image_comparison import inputs,needs_source
                    row=connection.execute('SELECT * FROM requests WHERE id=?',(item['id'],)).fetchone();photos=inputs(connection,row)
                if photos:
                    item['input_attachments']=photos;item['image_source_comparison_available']=True
                    if not item.get('source')and needs_source(row['body']):item['source_lookup_available']=True;item['source_choices_available']=True
            from .grounding import answer, current_text, file_name_question
            def nas_answer_full(operation,limit,query=''):
                if not config().nas_files_enabled or nas is None:
                    return {'status':'NEEDS_INFO','reply':'NAS 검색 연결을 확인하지 못했습니다. 파일 목록을 다시 보내실 필요는 없습니다.'}
                try:
                    return nas.context_answer(item['_requester'],operation,limit,query=query) if query else nas.context_answer(item['_requester'],operation,limit)
                except Exception:
                    return {'status':'NEEDS_INFO','reply':'현재 계정의 NAS 검색 연결과 이용 권한을 확인해야 합니다. 파일 목록을 다시 보내실 필요는 없습니다.'}
            def nas_answer(operation,limit,query=''):
                value=nas_answer_full(operation,limit,query)
                return {'status':value['status'],'reply':value['reply']}
            requester={**item['_requester'],'owner':bool(item['scope_exempt'])}
            def file_names():
                with db.connection()as connection:
                    bound=result_followup.requested(connection,item['id'])
                    if bound and bound.get('selected_file_id'):
                        row=connection.execute('SELECT * FROM requests WHERE id=?',(item['id'],)).fetchone()
                        value=result_validator(connection,row,user)
                        return [value['file_name']]
                return call(db.conversation_file_names,requester,item['id'],visible,nas_answer_full)
            def ui_features():
                from .input_images import available
                return {'photos':available(db),'owner_pc_lookup':bool(item['scope_exempt']and config().source_lookup_enabled and {'OWNER_SOURCE_CHOICES_V1','OWNER_SOURCE_CHOICES_V2'}&set(capabilities))}
            with db.connection()as connection:selected_result=result_followup.requested(connection,item['id'])
            selected_name_question=bool(selected_result and selected_result.get('selected_file_id')and file_name_question('이 파일의 '+current_text(item['body'])))
            grounded_item={**item,'body':'이 파일의 '+current_text(item['body'])}if selected_name_question else item
            grounded=answer(grounded_item,nas_answer,file_names,ui_features,lambda:consent_context(requester,item['id']))if not item.get('input_attachments')else None
            if grounded is not None:item['grounded_reply']=grounded
            if config().source_lookup_enabled and config().nas_files_enabled and 'REQUEST_SOURCE_LOOKUP_V1'in capabilities and item['kind']=='QUESTION'and not item.get('source')and not item.get('input_attachments')and grounded is None:item['source_lookup_available']=True;item['source_choices_available']=True
        if item is not None and item['scope_exempt']and {'OWNER_SOURCE_CHOICES_V1','OWNER_SOURCE_CHOICES_V2'}&set(capabilities):
            from .owner_source_choices import state as owner_choice_state
            with db.connection()as connection:proposal,selected=owner_choice_state(connection,item['id'])
            if selected:item['owner_source_choice_id']=selected;item.pop('grounded_reply',None)
        if item is not None and 'OWNER_SOURCE_CHOICES_V2'in capabilities:
            with db.connection()as connection:
                # Account/index/UI questions keep their grounded response even when a
                # result remains selected. Explicit document references keep its source.
                selected_text=current_text(item['body'])
                independent_answer=grounded is not None and not(result_followup.REFERENCE.search(selected_text) or result_followup.natural_reference(selected_text))
                if result_followup.requested(connection,item['id']) and not (grounded is not None and (selected_name_question or file_name_question(selected_text) or independent_answer)):
                    row=connection.execute('SELECT * FROM requests WHERE id=?',(item['id'],)).fetchone();item['result_source']=result_validator(connection,row,user);item.pop('grounded_reply',None)
        return result({'item':item})

    @router.post('/worker/{rid}/heartbeat')
    def heartbeat(rid:str,body:Heartbeat,user=Depends(worker),db=Depends(store)):
        call(db.heartbeat,rid,body.lease,body.phase);return result({'ok':True})

    @router.post('/worker/{rid}/interrupt')
    def interrupt(rid:str,body:Lease,user=Depends(worker),db=Depends(store)):
        return result(call(db.interrupt,rid,body.lease))

    @router.post('/worker/{rid}/finish')
    async def finish(rid:str,lease:str=Form(...,min_length=64,max_length=64),
            status:Literal['COMPLETED','DECLINED','FAILED','NEEDS_INFO']=Form(...),
            reply:str=Form(...,min_length=1,max_length=12000),business_allowed:bool=Form(...),
            delivery_mode:Literal['RESULT','OWNER_PREVIEW']=Form('RESULT'),
            file:UploadFile|None=File(None),user=Depends(worker),db=Depends(store)):
        content=await file.read(MAX_ORIGINAL_BYTES+1) if file else None
        if file and len(content)>MAX_ORIGINAL_BYTES:raise HTTPException(413,'원본 자료는 32MB까지 보낼 수 있습니다.')
        from . import result_followup
        def result_validator(connection,row,who):return result_followup.validate(connection,db,who,row,config(),eligible_provider(),source_valid,retained_access=retained_result_access)
        return result(call(db.finish,rid,lease,status,reply,business_allowed,eligible_provider(),file.filename if file else None,content,source_valid,delivery_mode,user,result_validator))

    @router.get('/{rid}')
    def detail(rid:str,user=Depends(actor),db=Depends(store)):
        return result(visible(call(db.get,user,rid),user))

    @router.post('/{rid}/cancel')
    def cancel(rid:str,user=Depends(actor),db=Depends(store)):
        return result(call(db.cancel,user,rid))

    @router.get('/{rid}/files/{fid}')
    def download(rid:str,fid:str,user=Depends(actor),db=Depends(store)):
        item=call(db.get,user,rid)
        if not file_access(item,user):raise HTTPException(404,'원본 자료와 이용 권한을 확인해 주세요.')
        name,stream,size=call(db.download_stream,user,rid,fid)
        def chunks():
            try:
                while chunk:=stream.read(1024*1024):yield chunk
            finally:stream.close()
        return StreamingResponse(chunks(),background=BackgroundTask(stream.close),media_type='application/octet-stream',headers={
            'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe=''),
            'Content-Length':str(size),'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})

    from .naver_delivery import install as install_naver_delivery
    install_naver_delivery(router,actor,worker,store,config,eligible_provider,result,call)
    from .source_lookup import install as install_source_lookup
    install_source_lookup(router,worker,store,config,eligible_provider,nas,result,call)
    from .source_choices import install as install_source_choices
    install_source_choices(router,actor,worker,store,config,eligible_provider,nas,result,call)
    from .question_retry import install as install_question_retry
    install_question_retry(router,actor,store,config,eligible_provider,source_valid,result,call)
    from .owner_source_choices import install as install_owner_source_choices
    install_owner_source_choices(router,actor,worker,store,config,eligible_provider,result,call)

    from .result_followup import install as install_result_followup
    install_result_followup(router,worker,store,config,eligible_provider,source_valid,call,retained_access=retained_result_access)
    return router
