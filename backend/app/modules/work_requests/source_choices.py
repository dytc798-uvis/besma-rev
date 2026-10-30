"""Request-bound metadata choices. Existing private event/selection ledger only."""
import hashlib,json
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from .source_lookup import LookupLease
from .store import Conflict
from .nas_sources import accident_source
PREFIX='SOURCE_CHOICES_V1:'
class Choices(LookupLease):
 selection_ids:list[str]=Field(min_length=1,max_length=5)
 action:Literal['QUESTION','FIND','EDIT','CREATE']='QUESTION'
 output_format:Literal['TXT','PDF']='TXT'
 artifact_title:str|None=Field(default=None,min_length=1,max_length=80)
class Choice(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 review_version:int=Field(ge=1)
 selection_id:str=Field(pattern=r'^[a-f0-9]{64}$')
class Refresh(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 review_version:int=Field(ge=1)

def pending(connection,rid):
 row=connection.execute("SELECT status FROM events WHERE request_id=? AND (status LIKE 'SOURCE_CHOICES_V1:%' OR status='SOURCE_CHOICES_CLEARED') ORDER BY id DESC LIMIT 1",(rid,)).fetchone()
 return json.loads(row['status'][len(PREFIX):])if row and row['status'].startswith(PREFIX)else None

def install(router,actor,worker,store,config,eligible,nas,result,call):
 def gate():
  cfg=config()
  if not cfg.source_lookup_enabled or not cfg.nas_files_enabled or nas is None:raise HTTPException(404,'자료 선택 연결을 준비하고 있습니다.')
 def identity(row):
  members={(u['id'],u['login_id']):bool(u['owner'])for u in eligible()};key=(row['user_id'],row['login_id'])
  if key not in members:raise Conflict('REQUESTER_ACCESS_REVOKED')
  value={'id':key[0],'login_id':key[1],'owner':members[key]}
  if not nas.member_valid(value):raise Conflict('REQUESTER_SOURCE_ACCESS_REVOKED')
  return value
 def checked_source(db,who,selection_id,action):
  value=nas.validate(who,db.selection(who,selection_id))
  if value.get('scope')!='TEAM_SAFETY_NAS'or value.get('logical_root_id')!='team-safety-nas-z4'or accident_source(value.get('relative_path','')):raise Conflict('SOURCE_NOT_ALLOWED')
  if action=='EDIT'and value.get('extension')not in {'.txt','.docx','.xlsx'}:raise Conflict('EDIT_COPY_FORMAT_REQUIRED')
  if action=='EDIT'and value.get('extension')=='.xlsx'and not config().workbook_edit_enabled:raise Conflict('WORKBOOK_EDIT_DISABLED')
  if action=='CREATE'and not config().source_generation_enabled:raise Conflict('SOURCE_GENERATION_DISABLED')
  return value
 def propose(db,rid,body):
  ids=body.selection_ids
  import re,unicodedata
  if len(set(ids))!=len(ids)or any(not re.fullmatch(r'[a-f0-9]{64}',s)for s in ids):raise ValueError('EXACT_SELECTIONS_REQUIRED')
  title=unicodedata.normalize('NFC',body.artifact_title or '').strip()
  if body.action=='CREATE'and(not title or any(ord(c)<32 for c in title)):raise ValueError('DOCUMENT_TITLE_REQUIRED')
  if body.action!='CREATE'and(body.output_format!='TXT'or body.artifact_title is not None):raise ValueError('QUESTION_OUTPUT_INVALID')
  marker='SOURCE_CHOICES_PROPOSED:'+hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest()
  with db.connection()as connection:
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   row=db._lease(connection,rid,body.lease);who=identity(row)
   from .input_images import for_request
   from .image_comparison import require_lookup
   require_lookup(config(),connection,row,body.action)
   if row['kind']!='QUESTION'or row['source_json']:raise Conflict('REQUEST_CHANGED')
  for sid in ids:checked_source(db,who,sid,body.action)
  value={'ids':ids,'action':body.action,'output_format':body.output_format,'artifact_title':title if body.action=='CREATE'else None}
  with db.connection()as connection,connection:
   connection.execute('BEGIN IMMEDIATE')
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   gate();row=db._lease(connection,rid,body.lease);identity(row)
   from .image_comparison import require_lookup
   require_lookup(config(),connection,row,body.action)
   for sid in ids:
    candidate_source=db.selection(who,sid)
    if not nas.valid(who,candidate_source):raise Conflict('SOURCE_CHANGED')
   if body.action=='CREATE'and not config().source_generation_enabled:raise Conflict('SOURCE_GENERATION_DISABLED')
   if body.action=='EDIT'and any(db.selection(who,sid).get('extension')=='.xlsx'for sid in ids)and not config().workbook_edit_enabled:raise Conflict('WORKBOOK_EDIT_DISABLED')
   if row['kind']!='QUESTION'or row['source_json']:raise Conflict('REQUEST_CHANGED')
   connection.execute("UPDATE requests SET status='NEEDS_INFO',reply=?,review_version=review_version+1,lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",('사용할 자료를 선택해 주세요. 수정시각만으로 최신 승인본을 확정하지 않습니다.',db.clock(),rid))
   db._event(connection,rid,PREFIX+json.dumps(value,ensure_ascii=False,separators=(',',':')));db._event(connection,rid,marker)
  return {'id':rid,'acknowledged':True}
 def owned(db,user,rid):
  db.get(user,rid)
  with db.connection()as connection:
   row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
   if (row['user_id'],row['login_id'])!=(user['id'],user['login_id']):raise KeyError('NOT_FOUND')
   who=identity(row);p=pending(connection,rid)
  return row,who,p
 def list_choices(db,user,rid):
  row,who,p=owned(db,user,rid);items=[]
  if row['status']=='NEEDS_INFO'and p:
   for sid in p['ids']:
    try:
     value=checked_source(db,who,sid,p['action']);items.append({k:value[k]for k in ['file_name','relative_path','extension','size','modified_at']}|{'selection_id':sid})
    except (KeyError,ValueError,Conflict,HTTPException):continue
  # Recheck account and state after metadata validation. Never show stale choices after selection.
  latest,current_who,current=owned(db,user,rid)
  if latest['status']!='NEEDS_INFO'or latest['review_version']!=row['review_version']or current!=p:items=[]
  return {'id':rid,'review_version':latest['review_version'],'items':items,'refreshable':latest['status']=='NEEDS_INFO'and bool(current),'approval_unconfirmed':True}
 def select(db,user,rid,body):
  marker='SOURCE_CHOICES_SELECTED:'+hashlib.sha256(json.dumps([body.review_version,body.selection_id]).encode()).hexdigest()
  row,who,p=owned(db,user,rid)
  with db.connection()as connection:
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
  if not p or row['status']!='NEEDS_INFO'or row['review_version']!=body.review_version or body.selection_id not in p['ids']:raise Conflict('SOURCE_CHOICES_CHANGED')
  selected=checked_source(db,who,body.selection_id,p['action'])
  with db.connection()as connection,connection:
   connection.execute('BEGIN IMMEDIATE');gate()
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();who=identity(row)
   if (row['user_id'],row['login_id'])!=(user['id'],user['login_id'])or row['status']!='NEEDS_INFO'or row['review_version']!=body.review_version or pending(connection,rid)!=p:raise Conflict('SOURCE_CHOICES_CHANGED')
   from .image_comparison import require_lookup
   comparison_photos=require_lookup(config(),connection,row,p['action'])
   if not nas.valid(who,selected):raise Conflict('SOURCE_CHANGED')
   if p['action']=='EDIT'and selected.get('extension')=='.xlsx'and not config().workbook_edit_enabled:raise Conflict('WORKBOOK_EDIT_DISABLED')
   if p['action']=='CREATE'and not config().source_generation_enabled:raise Conflict('SOURCE_GENERATION_DISABLED')
   kind='EDIT'if p['action']=='EDIT'else'FILE'if p['action']in {'CREATE','FIND'}else'QUESTION'
   phase='OWN'if who['owner']else'SHARED'if p['action']in {'QUESTION','FIND'}and selected.get('shared_file_id')and selected.get('approved_content_sha256')else'WAITING_REVIEW'
   target='AWAITING_REVIEW'if phase=='WAITING_REVIEW'else'QUEUED';title=p['artifact_title']if p['action']=='CREATE'else row['title']
   connection.execute('UPDATE requests SET kind=?,title=?,source_json=?,selection_id=?,status=?,reply=?,review_phase=?,review_version=review_version+1,scope_exempt=?,updated_at=? WHERE id=?',(kind,title,json.dumps(selected,ensure_ascii=False,sort_keys=True),body.selection_id,target,'원문 확인을 기다리고 있습니다.'if phase=='WAITING_REVIEW'else'',phase,int(who['owner']),db.clock(),rid))
   if comparison_photos:db._event(connection,rid,'IMAGE_COMPARISON_BOUND')
   db._event(connection,rid,marker);db._event(connection,rid,'LOOKUP_ACTION_'+p['action']+(':'+p['output_format']if p['action']=='CREATE'else''));db._event(connection,rid,'SOURCE_CHOICES_CLEARED');db._event(connection,rid,target)
  return {'id':rid,'acknowledged':True}
 def refresh(db,user,rid,body):
  row,who,p=owned(db,user,rid)
  marker='SOURCE_CHOICES_REFRESHED:'+str(body.review_version)
  with db.connection()as connection,connection:
   connection.execute('BEGIN IMMEDIATE');gate();row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();identity(row)
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   if (row['user_id'],row['login_id'])!=(user['id'],user['login_id'])or row['status']!='NEEDS_INFO'or row['review_version']!=body.review_version or not pending(connection,rid):raise Conflict('SOURCE_CHOICES_CHANGED')
   connection.execute("UPDATE requests SET status='QUEUED',reply='',review_version=review_version+1,updated_at=? WHERE id=?",(db.clock(),rid));db._event(connection,rid,marker);db._event(connection,rid,'SOURCE_CHOICES_CLEARED');db._event(connection,rid,'QUEUED')
  return {'id':rid,'acknowledged':True}
 @router.post('/worker/{rid}/lookup-choices')
 def proposed(rid:str,body:Choices,user=Depends(worker),db=Depends(store)):
  gate();return result(call(propose,db,rid,body))
 @router.get('/{rid}/source-choices')
 def choices(rid:str,user=Depends(actor),db=Depends(store)):
  gate();return result(call(list_choices,db,user,rid))
 @router.post('/{rid}/source-choice')
 def chosen(rid:str,body:Choice,user=Depends(actor),db=Depends(store)):
  gate();return result(call(select,db,user,rid,body))
 @router.post('/{rid}/source-choices/refresh')
 def refreshed(rid:str,body:Refresh,user=Depends(actor),db=Depends(store)):
  gate();return result(call(refresh,db,user,rid,body))
