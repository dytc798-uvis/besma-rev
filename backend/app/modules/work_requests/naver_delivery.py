"""Explicit, owner-to-self NAVERWORKS deliveries. A prepared file is not a sent file."""
import hashlib,json,re
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel,ConfigDict,Field
from fastapi import Depends,HTTPException
from .store import Conflict

def ready(db):return db.execute("SELECT 1 FROM sqlite_master WHERE type='table'AND name='naver_deliveries_v1'").fetchone()is not None
def upgrade(store):
 with store.connection()as db,db:db.execute('''CREATE TABLE IF NOT EXISTS naver_deliveries_v1(
 request_id TEXT PRIMARY KEY REFERENCES requests(id),recipient TEXT NOT NULL,query TEXT NOT NULL,
 phase TEXT NOT NULL,lease_hash TEXT,lease_until REAL,file_json TEXT,receipt_json TEXT,
 created_at REAL NOT NULL,updated_at REAL NOT NULL)''')
def parse(text):
 if not isinstance(text,str)or len(text)>6000:return None
 if re.search(r'보내지|전송하지|전달하지|보내면|보낼까|예를\s*들|라고\s*(?:하면|묻)',text):return None
 if not re.search(r'(?:정상익\s*(?:차장)?\s*(?:님)?(?:에게|한테)|나에게)',text):return None
 if not re.search(r'보내|전송|전달',text)or not re.search(r'나스|NAS',text,re.I):return None
 if not re.search(r'안전(?:보건)?\s*관리\s*계획서?',text):return None
 if not re.search(r'최신|최근|마지막',text):return None
 return {'recipient':'정상익','query':'안전관리계획서','latest_by':'modified_at'}
def validate(actor,value,kind,source,photo,completed):
 if value is None:return
 if not actor.get('owner')or value!={'recipient':'정상익','query':'안전관리계획서','latest_by':'modified_at'}or kind!='FILE'or source or photo or completed is not None:raise ValueError('INVALID_NAVER_DELIVERY')
def bind(db,store,value,rid):
 if value is None:return
 if not ready(db):raise RuntimeError('DELIVERY_NOT_INITIALIZED')
 db.execute('INSERT INTO naver_deliveries_v1(request_id,recipient,query,phase,created_at,updated_at)VALUES(?,?,?,?,?,?)',(rid,value['recipient'],value['query'],'WAITING',store.clock(),store.clock()))
def for_request(db,rid):
 if not ready(db):return None
 r=db.execute('SELECT recipient,phase,file_json FROM naver_deliveries_v1 WHERE request_id=?',(rid,)).fetchone()
 return {'recipient':r['recipient'],'phase':r['phase'],'file':json.loads(r['file_json'])if r['file_json']else None}if r else None

def expire(db,store):
 if not ready(db):return
 now=store.clock()
 rows=db.execute("SELECT d.request_id,r.status FROM naver_deliveries_v1 d JOIN requests r ON r.id=d.request_id WHERE d.phase IN ('CLAIMED','READY','SENDING')AND(d.lease_until<? OR r.status!='RUNNING')",(now,)).fetchall()
 for row in rows:
  phase='UNKNOWN'if row['status']=='RUNNING'else'CANCELLED'
  db.execute('UPDATE naver_deliveries_v1 SET phase=?,updated_at=? WHERE request_id=?',(phase,now,row['request_id']))
  if phase=='UNKNOWN':
   db.execute("UPDATE requests SET status='NEEDS_INFO',reply=?,updated_at=? WHERE id=?",('전송 결과를 확인해야 합니다. 중복 전송을 막기 위해 자동으로 다시 보내지 않습니다.',now,row['request_id']))
   store._event(db,row['request_id'],'DELIVERY_UNKNOWN')

def checked_file(f):
 if not isinstance(f,dict)or set(f)!={'filename','relative_path','bytes','sha256','modified_at'}:raise ValueError('INVALID_FILE')
 name,path,stamp=f['filename'],f['relative_path'],f['modified_at']
 if not isinstance(name,str)or not 1<=len(name)<=240 or name in {'.','..'}or name.startswith('.')or re.search(r'[\\/:\x00-\x1f]',name):raise ValueError('INVALID_FILE')
 if not isinstance(path,str)or not 1<=len(path)<=1500 or re.search(r'[:\x00-\x1f]',path)or path.startswith(('/','\\')):raise ValueError('INVALID_PATH')
 parts=path.replace('\\','/').split('/')
 if any(p in {'','.','..'}for p in parts)or parts[-1]!=name:raise ValueError('INVALID_PATH')
 if type(f['bytes'])is not int or not 0<f['bytes']<=64*1024*1024 or not isinstance(f['sha256'],str)or not re.fullmatch('[0-9a-f]{64}',f['sha256']):raise ValueError('INVALID_FILE')
 if not isinstance(stamp,str)or len(stamp)>40:raise ValueError('INVALID_STAMP')
 if datetime.fromisoformat(stamp).tzinfo is None:raise ValueError('INVALID_STAMP')
 return f

class NewDelivery(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 request_key:str=Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')
 body:str=Field(min_length=1,max_length=6000)
 parent_request_id:str|None=Field(default=None,pattern=r'^[0-9a-f]{32}$')
class UpdateDelivery(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 lease:str=Field(pattern=r'^[0-9a-f]{64}$')
 phase:str=Field(pattern=r'^(HEARTBEAT|READY|SENDING|SENT|FAILED|UNKNOWN)$')
 file:dict|None=None
 receipt:dict|None=None

def install(router,actor,worker,store,config,eligible,result,call):
 def enabled(user):
  if not config().naver_delivery_enabled or not user['owner']:raise HTTPException(404,'네이버웍스 전달을 준비하고 있습니다.')
 def current(user):
  enabled(user)
  if not any(a['id']==user['id']and a['login_id']==user['login_id']and a['owner']for a in eligible()):raise HTTPException(404,'현재 계정으로 다시 확인해 주세요.')
 @router.post('/naver-deliveries',status_code=201)
 def create_delivery(body:NewDelivery,user=Depends(actor),db=Depends(store)):
  current(user);intent=parse(body.body)
  if not intent:raise HTTPException(422,'받는 사람과 보낼 자료를 확인해 주세요.')
  value=call(db.create,user,body.request_key,'FILE','네이버웍스 파일 전달',body.body,parent_request_id=body.parent_request_id,delivery=intent)
  response=result(value);response.status_code=201;return response
 @router.post('/worker/naver-deliveries/claim')
 def claim_delivery(user=Depends(worker),store=Depends(store)):
  current(user)
  with store.connection()as db,db:
   db.execute('BEGIN IMMEDIATE')
   if not ready(db):raise HTTPException(503,'파일 전달을 준비하고 있습니다.')
   expire(db,store)
   row=db.execute("SELECT d.* FROM naver_deliveries_v1 d JOIN requests r ON r.id=d.request_id WHERE d.phase='WAITING' AND r.status='QUEUED'AND r.user_id=? AND r.login_id=? AND NOT EXISTS(SELECT 1 FROM requests p WHERE p.id=r.parent_request_id AND p.status IN ('QUEUED','RUNNING','AWAITING_REVIEW','AWAITING_RELEASE')) ORDER BY d.created_at LIMIT 1",(user['id'],user['login_id'])).fetchone()
   if row is None:return result({'item':None})
   lease=uuid4().hex+uuid4().hex;now=store.clock()
   db.execute("UPDATE naver_deliveries_v1 SET phase='CLAIMED',lease_hash=?,lease_until=?,updated_at=? WHERE request_id=?",(hashlib.sha256(lease.encode()).hexdigest(),now+180,now,row['request_id']))
   db.execute("UPDATE requests SET status='RUNNING',reply=?,updated_at=? WHERE id=?",('NAS에서 수정일이 가장 최근인 안전관리계획서를 확인하고 있습니다.',now,row['request_id']));store._event(db,row['request_id'],'DELIVERY_CLAIMED')
   return result({'item':{'id':row['request_id'],'lease':lease,'recipient':'정상익','query':'안전관리계획서','latest_by':'modified_at','message_prefix':'BESMA가 보낸 파일입니다.'}})
 @router.post('/worker/naver-deliveries/{rid}')
 def update_delivery(rid:str,body:UpdateDelivery,user=Depends(worker),store=Depends(store)):
  current(user)
  with store.connection()as db,db:
   db.execute('BEGIN IMMEDIATE');r=db.execute('SELECT d.*,q.user_id,q.login_id,q.status AS request_status FROM naver_deliveries_v1 d JOIN requests q ON q.id=d.request_id WHERE request_id=?',(rid,)).fetchone()
   if r is None or(r['user_id'],r['login_id'])!=(user['id'],user['login_id']):raise HTTPException(404,'요청을 찾지 못했습니다.')
   if r['lease_hash']!=hashlib.sha256(body.lease.encode()).hexdigest():raise HTTPException(409,'전송 상태를 다시 확인해 주세요.')
   if r['phase']=='SENT'and r['request_status']=='COMPLETED'and body.phase=='SENT'and json.loads(r['receipt_json'])==body.receipt:return result({'ok':True,'phase':'SENT'})
   if r['request_status']!='RUNNING' or r['lease_until']<store.clock():raise HTTPException(409,'전송 상태를 다시 확인해 주세요.')
   if body.phase=='HEARTBEAT':
    if r['phase']not in {'CLAIMED','READY','SENDING'}:raise HTTPException(409,'전송 상태가 바뀌었습니다.')
    db.execute('UPDATE naver_deliveries_v1 SET lease_until=? WHERE request_id=?',(store.clock()+180,rid));return result({'ok':True,'phase':r['phase']})
   allowed={'READY':{'CLAIMED'},'SENDING':{'READY'},'SENT':{'SENDING'},'FAILED':{'CLAIMED','READY'},'UNKNOWN':{'CLAIMED','READY','SENDING'}}
   if r['phase']not in allowed[body.phase]:raise HTTPException(409,'전송 상태가 바뀌었습니다.')
   file=json.loads(r['file_json'])if r['file_json']else None
   if body.phase=='READY':
    try:file=checked_file(body.file)
    except (ValueError,TypeError,OverflowError):raise HTTPException(422,'원본 파일을 확인해 주세요.')from None
   if body.phase=='SENT':
    if body.receipt!={'recipient':'정상익','source_sha256':file['sha256'],'filename':file['filename'],'prefix':'BESMA가 보낸 파일입니다.','ui_file_observed':True}:raise HTTPException(422,'실제 전송 결과를 확인해 주세요.')
   now=store.clock();db.execute('UPDATE naver_deliveries_v1 SET phase=?,file_json=?,receipt_json=?,updated_at=?,lease_until=? WHERE request_id=?',(body.phase,json.dumps(file,ensure_ascii=False)if file else None,json.dumps(body.receipt,ensure_ascii=False)if body.receipt else None,now,now+180,rid))
   reply={'READY':'보낼 파일을 확인했습니다. 네이버웍스 전달을 준비하고 있습니다.','SENDING':'정상익 차장에게 파일을 보내고 있습니다.','SENT':'정상익 차장에게 네이버웍스로 보냈습니다.\n'+(file['filename']if file else''),'FAILED':'파일을 확인하지 못해 전송하지 않았습니다.','UNKNOWN':'전송 결과를 확인해야 합니다. 중복 전송을 막기 위해 자동으로 다시 보내지 않습니다.'}[body.phase]
   status='COMPLETED'if body.phase=='SENT'else'FAILED'if body.phase=='FAILED'else'NEEDS_INFO'if body.phase=='UNKNOWN'else'RUNNING'
   db.execute('UPDATE requests SET status=?,reply=?,result_sha256=?,updated_at=? WHERE id=?',(status,reply,hashlib.sha256(reply.encode()).hexdigest()if status=='COMPLETED'else None,now,rid));store._event(db,rid,'DELIVERY_'+body.phase)
   return result({'ok':True,'phase':body.phase})
