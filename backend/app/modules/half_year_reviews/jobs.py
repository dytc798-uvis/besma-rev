from contextlib import closing
from datetime import datetime,timezone
import copy,hashlib,json,secrets,time,uuid
from .catalog import FORMS,Conflict,validate_assessment
from . import paper

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def ensure(c):
    c.execute('CREATE TABLE IF NOT EXISTS paper_jobs(id TEXT PRIMARY KEY,context_id TEXT NOT NULL,requester_id INTEGER NOT NULL,status TEXT NOT NULL,lease TEXT,lease_until REAL NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,payload TEXT NOT NULL,result TEXT,at TEXT NOT NULL,updated_at TEXT NOT NULL,error TEXT NOT NULL DEFAULT "")')
    c.execute('CREATE TABLE IF NOT EXISTS paper_worker(id INTEGER PRIMARY KEY CHECK(id=1),at REAL NOT NULL)')
def visible(row):
    value=json.loads(row['payload']);return {k:value[k]for k in ['file_id','form','subject_id','subject_name']}|{'id':row['id'],'status':row['status'],'at':row['at'],'updated_at':row['updated_at'],'result':json.loads(row['result'])if row['result']else None,'error':row['error']}
def listing(store,key):
    with closing(store.connect())as c:
        ensure(c);rows=c.execute('SELECT * FROM paper_jobs WHERE context_id=? ORDER BY at DESC LIMIT 100',(key,)).fetchall();worker=c.execute('SELECT at FROM paper_worker WHERE id=1').fetchone()
        return {'items':[visible(r)for r in rows],'worker_online':bool(worker and time.time()-worker['at']<180)}
def queue(c,key,data,actor,name,body,meta,period,stamp):
    ensure(c)
    if set(body)!={'form','subject_id','file_id'}or body['form']not in FORMS or meta is None:raise ValueError('PARSE_REQUEST_INVALID')
    form=body['form'];subject=body['subject_id'];target=next((s['name']for s in data['subjects'].get(form,[])if s['id']==subject),'')
    if FORMS[form].get('needs_subject')and not target or not FORMS[form].get('needs_subject')and subject!='site':raise ValueError('SUBJECT_REQUIRED')
    file=next((f for f in data['files']if f['id']==body['file_id']and f['extension']=='.pdf'),None)
    if file is None:raise ValueError('PDF_REQUIRED')
    baseline=copy.deepcopy(data['assessments'].get(form+':'+subject,{}).get('draft',{}))
    payload={**body,**meta,'context_site':key.split('|')[0],'period':period,'subject_name':target,'baseline':baseline,'source_sha256':file['sha256'],'requester_name':name}
    for row in c.execute('SELECT * FROM paper_jobs WHERE context_id=? AND status IN ("QUEUED","RUNNING","READY","NEEDS_REVIEW")',(key,)):
        if row['error']:continue
        old=json.loads(row['payload'])
        if all(old.get(k)==payload.get(k)for k in ['form','subject_id','file_id','baseline']):return visible(row)
    jid=uuid.uuid4().hex;c.execute('INSERT INTO paper_jobs(id,context_id,requester_id,status,payload,at,updated_at)VALUES(?,?,?,"QUEUED",?,?,?)',(jid,key,actor,encoded(payload),stamp,stamp));return visible(c.execute('SELECT * FROM paper_jobs WHERE id=?',(jid,)).fetchone())
def apply(c,key,data,body):
    ensure(c)
    if set(body)!={'job_id','criterion_ids','identity_confirmed'}or type(body['identity_confirmed'])is not bool or not isinstance(body['criterion_ids'],list)or len(set(body['criterion_ids']))!=len(body['criterion_ids']):raise ValueError('PARSE_APPLY_INVALID')
    row=c.execute('SELECT * FROM paper_jobs WHERE id=? AND context_id=?',(body['job_id'],key)).fetchone()
    if row is None or row['status']not in {'READY','NEEDS_REVIEW','APPLIED'}:raise ValueError('PARSE_NOT_READY')
    result=json.loads(row['result']);job=json.loads(row['payload']);known={r['id']for r in result['transcription']['answers']}
    if not set(body['criterion_ids'])<=known:raise ValueError('PARSE_APPLY_INVALID')
    answers,check=paper.merge(result['transcription'],job,data,body['criterion_ids'],body['identity_confirmed'])
    if not check['applied']:raise ValueError('PARSE_REVIEW_REQUIRED')
    c.execute('UPDATE paper_jobs SET status="APPLIED",updated_at=? WHERE id=?',(datetime.now(timezone.utc).isoformat(),row['id']))
    return job,answers,check
def claim(store,allowed):
    stamp=datetime.now(timezone.utc).isoformat();now=time.time()
    with closing(store.connect())as c:
        ensure(c);c.execute('BEGIN IMMEDIATE');c.execute('INSERT INTO paper_worker VALUES(1,?)ON CONFLICT(id)DO UPDATE SET at=excluded.at',(now,))
        c.execute('UPDATE paper_jobs SET status="QUEUED",lease=NULL WHERE status="RUNNING"AND lease_until<? AND attempts<3',(now,))
        c.execute('UPDATE paper_jobs SET status="NEEDS_REVIEW",error="PROCESSING_INTERRUPTED",updated_at=? WHERE status="RUNNING"AND lease_until<? AND attempts>=3',(stamp,now))
        for row in c.execute('SELECT * FROM paper_jobs WHERE status="QUEUED" AND lease_until<=? ORDER BY at LIMIT 50',(now,)).fetchall():
            job=json.loads(row['payload'])
            if not allowed(row['requester_id'],job):
                c.execute('UPDATE paper_jobs SET status="NEEDS_REVIEW",error="ACCESS_CHANGED",updated_at=? WHERE id=?',(stamp,row['id']));continue
            lease=secrets.token_hex(32);c.execute('UPDATE paper_jobs SET status="RUNNING",lease=?,lease_until=?,attempts=attempts+1,updated_at=? WHERE id=?',(lease,now+900,stamp,row['id']));c.commit()
            content,meta=store.file(row['context_id'],job['file_id'])
            if meta['sha256']!=job['source_sha256']:raise ValueError('PARSE_SOURCE_CHANGED')
            return {'id':row['id'],'lease':lease,'context_id':row['context_id'],'payload':job,'source':content}
        c.commit();return None
def finish(store,jid,lease,value,pages,source_sha,error,allowed):
    stamp=datetime.now(timezone.utc).isoformat()
    with closing(store.connect())as c:
        ensure(c);c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM paper_jobs WHERE id=?',(jid,)).fetchone()
        if row is None or row['lease']!=lease:raise Conflict('PARSE_LEASE_CHANGED')
        if row['status']in {'READY','NEEDS_REVIEW','APPLIED'}:return visible(row)
        if row['status']!='RUNNING'or row['lease_until']<time.time():raise Conflict('PARSE_LEASE_EXPIRED')
        job=json.loads(row['payload'])
        if not allowed(row['requester_id'],job):error='ACCESS_CHANGED'
        if error:
            if error not in {'ACCESS_CHANGED','MODEL_UNAVAILABLE','PDF_UNREADABLE','PROCESSING_FAILED'}:error='PROCESSING_FAILED'
            retry=error in {'MODEL_UNAVAILABLE','PROCESSING_FAILED'}and row['attempts']<3
            state='QUEUED'if retry else'NEEDS_REVIEW';next_at=time.time()+60*(2**(row['attempts']-1))if retry else 0
            c.execute('UPDATE paper_jobs SET status=?,lease_until=?,error=?,updated_at=? WHERE id=?',(state,next_at,error,stamp,jid));c.commit();return visible(c.execute('SELECT * FROM paper_jobs WHERE id=?',(jid,)).fetchone())
        if source_sha!=job['source_sha256']or type(pages)is not int or not 1<=pages<=12:raise ValueError('PARSE_SOURCE_CHANGED')
        transcription=paper.validate(value,job['form'],set(range(1,pages+1)))
        current=c.execute('SELECT * FROM contexts WHERE id=?',(row['context_id'],)).fetchone();data=json.loads(current['data']);answers,check=paper.merge(transcription,job,data)
        if check['applied']:
            clean,totals=validate_assessment(job['form'],answers,data['files'],data['subjects'],job['subject_id'],False)
            assessment=data['assessments'].setdefault(job['form']+':'+job['subject_id'],{});assessment['draft']={'data':clean,'result':totals,'subject_name':job['subject_name'],'inspector':job['requester_name'],'actor_id':row['requester_id'],'at':stamp,'paper_job_id':jid}
            revision=current['revision']+1;c.execute('UPDATE contexts SET revision=?,data=? WHERE id=?',(revision,encoded(data),row['context_id']));c.execute('INSERT INTO events(context_id,revision,actor_id,at,action,data)VALUES(?,?,?,?,?,?)',(row['context_id'],revision,row['requester_id'],stamp,'paper_transcription',encoded({'job_id':jid,'source_sha256':source_sha,'check':check})))
        result={'transcription':transcription,**check};status='NEEDS_REVIEW'if check['pending']or not check['applied']else'READY'
        c.execute('UPDATE paper_jobs SET status=?,result=?,updated_at=? WHERE id=?',(status,encoded(result),stamp,jid));c.commit();return visible(c.execute('SELECT * FROM paper_jobs WHERE id=?',(jid,)).fetchone())
