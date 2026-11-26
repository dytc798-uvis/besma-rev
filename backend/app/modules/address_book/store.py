"""Shared safety contacts with atomic, append-only revisions."""
import json,re,sqlite3,unicodedata
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from contextlib import contextmanager

FIELDS={'category':60,'organization':160,'region':120,'department':160,'person':80,'duties':1600,'phone':40,'fax':40,'source_url':1000,'verified_on':10,'note':1000}
CATEGORIES=['고용노동부','근로복지공단','안전보건공단','거래처','교육·검진기관','협회·유관기관','비상연락','기타']
def now():return datetime.now(timezone.utc).isoformat()
def normalized(s):return ''.join(unicodedata.normalize('NFKC',s).lower().split())
def clean(data):
 if set(data)-set(FIELDS):raise ValueError('지원하지 않는 항목입니다.')
 result={k:str(data.get(k,'')).strip() for k in FIELDS}
 for k,n in FIELDS.items():
  if len(result[k])>n:raise ValueError('입력 내용이 너무 깁니다: '+k)
 if result['category']not in CATEGORIES or not result['organization']or not result['duties']:raise ValueError('분류·기관명·담당업무를 입력해 주세요.')
 if not re.fullmatch(r'[0-9+() -]{3,40}',result['phone']) or not 3<=len(re.sub(r'\D','',result['phone']))<=15:raise ValueError('전화번호를 확인해 주세요.')
 if result['fax'] and not re.fullmatch(r'[0-9+() -]{3,40}',result['fax']):raise ValueError('팩스번호를 확인해 주세요.')
 if result['source_url'] and not re.fullmatch(r'https?://[^\s]+',result['source_url']):raise ValueError('출처는 http 또는 https 주소로 입력해 주세요.')
 if result['verified_on']:
  from datetime import date
  try:date.fromisoformat(result['verified_on'])
  except ValueError:raise ValueError('확인일 형식을 확인해 주세요.')
 return result

class Store:
 def __init__(self,path):self.path=Path(path)
 @contextmanager
 def connect(self):
  c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
  try:
   with c:yield c
  finally:c.close()
 def init(self):
  self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect()as c:
   c.executescript('''
   CREATE TABLE IF NOT EXISTS contacts(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,active INTEGER NOT NULL,data TEXT NOT NULL,search_text TEXT NOT NULL,phone_digits TEXT NOT NULL,updated_at TEXT NOT NULL,updated_by TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,contact_id TEXT NOT NULL REFERENCES contacts(id),revision INTEGER NOT NULL,action TEXT NOT NULL,actor_id TEXT NOT NULL,actor_login TEXT NOT NULL,actor_name TEXT NOT NULL,at TEXT NOT NULL,reason TEXT NOT NULL,before_json TEXT,after_json TEXT,UNIQUE(contact_id,revision));
   CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
   CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
   CREATE TABLE IF NOT EXISTS seeds(seed_key TEXT PRIMARY KEY,contact_id TEXT NOT NULL REFERENCES contacts(id));
   ''')
 def item(self,row):return dict(id=row['id'],revision=row['revision'],active=bool(row['active']),updated_at=row['updated_at'],updated_by=row['updated_by'],**json.loads(row['data']))
 def listing(self,q='',category='',region='',include_inactive=False,offset=0,limit=50):
  terms=q.split();where=['1=1'];args=[]
  if not include_inactive:where.append('active=1')
  for term in terms:
   term=normalized(term);where.append('(instr(search_text,?)>0 OR instr(phone_digits,?)>0)');args.extend([term,re.sub(r'\D','',term)or '\x01'])
  if category:where.append("json_extract(data,'$.category')=?");args.append(category)
  if region:where.append("instr(json_extract(data,'$.region'),?)>0");args.append(region)
  sql=' FROM contacts WHERE '+' AND '.join(where)
  with self.connect()as c:
   total=c.execute('SELECT count(*)'+sql,args).fetchone()[0]
   rows=c.execute('SELECT *'+sql+" ORDER BY json_extract(data,'$.organization'),json_extract(data,'$.department'),id LIMIT ? OFFSET ?",[*args,limit,offset]).fetchall()
  return dict(total=total,items=[self.item(r)for r in rows],offset=offset,limit=limit)
 def write(self,data,actor,reason,id=None,revision=None,active=True,seed_key=None):
  data=clean(data);stamp=now();id=id or str(uuid4());reason=reason.strip()
  if not reason or len(reason)>300:raise ValueError('변경 사유를 300자 이내로 입력해 주세요.')
  raw=json.dumps(data,ensure_ascii=False,sort_keys=True)
  with self.connect()as c:
   c.execute('BEGIN IMMEDIATE')
   if seed_key and c.execute('SELECT 1 FROM seeds WHERE seed_key=?',(seed_key,)).fetchone():return None
   old=c.execute('SELECT * FROM contacts WHERE id=?',(id,)).fetchone()
   if old and (revision is None or old['revision']!=revision):raise RuntimeError('다른 사용자가 수정했습니다. 새로 조회한 뒤 수정해 주세요.')
   if not old and revision is not None:raise KeyError(id)
   if old and json.loads(old['data'])==data and bool(old['active'])==active:return self.item(old)
   rev=old['revision']+1 if old else 1
   before=self.item(old)if old else None
   after=dict(id=id,revision=rev,active=active,updated_at=stamp,updated_by=actor['name'],**data)
   c.execute('INSERT INTO contacts VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,active=excluded.active,data=excluded.data,search_text=excluded.search_text,phone_digits=excluded.phone_digits,updated_at=excluded.updated_at,updated_by=excluded.updated_by',(id,rev,int(active),raw,normalized(' '.join(data.values())),re.sub(r'\D','',data['phone']),stamp,actor['name']))
   action='등록'if not old else '사용중지'if not active else '다시사용'if not old['active']else '수정'
   c.execute('INSERT INTO events(contact_id,revision,action,actor_id,actor_login,actor_name,at,reason,before_json,after_json) VALUES(?,?,?,?,?,?,?,?,?,?)',(id,rev,action,str(actor['id']),actor['login'],actor['name'],stamp,reason,json.dumps(before,ensure_ascii=False)if before else None,json.dumps(after,ensure_ascii=False)))
   if seed_key:c.execute('INSERT INTO seeds VALUES(?,?)',(seed_key,id))
  return after
 def history(self,id,offset=0,limit=50):
  with self.connect()as c:
   if not c.execute('SELECT 1 FROM contacts WHERE id=?',(id,)).fetchone():raise KeyError(id)
   total=c.execute('SELECT count(*) FROM events WHERE contact_id=?',(id,)).fetchone()[0]
   rows=c.execute('SELECT * FROM events WHERE contact_id=? ORDER BY revision DESC LIMIT ? OFFSET ?',(id,limit,offset)).fetchall()
  return dict(total=total,items=[dict(revision=r['revision'],action=r['action'],actor_login=r['actor_login'],actor_name=r['actor_name'],at=r['at'],reason=r['reason'],before=json.loads(r['before_json'])if r['before_json']else None,after=json.loads(r['after_json']))for r in rows])
