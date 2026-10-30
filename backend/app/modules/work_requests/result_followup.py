"""Explicit owner-self follow-up to one immutable result in the same conversation."""
import hashlib,json,re
from pathlib import PurePosixPath
from fastapi import Depends,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field
from .store import Conflict,MAX_ORIGINAL_BYTES
PREFIX='OWNER_RESULT_FOLLOWUP_V1:'
CAP='OWNER_SOURCE_CHOICES_V2'
EXTENSIONS={'.txt','.pdf','.docx','.xlsx','.pptx','.hwp','.hwpx','.csv'}
REFERENCE=re.compile(r'(?:방금\s*(?:만든|수정한|받은|작성한)?|[이그]\s*)\s*(?:파일|안내문|문서|자료|사본)')
class ReadResult(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 lease:str=Field(pattern=r'^[a-f0-9]{64}$')
 file_id:str=Field(pattern=r'^[a-f0-9]{32}$')

def requested(db,rid):
 row=db.execute('SELECT status FROM events WHERE request_id=? AND status LIKE ? ORDER BY id DESC LIMIT 1',(rid,PREFIX+'%')).fetchone()
 return json.loads(row['status'][len(PREFIX):])if row else None

def nearest_result(db,actor,row):
 from .input_images import for_request as image
 from .naver_delivery import for_request as delivery
 from .owner_source_choices import state
 parent_id=row['parent_request_id'];seen={row['id']};chain=[]
 for _ in range(12):
  if not parent_id or parent_id in seen:return None
  seen.add(parent_id);parent=db.execute('SELECT * FROM requests WHERE id=?',(parent_id,)).fetchone()
  if parent is None or(parent['user_id'],parent['login_id'])!=(actor['id'],actor['login_id'])or not parent['scope_exempt']or parent['conversation_id']!=row['conversation_id']or parent['review_phase']not in {'NONE','OWN','SHARED','RELEASED'}or parent['status']not in {'COMPLETED','NEEDS_INFO','ACCESS_REVOKED'}:return None
  chain.append({'id':parent['id'],'updated_at':parent['updated_at'],'body':parent['body']})
  all_files=db.execute('SELECT * FROM files WHERE request_id=?',(parent['id'],)).fetchall();files=[f for f in all_files if f['audience']=='REQUESTER']
  if files:
   return(parent,files,chain)if parent['status']=='COMPLETED'and len(files)==1 else None
  if all_files or parent['kind']!='QUESTION'or parent['source_json']or image(db,parent['id'])or delivery(db,parent['id'])is not None or state(db,parent['id'])[0]:return None
  parent_id=parent['parent_request_id']
 return None

def candidate(db,actor,row):
 if not actor['owner']or not row['scope_exempt']or row['kind']!='QUESTION'or not row['parent_request_id']or row['source_json']or not REFERENCE.search(row['body']):return None
 from .input_images import for_request as image
 from .naver_delivery import for_request as delivery
 if image(db,row['id'])or delivery(db,row['id'])is not None:return None
 resolved=nearest_result(db,actor,row)
 if resolved is None:return None
 parent,files,chain=resolved
 file=files[0]
 from .nas_sources import accident_source
 if not 0<file['bytes']<=MAX_ORIGINAL_BYTES or PurePosixPath(file['filename']).suffix.casefold()not in EXTENSIONS or accident_source(file['filename']):return None
 origin='RESULT';anchor=parent['id']
 if parent['source_json']:origin='NAS'
 else:
  from .owner_source_choices import state
  proposal,selected=state(db,parent['id'])
  if proposal and selected:
   matches=[i for i in proposal['items']if i['choice_id']==selected]
   if len(matches)!=1:return None
   origin=matches[0]['source']
  inherited=requested(db,parent['id'])
  if inherited:origin=inherited['origin'];anchor=inherited['origin_request_id']
 value={'request_id':parent['id'],'file_id':file['id'],'file_name':file['filename'],'bytes':file['bytes'],'sha256':file['sha256'],'origin':origin,'origin_request_id':anchor}
 if len(chain)>1:value['context_sha256']=hashlib.sha256(json.dumps(chain,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return value

def bind(db,queue,actor,rid):
 row=db.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();value=candidate(db,actor,row)
 if value:queue._event(db,rid,PREFIX+json.dumps(value,ensure_ascii=False,separators=(',',':')))

def validate(db,queue,user,row,cfg,eligible,source_valid,*,retained_access=None):
 if not cfg.enabled or not cfg.source_lookup_enabled or not cfg.owner_result_followup_enabled or not user['owner']or(user['id'],user['login_id'])!=cfg.owner:raise Conflict('RESULT_FOLLOWUP_DISABLED')
 if not any((p['id'],p['login_id'])==(user['id'],user['login_id'])and p['owner']for p in eligible):raise Conflict('OWNER_ACCESS_REVOKED')
 value=requested(db,row['id']);now=candidate(db,user,row)
 if value is None or value!=now:raise Conflict('RESULT_SOURCE_CHANGED')
 if value['origin']=='NAS'and not cfg.nas_files_enabled:raise Conflict('NAS_FILES_DISABLED')
 anchor=db.execute('SELECT * FROM requests WHERE id=?',(value['origin_request_id'],)).fetchone()
 if anchor is None or anchor['status']!='COMPLETED'or anchor['conversation_id']!=row['conversation_id']or(anchor['user_id'],anchor['login_id'])!=(user['id'],user['login_id']):raise Conflict('RESULT_ORIGIN_REVOKED')
 if anchor['source_json']:
  from .nas_sources import accident_source
  if accident_source(json.loads(anchor['source_json']).get('relative_path','')):raise Conflict('SOURCE_ACCESS_REVOKED')
  # This is an already delivered, hash-pinned private result, not a new NAS read.
  # Reuse the same access gate as its existing download endpoint.
  allowed=retained_access(user,anchor)if retained_access is not None else source_valid(user,json.loads(anchor['source_json']))
  if not allowed:raise Conflict('SOURCE_ACCESS_REVOKED')
 return {k:v for k,v in value.items()if k not in {'origin','origin_request_id'}}

def install(router,worker,store,config,eligible,source_valid,call,*,retained_access=None):
 @router.post('/worker/{rid}/input-result')
 def read_result(rid:str,body:ReadResult,user=Depends(worker),queue=Depends(store)):
  def checked():
   with queue.connection()as db:
    row=queue._lease(db,rid,body.lease)
    value=validate(db,queue,user,row,config(),eligible(),source_valid,retained_access=retained_access)
    if value['file_id']!=body.file_id:raise Conflict('EXACT_RESULT_REQUIRED')
    return value
  value=call(checked);name,data=call(queue.download,user,value['request_id'],value['file_id'])
  if call(checked)!=value or name!=value['file_name']or len(data)!=value['bytes']:raise HTTPException(409,'결과 파일 상태를 다시 확인해 주세요.')
  return Response(data,media_type='application/octet-stream',headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
