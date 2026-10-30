"""Owner-self metadata choices. All actual references and private paths stay on PC."""
import json,hashlib,re,unicodedata
from pathlib import PurePosixPath
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from .store import Conflict
PREFIX='OWNER_CHOICES_V1:';SELECTED='OWNER_CHOICE_SELECTED_V1:';CLEARED='OWNER_CHOICES_CLEARED'
class Meta(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 choice_id:str=Field(pattern=r'^[a-f0-9]{64}$')
 source:Literal['NAS','PC']
 file_name:str=Field(min_length=1,max_length=255)
 root_label:str=Field(min_length=1,max_length=100)
 relative_path:str=Field(min_length=1,max_length=2048)
 modified_at:str|None=Field(default=None,max_length=80)
 index_uncertain:bool
 @field_validator('file_name','root_label')
 @classmethod
 def leaf(cls,v):
  if any(c in v for c in '\\/:')or any(ord(c)<32 for c in v)or v in {'.','..'}:raise ValueError('EXACT_DISPLAY_NAME_REQUIRED')
  return v
 @field_validator('relative_path')
 @classmethod
 def relative(cls,v):
  if '\\'in v or':'in v or any(ord(c)<32 for c in v)or PurePosixPath(v).is_absolute()or'..'in PurePosixPath(v).parts or PurePosixPath(v).as_posix()!=v:raise ValueError('RELATIVE_METADATA_REQUIRED')
  return v
 @model_validator(mode='after')
 def identity(self):
  key=lambda v:unicodedata.normalize('NFC',v).casefold()
  if key(self.file_name)!=key(PurePosixPath(self.relative_path).name):raise ValueError('EXACT_METADATA_IDENTITY_REQUIRED')
  return self
class Proposal(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 lease:str=Field(pattern=r'^[a-f0-9]{64}$')
 items:list[Meta]=Field(min_length=1,max_length=5)
class Choose(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 review_version:int=Field(ge=0)
 choice_id:str=Field(pattern=r'^[a-f0-9]{64}$')
class Refresh(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 review_version:int=Field(ge=0)

def state(db,rid):
 rows=db.execute("SELECT status FROM events WHERE request_id=? AND (status LIKE 'OWNER_CHOICES_V1:%' OR status LIKE 'OWNER_CHOICE_SELECTED_V1:%' OR status=?) ORDER BY id DESC",(rid,CLEARED)).fetchall()
 selected=None
 for row in rows:
  value=row['status']
  if value==CLEARED:return None,None
  if value.startswith(SELECTED)and selected is None:selected=value[len(SELECTED):]
  if value.startswith(PREFIX):return json.loads(value[len(PREFIX):]),selected
 return None,None
def flow_started(db,rid):return db.execute("SELECT 1 FROM events WHERE request_id=? AND status LIKE 'OWNER_CHOICES_V1:%' LIMIT 1",(rid,)).fetchone()is not None

def install(router,actor,worker,store,config,eligible,result,call):
 def gate(user):
  cfg=config()
  if not cfg.enabled or not cfg.source_lookup_enabled or not user.get('owner')or(user['id'],user['login_id'])!=cfg.owner:raise HTTPException(404,'자료 선택 연결을 준비하고 있습니다.')
  if not any(u['id']==user['id']and u['login_id']==user['login_id']and u['owner']for u in eligible()):raise Conflict('OWNER_ACCESS_REVOKED')
 def row_for(db,user,rid):
  row=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
  if row is None or(row['user_id'],row['login_id'])!=(user['id'],user['login_id']):raise KeyError('NOT_FOUND')
  return row
 def applicable(db,row):
  from .input_images import for_request
  from .naver_delivery import for_request as delivery
  if row['kind']!='QUESTION'or row['source_json']or row['preview_file_id']or for_request(db,row['id'])or delivery(db,row['id'])is not None or db.execute('SELECT 1 FROM files WHERE request_id=? LIMIT 1',(row['id'],)).fetchone():raise Conflict('OWNER_CHOICES_NOT_APPLICABLE')
 def propose(queue,user,rid,body):
  ids=[i.choice_id for i in body.items]
  if len(set(ids))!=len(ids):raise ValueError('UNIQUE_OWNER_CHOICES_REQUIRED')
  from .nas_sources import accident_source
  if any(accident_source(i.relative_path)for i in body.items):raise ValueError('ACCIDENT_SOURCE_EXCLUDED')
  if any(i.source=='NAS'for i in body.items)and not config().nas_files_enabled:raise Conflict('NAS_FILES_DISABLED')
  marker='OWNER_CHOICES_PROPOSED:'+hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest()
  with queue.connection()as db,db:
   db.execute('BEGIN IMMEDIATE');gate(user);row=row_for(db,user,rid)
   if db.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   queue._lease(db,rid,body.lease);applicable(db,row)
   if not row['scope_exempt']:raise Conflict('OWNER_REQUEST_REQUIRED')
   value={'items':[i.model_dump()for i in body.items],'expires_at':queue.clock()+3600}
   db.execute("UPDATE requests SET status='NEEDS_INFO',reply=?,review_version=review_version+1,lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",('사용할 자료를 선택해 주세요. 수정시각만으로 최신 승인본을 확정하지 않습니다.',queue.clock(),rid))
   queue._event(db,rid,PREFIX+json.dumps(value,ensure_ascii=False,separators=(',',':')));queue._event(db,rid,marker)
  return {'id':rid,'acknowledged':True}
 def listed(queue,user,rid):
  with queue.connection()as db:
   row=row_for(db,user,rid);proposal,selected=state(db,rid);items=[]
   if row['status']=='NEEDS_INFO'and proposal and selected is None and proposal['expires_at']>=queue.clock():items=[i for i in proposal['items']if i['source']=='PC'or config().nas_files_enabled]
   return {'id':rid,'items':items,'review_version':row['review_version'],'refreshable':row['status']=='NEEDS_INFO'and bool(proposal),'approval_unconfirmed':True}
 def choose(queue,user,rid,body):
  marker='OWNER_CHOICE_RECEIPT:'+hashlib.sha256(json.dumps([body.review_version,body.choice_id]).encode()).hexdigest()
  with queue.connection()as db,db:
   db.execute('BEGIN IMMEDIATE');gate(user);row=row_for(db,user,rid)
   if db.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   applicable(db,row);proposal,selected=state(db,rid)
   if row['status']!='NEEDS_INFO'or row['review_version']!=body.review_version or not proposal or selected or proposal['expires_at']<queue.clock():raise Conflict('OWNER_CHOICES_CHANGED')
   matches=[i for i in proposal['items']if i['choice_id']==body.choice_id]
   if len(matches)!=1 or matches[0]['source']=='NAS'and not config().nas_files_enabled:raise Conflict('OWNER_SOURCE_CHANGED')
   db.execute("UPDATE requests SET status='QUEUED',reply='',review_version=review_version+1,lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(queue.clock(),rid));queue._event(db,rid,SELECTED+body.choice_id);queue._event(db,rid,marker);queue._event(db,rid,'QUEUED')
  return {'id':rid,'acknowledged':True}
 def refresh(queue,user,rid,body):
  marker='OWNER_CHOICES_REFRESHED:'+str(body.review_version)
  with queue.connection()as db,db:
   db.execute('BEGIN IMMEDIATE');gate(user);row=row_for(db,user,rid)
   if db.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   applicable(db,row);proposal,selected=state(db,rid)
   if row['status']!='NEEDS_INFO'or row['review_version']!=body.review_version or not proposal:raise Conflict('OWNER_CHOICES_CHANGED')
   db.execute("UPDATE requests SET status='QUEUED',reply='',review_version=review_version+1,lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(queue.clock(),rid));queue._event(db,rid,CLEARED);queue._event(db,rid,marker);queue._event(db,rid,'QUEUED')
  return {'id':rid,'acknowledged':True}
 @router.post('/worker/{rid}/owner-source-choices')
 def proposed(rid:str,body:Proposal,user=Depends(worker),db=Depends(store)):
  gate(user);return result(call(propose,db,user,rid,body))
 @router.get('/{rid}/owner-source-choices')
 def choices(rid:str,user=Depends(actor),db=Depends(store)):
  gate(user);return result(call(listed,db,user,rid))
 @router.post('/{rid}/owner-source-choice')
 def selected(rid:str,body:Choose,user=Depends(actor),db=Depends(store)):
  gate(user);return result(call(choose,db,user,rid,body))
 @router.post('/{rid}/owner-source-choices/refresh')
 def refreshed(rid:str,body:Refresh,user=Depends(actor),db=Depends(store)):
  gate(user);return result(call(refresh,db,user,rid,body))
