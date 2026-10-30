"""Explicit retry of an interrupted read-only question, using the same request."""
import hashlib,json
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from .store import Conflict

class RetryQuestion(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 review_version:int=Field(ge=0)
 retry_key:str=Field(pattern=r'^[a-f0-9]{32}$')

SOURCE_READ_FAILED_REPLY='NAS 연결과 원본 자료가 변경되었는지 확인해 주세요.'

def retryable(row,delivery,has_files,*,source_generation=False):
 question=(row['kind']=='QUESTION'and row['status']=='INTERRUPTED'
           and ((not row['source_json']and row['review_phase']=='NONE')
                or(row['source_json']and row['review_phase']in {'OWN','SHARED'})))
 original=(row['kind']=='FILE'and row['source_json']and row['review_phase']in {'OWN','SHARED'}
           and (row['status']=='INTERRUPTED'or row['status']=='NEEDS_INFO'and row['reply']==SOURCE_READ_FAILED_REPLY))
 return bool((question or original)and not source_generation and not row['preview_file_id']and not has_files and delivery is None)

def install(router,actor,store,config,eligible,source_valid,result,call):
 def retry(db,user,rid,body):
  marker='QUESTION_RETRY_V1:'+hashlib.sha256(json.dumps([user['id'],user['login_id'],body.review_version,body.retry_key],separators=(',',':')).encode()).hexdigest()
  def row_and_source(connection):
   row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
   if row is None or(row['user_id'],row['login_id'])!=(user['id'],user['login_id']):raise KeyError('NOT_FOUND')
   return row,json.loads(row['source_json'])if row['source_json']else None
  def account():
   if not config().enabled:raise HTTPException(404,'질문 처리를 준비하고 있습니다.')
   people={(u['id'],u['login_id']):bool(u['owner'])for u in eligible()};pair=(user['id'],user['login_id'])
   if pair not in people:raise Conflict('REQUESTER_ACCESS_REVOKED')
   return people[pair]
  def check(connection,row,source,is_owner):
   from .naver_delivery import for_request
   files=connection.execute('SELECT 1 FROM files WHERE request_id=? LIMIT 1',(rid,)).fetchone()
   from .source_generation import requested
   if row['review_version']!=body.review_version or not retryable(row,for_request(connection,rid),bool(files),source_generation=requested(connection,row)is not None):raise Conflict('QUESTION_RETRY_NOT_AVAILABLE')
   if source and(row['review_phase']=='OWN'and not is_owner or row['review_phase']=='SHARED'and not(source.get('shared_file_id')and source.get('approved_content_sha256'))):raise Conflict('SOURCE_GRANT_CHANGED')
   if source and not source_valid(user,source):raise Conflict('SOURCE_CHANGED')
  is_owner=account()
  with db.connection()as connection:
   row,source=row_and_source(connection)
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   check(connection,row,source,is_owner)
  with db.connection()as connection,connection:
   connection.execute('BEGIN IMMEDIATE');is_owner=account();row,source=row_and_source(connection)
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():return {'id':rid,'acknowledged':True}
   check(connection,row,source,is_owner)
   if row['kind']=='FILE':
    evidence={'status':row['status'],'review_version':row['review_version'],'reply_sha256':hashlib.sha256(row['reply'].encode()).hexdigest()}
    if row['reply']==SOURCE_READ_FAILED_REPLY:evidence['reply']=SOURCE_READ_FAILED_REPLY
    db._event(connection,rid,'ORIGINAL_READ_RETRY_V1:'+json.dumps(evidence,separators=(',',':')))
   connection.execute("UPDATE requests SET status='QUEUED',reply='',review_version=review_version+1,lease_hash=NULL,lease_until=NULL,updated_at=? WHERE id=?",(db.clock(),rid))
   db._event(connection,rid,marker);db._event(connection,rid,'QUEUED')
  return {'id':rid,'acknowledged':True}

 @router.post('/{rid}/retry-question')
 def retry_question(rid:str,body:RetryQuestion,user=Depends(actor),db=Depends(store)):
  return result(call(retry,db,user,rid,body))
