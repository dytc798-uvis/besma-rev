"""Personal, single-use site setup. Raw invite credentials are never persisted."""
import hashlib
import hmac
import math
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException
from sqlalchemy import text
from app.config.settings import settings
from app.config.security import get_password_hash
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.core.password_policy import MIN_PASSWORD_LENGTH
from app.modules.users.models import User
from app.modules.sites.models import Site

VERSION = '1.0.0'
SITES = {'24028':'gangwon-tunnel','25037':'namyangju-wangsuk','25040':'gangjin-gwangju','25059':'gunpo-daeyami'}
DDL = [
 """CREATE TABLE IF NOT EXISTS site_setup_invites (
 id TEXT PRIMARY KEY, site_id INTEGER NOT NULL REFERENCES sites(id),
 expected_name TEXT NOT NULL, job_title TEXT NOT NULL, email TEXT,
 target_user_id INTEGER REFERENCES users(id), claimed_user_id INTEGER REFERENCES users(id),
 token_hash TEXT NOT NULL, purpose TEXT NOT NULL DEFAULT 'SETUP',
 state TEXT NOT NULL DEFAULT 'ACTIVE', issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
 consumed_at INTEGER, issued_by INTEGER NOT NULL REFERENCES users(id))""",
 """CREATE TABLE IF NOT EXISTS site_setup_profiles (
 user_id INTEGER PRIMARY KEY REFERENCES users(id), site_id INTEGER NOT NULL REFERENCES sites(id),
 job_title TEXT NOT NULL, email TEXT NOT NULL, session_valid_after INTEGER NOT NULL,
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL)""",
 """CREATE TABLE IF NOT EXISTS site_setup_threads (
 id INTEGER PRIMARY KEY REFERENCES government_contact_messages(id), site_id INTEGER NOT NULL REFERENCES sites(id), title TEXT NOT NULL)""",
 """CREATE TABLE IF NOT EXISTS site_setup_thread_messages (
 message_id INTEGER PRIMARY KEY REFERENCES government_contact_messages(id), thread_id INTEGER NOT NULL REFERENCES site_setup_threads(id))""",
 """CREATE TABLE IF NOT EXISTS site_setup_reset_requests (
 id INTEGER PRIMARY KEY AUTOINCREMENT, site_code TEXT NOT NULL, name TEXT NOT NULL,
 email TEXT NOT NULL, created_at INTEGER NOT NULL, resolved_at INTEGER)"""
]

def migrate(db):
 for sql in DDL:db.execute(text(sql))

def owner(user):
 from app.core.government_workspace_access import is_government_owner
 from app.core.system_backup_access import can_system_backup
 role=getattr(user.role,'value',user.role)
 return bool(user.is_active and (is_government_owner(user) or
  (can_system_backup(user.login_id) and role in {'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN'})))

def require_owner(user):
 if not owner(user):raise HTTPException(403,'초대 링크 관리는 정상익 관리자만 사용할 수 있습니다.')

def signature(ident):
 return hmac.new(settings.jwt_secret_key.encode(),('besma-site-setup-v1:'+ident).encode(),hashlib.sha256).hexdigest()

def credential(ident):return ident+'.'+signature(ident)

def issue(db, *, site_id, name, job_title, email, user_id, issued_by, purpose='SETUP'):
 site=db.get(Site,site_id)
 if not site or site.site_code not in SITES:raise HTTPException(400,'대상 현장이 아닙니다.')
 if user_id:
  user=db.get(User,user_id)
  if not user or user.site_id!=site_id or user.name!=name or not user.is_active or getattr(user.role,'value',user.role)!='SITE':
   raise HTTPException(409,'기존 개인 계정과 일치하지 않습니다.')
 ident=uuid.uuid4().hex;now=int(time.time())
 db.execute(text('''INSERT INTO site_setup_invites
 (id,site_id,expected_name,job_title,email,target_user_id,token_hash,purpose,issued_at,expires_at,issued_by)
 VALUES (:id,:site,:name,:job,:email,:user,:hash,:purpose,:now,:expiry,:owner)'''),
 {'id':ident,'site':site_id,'name':name,'job':job_title,'email':email,'user':user_id,
 'hash':hashlib.sha256(credential(ident).encode()).hexdigest(),'purpose':purpose,
 'now':now,'expiry':now+72*3600,'owner':issued_by})
 return ident

def lookup(db, token):
 if not isinstance(token,str) or not re.fullmatch(r'[0-9a-f]{32}\.[0-9a-f]{64}',token):raise HTTPException(400,'사용할 수 없는 링크입니다. 관리자에게 새 링크를 요청해 주세요.')
 ident=token.split('.')[0]
 row=db.execute(text('SELECT * FROM site_setup_invites WHERE id=:id'),{'id':ident}).mappings().first()
 if not row or row['state']!='ACTIVE' or row['expires_at']<=time.time() or not hmac.compare_digest(row['token_hash'],hashlib.sha256(token.encode()).hexdigest()):
  raise HTTPException(400,'사용되었거나 만료된 링크입니다. 관리자에게 새 링크를 요청해 주세요.')
 site=db.get(Site,row['site_id'])
 if not site or site.site_code not in SITES:raise HTTPException(400,'대상 현장을 확인할 수 없습니다.')
 return dict(row),site

def inspect_invite(db,token):
 row,site=lookup(db,token)
 prefix=(row['email'] or '').split('@')[0].lower()
 proposed=prefix if re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,49}',prefix) else ''
 def available(value):return not db.execute(text('SELECT id FROM users WHERE lower(login_id)=:login AND id!=:target'),{'login':value,'target':row['target_user_id'] or -1}).first()
 if not proposed or not available(proposed):proposed=SITES[site.site_code]
 base=proposed;n=1
 while not available(proposed):n+=1;proposed=base+'-'+str(n)
 return {'site_name':site.site_name,'site_code':site.site_code,'name':row['expected_name'],
 'job_title':row['job_title'],'email':row['email'] or '', 'suggested_login_id':proposed,
 'expires_at':datetime.fromtimestamp(row['expires_at'],timezone.utc).isoformat(),'purpose':row['purpose']}

def accept(db,payload):
 allowed={'token','login_id','password','password_confirm','name','job_title','email'}
 if set(payload)!=allowed or any(not isinstance(v,str) for v in payload.values()):raise HTTPException(422,'입력 항목을 확인해 주세요.')
 # Atomic compare-and-consume prevents two signups using one invitation.
 db.rollback();db.execute(text('BEGIN IMMEDIATE'))
 try:
  row,site=lookup(db,payload['token'])
  login=payload['login_id'].strip().lower();name=payload['name'].strip();job=payload['job_title'].strip();email=payload['email'].strip()
  password=payload['password']
  if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,49}',login):raise HTTPException(422,'아이디는 영문 소문자·숫자·._-로 3~50자 입력해 주세요.')
  if name!=row['expected_name']:raise HTTPException(422,'초대받은 이름과 다릅니다. 관리자에게 확인해 주세요.')
  if not job or len(job)>60:raise HTTPException(422,'직책을 입력해 주세요.')
  if len(email)>254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email):raise HTTPException(422,'이메일 주소를 확인해 주세요.')
  if len(password)<MIN_PASSWORD_LENGTH or len(password)>128 or password!=password.strip():raise HTTPException(422,'비밀번호는 앞뒤 공백 없이 4~128자로 입력해 주세요.')
  if password!=payload['password_confirm']:raise HTTPException(422,'비밀번호 확인이 일치하지 않습니다.')
  user=db.get(User,row['target_user_id']) if row['target_user_id'] else None
  if user and (user.site_id!=site.id or user.name!=row['expected_name'] or not user.is_active or getattr(user.role,'value',user.role)!='SITE'):
   raise HTTPException(409,'기존 계정 상태가 변경됐습니다. 관리자에게 확인해 주세요.')
  collision=db.execute(text('SELECT id FROM users WHERE lower(login_id)=:login AND id!=:target'),{'login':login,'target':user.id if user else -1}).first()
  if collision:raise HTTPException(409,'이미 사용 중인 아이디입니다. 다른 아이디를 정해 주세요.')
  now=int(time.time());stamp=utc_now()
  if user is None:
   user=User(name=name,login_id=login,password_hash=get_password_hash(password),role=Role.SITE,ui_type=UIType.SITE,site_id=site.id,is_active=True,must_change_password=False)
   db.add(user);db.flush()
  else:
   user.login_id=login;user.password_hash=get_password_hash(password);user.must_change_password=False
  user.password_changed_at=stamp;user.temporary_password_expires_at=None;user.updated_at=stamp
  db.execute(text('''INSERT INTO site_setup_profiles (user_id,site_id,job_title,email,session_valid_after,created_at,updated_at)
  VALUES (:user,:site,:job,:email,:valid,:now,:now) ON CONFLICT(user_id) DO UPDATE SET
  site_id=excluded.site_id,job_title=excluded.job_title,email=excluded.email,session_valid_after=excluded.session_valid_after,updated_at=excluded.updated_at'''),
  {'user':user.id,'site':site.id,'job':job,'email':email,'valid':math.ceil(time.time()),'now':now})
  updated=db.execute(text("UPDATE site_setup_invites SET state='USED',consumed_at=:now,claimed_user_id=:user WHERE id=:id AND state='ACTIVE'"),{'now':now,'user':user.id,'id':row['id']})
  if updated.rowcount!=1:raise HTTPException(409,'이미 사용된 링크입니다.')
  db.commit()
  return {'result':'ok','login_id':login,'site_name':site.site_name,'message':'계정 설정이 완료됐습니다. 정한 아이디와 비밀번호로 로그인해 주세요.'}
 except Exception:
  db.rollback();raise

def profile(db,user):
 if not db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='site_setup_profiles'")).first():return None
 row=db.execute(text('SELECT * FROM site_setup_profiles WHERE user_id=:user'),{'user':user.id}).mappings().first()
 if row and row['site_id']!=user.site_id:raise HTTPException(403,'현장 연결을 확인해 주세요.')
 return dict(row) if row else None

def enforce(db,user,request,payload):
 p=profile(db,user)
 if not p:return
 if int(payload.get('iat',0))<p['session_valid_after']:raise HTTPException(401,'로그인이 갱신됐습니다. 다시 로그인해 주세요.')
 path=request.url.path;method=request.method
 reads={'/auth/me','/site-invitations/access','/site-invitations/documents','/site-invitations/ideas','/site-invitations/threads'}
 allowed=(method=='GET' and (path in reads or re.fullmatch(r'/site-invitations/(documents/\d+/content|threads/\d+)',path))) or (method=='POST' and (path in {'/auth/logout','/auth/change-password','/site-invitations/reset-request','/site-invitations/threads'} or re.fullmatch(r'/site-invitations/threads/\d+/(reply|read)',path)))
 if not allowed:raise HTTPException(403,'본인 현장문서·소통게시판·운영 아이디어 조회만 사용할 수 있습니다.')

_lock=Lock();_buckets={}
def throttle(request):
 key=request.client.host if request.client else 'unknown';now=time.monotonic()
 with _lock:
  if len(_buckets)>5000:
   for k,v in list(_buckets.items()):
    if v[0]<now-60:_buckets.pop(k,None)
  started,count=_buckets.get(key,(now,0))
  if started<now-60:started,count=now,0
  if count>=40:raise HTTPException(429,'잠시 후 다시 시도해 주세요.')
  _buckets[key]=(started,count+1)
