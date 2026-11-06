"""Private, idempotent signing PDF queue. Render success is never delivery success."""
from pathlib import Path
from contextlib import closing
from datetime import datetime,timezone
import sqlite3,json,hashlib,secrets,time,uuid,re

def stamp():return datetime.now(timezone.utc).isoformat()
def encode(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def connect(store):
    folder=store.root/'signature-output';folder.mkdir(parents=True,mode=0o700,exist_ok=True)
    c=sqlite3.connect(folder/'jobs.sqlite3',timeout=20);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,context_id TEXT NOT NULL,owner_id INTEGER NOT NULL,request_key TEXT NOT NULL,source_hash TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,result TEXT,lease_hash TEXT,lease_until REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT "",at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(context_id,owner_id,request_key))');c.commit();return c

def visible(row):
    p=json.loads(row['payload']);purpose=p.get('purpose','SIGNATURE');return {'id':row['id'],'status':row['status'],'form':p['form'],'subject_id':p['subject_id'],'snapshot_id':p['snapshot_id'],'purpose':purpose,'filename':p['filename'],'at':row['at'],'updated_at':row['updated_at'],'error':row['error'],'result':json.loads(row['result'])if row['result']else None,'delivery_status':'NOT_REQUESTED','message':'공무 전달용: 다운로드하여 웍스에 첨부해 주세요.'if purpose!='REPORT'and p['form']in {'report','law'}else'평가서 다운로드'}

def queue(store,key,user,row,period,body,profile=None):
    from .catalog import FORMS
    from .printing import document
    purpose=body.get('purpose','SIGNATURE')
    if set(body)not in [{'form','subject_id','snapshot_id','request_key'},{'form','subject_id','snapshot_id','request_key','purpose'}]or purpose not in {'SIGNATURE','REPORT'}or(purpose=='REPORT'and body.get('form')!='report')or body['form']not in FORMS or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',body['request_key']):raise ValueError('SIGNATURE_REQUEST_INVALID')
    assessment=store.load(key)['data']['assessments'].get(body['form']+':'+body['subject_id'],{});snapshot=assessment.get('completed')
    if not snapshot or snapshot['id']!=body['snapshot_id']:raise ValueError('COMPLETE_FIRST')
    from .site_profile import enrich
    snapshot=enrich(snapshot,profile or{},assessment)
    site=row.title.removeprefix('[점검] ').strip();filename=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',site+'_'+FORMS[body['form']]['title']+('_대표보고용.pdf'if purpose=='REPORT'else'_소장서명용.pdf'if body['form']in {'report','law'}else'_평가서.pdf'))
    html=document(body['form'],snapshot,site,period,blind=purpose!='REPORT');source=hashlib.sha256(html.encode()).hexdigest();payload={**body,'html':html,'source_sha256':source,'public_id':row.public_id,'period':period,'context_id':key,'site':site,'filename':filename,'blind_report_scores':False,'purpose':purpose};now=stamp()
    with closing(connect(store))as c,c:
        c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT * FROM jobs WHERE context_id=? AND owner_id=? AND request_key=?',(key,user.id,body['request_key'])).fetchone()
        if old:
            if old['source_hash']!=source:raise ValueError('SIGNATURE_REQUEST_CHANGED')
            return visible(old)
        for existing in c.execute('SELECT * FROM jobs WHERE context_id=? AND owner_id=? AND source_hash=? AND status IN ("QUEUED","RENDERING","READY") ORDER BY at DESC LIMIT 100',(key,user.id,source)).fetchall():
            prior=json.loads(existing['payload'])
            if prior.get('purpose','SIGNATURE')==purpose and all(prior.get(k)==body[k]for k in ['form','subject_id','snapshot_id']):return visible(existing)
        if c.execute('SELECT COUNT(*) FROM jobs WHERE owner_id=? AND status IN ("QUEUED","RENDERING")',(user.id,)).fetchone()[0]>=20:raise ValueError('SIGNATURE_QUEUE_FULL')
        jid=uuid.uuid4().hex;c.execute('INSERT INTO jobs(id,context_id,owner_id,request_key,source_hash,status,payload,at,updated_at)VALUES(?,?,?,?,?,"QUEUED",?,?,?)',(jid,key,user.id,body['request_key'],source,encode(payload),now,now));return visible(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())

def listing(store,key,owner):
    with closing(connect(store))as c:return [visible(r)for r in c.execute('SELECT * FROM jobs WHERE context_id=? AND owner_id=? ORDER BY at DESC LIMIT 100',(key,owner))]

def output(store,key,owner,jid):
    if not re.fullmatch('[0-9a-f]{32}',jid):raise KeyError('SIGNATURE_MISSING')
    with closing(connect(store))as c:r=c.execute('SELECT * FROM jobs WHERE id=? AND context_id=? AND owner_id=?',(jid,key,owner)).fetchone()
    if r is None or r['status']!='READY':raise KeyError('SIGNATURE_MISSING')
    meta=json.loads(r['result']);raw=(store.root/'signature-output'/jid/'output.pdf').read_bytes()
    if len(raw)!=meta['bytes']or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('SIGNATURE_OUTPUT_CHANGED')
    return raw,meta

def claim(store,allowed):
    with closing(connect(store))as c,c:
        c.execute('BEGIN IMMEDIATE');now=time.time();c.execute('UPDATE jobs SET status=CASE WHEN attempts<3 THEN "QUEUED" ELSE "FAILED" END,error="RENDER_INTERRUPTED" WHERE status="RENDERING" AND lease_until<?',(now,))
        for row in c.execute('SELECT * FROM jobs WHERE status="QUEUED" ORDER BY at LIMIT 100').fetchall():
            p=json.loads(row['payload'])
            if not allowed(row['owner_id'],p):continue
            lease=secrets.token_hex(32);c.execute('UPDATE jobs SET status="RENDERING",lease_hash=?,lease_until=?,attempts=attempts+1,error="",updated_at=? WHERE id=?',(hashlib.sha256(lease.encode()).hexdigest(),now+180,stamp(),row['id']));return {'id':row['id'],'lease':lease,'payload':p}
    return None

def finish(store,jid,lease,raw,error,allowed):
    if not re.fullmatch('[0-9a-f]{32}',jid)or not re.fullmatch('[0-9a-f]{64}',lease):raise ValueError('SIGNATURE_LEASE_INVALID')
    with closing(connect(store))as c,c:
        c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
        if row is None or row['lease_hash']!=hashlib.sha256(lease.encode()).hexdigest()or not allowed(row['owner_id'],json.loads(row['payload'])):raise ValueError('SIGNATURE_LEASE_INVALID')
        if row['status']=='READY':
            result=json.loads(row['result'])
            if hashlib.sha256(raw).hexdigest()!=result['sha256']:raise ValueError('SIGNATURE_RESULT_CHANGED')
            return visible(row)
        if row['status']!='RENDERING'or row['lease_until']<time.time():raise ValueError('SIGNATURE_LEASE_EXPIRED')
        if error:
            c.execute('UPDATE jobs SET status="FAILED",error="PDF_RENDER_FAILED",updated_at=? WHERE id=?',(stamp(),jid))
        else:
            if not raw.startswith(b'%PDF-')or not 100<len(raw)<=15*1024*1024:raise ValueError('PDF_INVALID')
            from .pdf_preview import document
            with document(raw)as pdf:
                pages=len(pdf)
                if not 1<=pages<=30:raise ValueError('PDF_PAGE_LIMIT')
            folder=store.root/'signature-output'/jid;folder.mkdir(mode=0o700,exist_ok=True);path=folder/'output.pdf'
            if path.exists()and path.read_bytes()!=raw:raise ValueError('SIGNATURE_FILE_EXISTS')
            if not path.exists():
                with path.open('xb')as f:f.write(raw)
            p=json.loads(row['payload']);result={'filename':p['filename'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'pages':pages,'rendered_on':'LOCAL_PC','scores_hidden':p['form']=='report','photos_included':False}
            c.execute('UPDATE jobs SET status="READY",result=?,updated_at=? WHERE id=?',(encode(result),stamp(),jid))
        return visible(c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone())
