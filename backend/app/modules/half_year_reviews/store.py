from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import sqlite3,json,hashlib,uuid,re,io,zipfile,os
from .catalog import CATALOG,FORMS,EVIDENCE,blank,cleaned,validate_assessment,Conflict
from app.modules.inspection_reports.pptx_report import normalize_photo
from . import exports,jobs
digest=lambda value:hashlib.sha256(value).hexdigest()
encoded=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
class ReviewStore:
    def __init__(self,root):
        path=str(Path(root).resolve())
        if os.name=='nt'and not path.startswith('\\\\?\\'):path='\\\\?\\UNC\\'+path[2:]if path.startswith('\\\\')else'\\\\?\\'+path
        self.root=Path(path)
    def connect(self):
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        c=sqlite3.connect(self.root/'reviews.sqlite3',timeout=20);c.row_factory=sqlite3.Row
        c.executescript('''CREATE TABLE IF NOT EXISTS contexts(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL);CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,context_id TEXT NOT NULL,revision INTEGER NOT NULL,actor_id INTEGER NOT NULL,at TEXT NOT NULL,action TEXT NOT NULL,data TEXT NOT NULL);CREATE TABLE IF NOT EXISTS receipts(context_id TEXT NOT NULL,request_key TEXT NOT NULL,actor_id INTEGER NOT NULL,payload_sha256 TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(context_id,request_key,actor_id));CREATE TABLE IF NOT EXISTS outputs(id TEXT PRIMARY KEY,context_id TEXT NOT NULL,snapshot_id TEXT NOT NULL,form TEXT NOT NULL,filename TEXT NOT NULL,sha256 TEXT NOT NULL,size INTEGER NOT NULL,at TEXT NOT NULL,UNIQUE(context_id,snapshot_id,form));''');c.commit();return c
    def load(self,key):
        with closing(self.connect())as c:
            row=c.execute('SELECT * FROM contexts WHERE id=?',(key,)).fetchone()
            return {'revision':row['revision'],'data':json.loads(row['data'])}if row else{'revision':0,'data':blank()}
    def receipt(self,key,actor,request_key):
        with closing(self.connect())as c:
            row=c.execute('SELECT result FROM receipts WHERE context_id=? AND request_key=? AND actor_id=?',(key,request_key,actor)).fetchone()
            if row is None:raise KeyError('RECEIPT_MISSING')
            return json.loads(row['result'])
    def mutate(self,key,actor,name,request,attachment=None,context_meta=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',request['request_key']):raise ValueError('REQUEST_KEY_INVALID')
        canonical={**request,'attachment_sha256':digest(attachment[0])if attachment else None};payload_sha=digest(encoded(canonical).encode());stamp=datetime.now(timezone.utc).isoformat();new_path=None
        with closing(self.connect())as c:
            c.execute('BEGIN IMMEDIATE')
            replay=c.execute('SELECT payload_sha256,result FROM receipts WHERE context_id=? AND request_key=? AND actor_id=?',(key,request['request_key'],actor)).fetchone()
            if replay:
                if replay['payload_sha256']!=payload_sha:raise Conflict('REQUEST_CHANGED')
                return json.loads(replay['result'])
            row=c.execute('SELECT * FROM contexts WHERE id=?',(key,)).fetchone();revision=row['revision']if row else 0;data=json.loads(row['data'])if row else blank()
            if revision!=request['revision']:raise Conflict('REVISION_CHANGED')
            action=request['action'];body=request['data'];result={};op_meta={}
            if not isinstance(body,dict):raise ValueError('REQUEST_INVALID')
            if action=='evidence':
                if set(body)!={'id','checked','note'}or body['id']not in EVIDENCE or type(body['checked'])is not bool:raise ValueError('EVIDENCE_INVALID')
                data['evidence'][body['id']]={'checked':body['checked'],'note':cleaned(body['note'],160),'by':name,'at':stamp}
            elif action=='subject':
                if set(body)!={'form','name'}or body['form']not in {'manager','supervisor'}:raise ValueError('SUBJECT_INVALID')
                target=cleaned(body['name'],40)
                if not target:raise ValueError('SUBJECT_REQUIRED')
                if len(data['subjects'][body['form']])>=30:raise ValueError('SUBJECT_LIMIT')
                if any(s['name']==target for s in data['subjects'][body['form']]):raise ValueError('SUBJECT_EXISTS')
                subject={'id':uuid.uuid4().hex,'name':target};data['subjects'][body['form']].append(subject);result['subject']=subject
            elif action=='assessment':
                if set(body)!={'form','subject_id','answers','complete'}or type(body['complete'])is not bool:raise ValueError('ASSESSMENT_INVALID')
                form=body['form'];subject=body['subject_id'];answers,totals=validate_assessment(form,body['answers'],data['files'],data['subjects'],subject,body['complete']);subject_name=''
                day=answers['inspection_date'];actual_period=day[:4]+('-H1'if int(day[5:7])<=6 else'-H2')
                if actual_period!=request['period']:raise ValueError('DATE_PERIOD_MISMATCH')
                if form in {'manager','supervisor'}:subject_name=next(s['name']for s in data['subjects'][form]if s['id']==subject)
                assessment=data['assessments'].setdefault(form+':'+subject,{})
                draft={'data':answers,'result':totals,'subject_name':subject_name,'inspector':name,'actor_id':actor,'at':stamp};assessment['draft']=draft
                if body['complete']:
                    complete={**draft,'id':uuid.uuid4().hex,'revision':revision+1,'evidence':data['evidence'].copy(),'photo_metadata':[{**f,'caption':answers['photo_captions'].get(f['id'],f['caption'])}for f in data['files']if f['id']in answers['photo_ids']]};assessment['completed']=complete;result['completed_id']=complete['id']
                result['assessment']=assessment
            elif action=='parse':
                result['parse_job']=jobs.queue(c,key,data,actor,name,body,context_meta,request['period'],stamp)
            elif action=='apply_parse':
                job,answers,check=jobs.apply(c,key,data,body)
                clean,totals=validate_assessment(job['form'],answers,data['files'],data['subjects'],job['subject_id'],False)
                assessment=data['assessments'].setdefault(job['form']+':'+job['subject_id'],{})
                assessment['draft']={'data':clean,'result':totals,'subject_name':job['subject_name'],'inspector':name,'actor_id':actor,'at':stamp,'paper_job_id':body['job_id']}
                result['parse_check']=check
            elif action=='caption':
                if set(body)!={'id','caption'}:raise ValueError('PHOTO_CAPTION_INVALID')
                target=next((f for f in data['files']if f['id']==body['id']and f['kind']=='image'),None)
                if target is None:raise ValueError('PHOTO_MISSING')
                caption=cleaned(body['caption'],60)
                if len(caption.splitlines())>3:raise ValueError('PHOTO_CAPTION_INVALID')
                target['caption']=caption
            elif action=='attach':
                if set(body)!={'evidence_id','filename','caption'}or body['evidence_id']not in {*EVIDENCE,'paper_assessment'}or attachment is None:raise ValueError('ATTACHMENT_INVALID')
                if len(data['files'])>=100:raise ValueError('ATTACHMENT_LIMIT')
                raw,mime=attachment;filename=cleaned(body['filename'],180);suffix=Path(filename).suffix.casefold();caption=cleaned(body['caption'],60)
                if not 0<len(raw)<=15*1024*1024:raise ValueError('ATTACHMENT_SIZE_INVALID')
                photo=None
                if mime in {'image/jpeg','image/png','image/webp'}:photo=normalize_photo(raw);content=photo['data'];kind='image';extension='.jpg'
                else:
                    if suffix not in {'.pdf','.xlsx','.docx','.pptx','.hwp','.hwpx'}:raise ValueError('ATTACHMENT_TYPE_INVALID')
                    if suffix=='.pdf'and not raw.startswith(b'%PDF-')or suffix=='.hwp'and not raw.startswith(bytes.fromhex('D0CF11E0A1B11AE1'))or suffix in {'.xlsx','.docx','.pptx','.hwpx'}and not raw.startswith(b'PK\x03\x04'):raise ValueError('ATTACHMENT_TYPE_INVALID')
                    content=raw;kind='document';extension=suffix
                known=next((f for f in data['files']if f['sha256']==digest(content)and f['evidence_id']==body['evidence_id']),None)
                if known:result['file']=known
                else:
                    folder=self.root/'files'/digest(key.encode());folder.mkdir(parents=True,mode=0o700,exist_ok=True);fid=uuid.uuid4().hex;path=folder/(fid+extension)
                    with path.open('xb')as stream:stream.write(content)
                    new_path=path;meta={'id':fid,'evidence_id':body['evidence_id'],'filename':Path(filename).stem+extension,'extension':extension,'kind':kind,'sha256':digest(content),'bytes':len(content),'caption':caption,'by':name,'at':stamp}
                    if photo:meta.update(width=photo['width'],height=photo['height'])
                    data['files'].append(meta);result['file']=meta
            else:raise ValueError('ACTION_INVALID')
            try:
                revision+=1;c.execute('INSERT INTO contexts VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,data=excluded.data',(key,revision,encoded(data)))
                op_meta={'request':request,'result':result};c.execute('INSERT INTO events(context_id,revision,actor_id,at,action,data)VALUES(?,?,?,?,?,?)',(key,revision,actor,stamp,action,encoded(op_meta)))
                response={'revision':revision,'data':data,**result};c.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(key,request['request_key'],actor,payload_sha,encoded(response)));c.commit();return response
            except Exception:
                c.rollback()
                if new_path:new_path.unlink(missing_ok=True)
                raise
    def file(self,key,fid):
        state=self.load(key);meta=next((f for f in state['data']['files']if f['id']==fid),None)
        if meta is None:raise KeyError('FILE_MISSING')
        path=self.root/'files'/digest(key.encode())/(fid+meta['extension'])
        if path.is_symlink():raise ValueError('FILE_CHANGED')
        content=path.read_bytes()
        if len(content)!=meta['bytes']or digest(content)!=meta['sha256']:raise ValueError('FILE_CHANGED')
        return content,meta
    def export(self,key,form,subject,site,period,expected_snapshot=None):
        current=self.load(key);assessment=current['data']['assessments'].get(form+':'+subject,{});snapshot=assessment.get('completed')
        if not snapshot:raise ValueError('COMPLETE_FIRST')
        with closing(self.connect())as c:
            prior=c.execute('SELECT * FROM outputs WHERE context_id=? AND snapshot_id=? AND form=?',(key,expected_snapshot or snapshot['id'],form)).fetchone()
            if prior:return dict(prior)
        if expected_snapshot is not None and expected_snapshot!=snapshot['id']:raise Conflict('COMPLETED_VERSION_CHANGED')
        if form=='report':
            photos=[]
            for meta in snapshot['photo_metadata']:
                content,original=self.file(key,meta['id']);photos.append({'data':content,'width':meta['width'],'height':meta['height'],'sha256':meta['sha256'],'caption':meta['caption']})
            content=exports.pptx(snapshot,site,snapshot['inspector'],photos,period)
        elif form=='law':content=exports.hwpx(snapshot,site,snapshot['inspector'])
        else:content=exports.xlsx(form,snapshot,site,snapshot['inspector'])
        oid=uuid.uuid4().hex;folder=self.root/'outputs';folder.mkdir(mode=0o700,exist_ok=True);path=folder/(oid+'.'+FORMS[form]['format']);safe=lambda s:re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',s)[:80]
        filename=safe(FORMS[form]['title'])+'_'+safe(site)+'_'+period+('_'+safe(snapshot['subject_name'])if snapshot['subject_name']else'')+'.'+FORMS[form]['format'];at=datetime.now(timezone.utc).isoformat()
        with closing(self.connect())as c:
            c.execute('BEGIN IMMEDIATE');prior=c.execute('SELECT * FROM outputs WHERE context_id=? AND snapshot_id=? AND form=?',(key,snapshot['id'],form)).fetchone()
            if prior:return dict(prior)
            with path.open('xb')as stream:stream.write(content)
            try:
                c.execute('INSERT INTO outputs VALUES(?,?,?,?,?,?,?,?)',(oid,key,snapshot['id'],form,filename,digest(content),len(content),at));c.commit()
            except Exception:c.rollback();path.unlink(missing_ok=True);raise
            return dict(c.execute('SELECT * FROM outputs WHERE id=?',(oid,)).fetchone())
    def output_file(self,key,oid):
        with closing(self.connect())as c:row=c.execute('SELECT * FROM outputs WHERE id=? AND context_id=?',(oid,key)).fetchone()
        if row is None:raise KeyError('OUTPUT_MISSING')
        path=self.root/'outputs'/(oid+'.'+FORMS[row['form']]['format'])
        if path.is_symlink():raise ValueError('OUTPUT_CHANGED')
        content=path.read_bytes()
        if len(content)!=row['size']or digest(content)!=row['sha256']:raise ValueError('OUTPUT_CHANGED')
        return content,dict(row)
