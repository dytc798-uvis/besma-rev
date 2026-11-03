from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
import sqlite3,json,hashlib,uuid,re,io,zipfile,os
from .catalog import CATALOG,FORMS,EVIDENCE,blank,cleaned,validate_assessment,Conflict
from app.modules.inspection_reports.pptx_report import normalize_photo
from . import exports,jobs,monthly_sources,walkthrough
from .concurrent import merge_edits,confirm_evidence
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
        canonical={**{k:v for k,v in request.items()if k!='base'or v is not None},'attachment_sha256':digest(attachment[0])if attachment else None};payload_sha=digest(encoded(canonical).encode());stamp=datetime.now(timezone.utc).isoformat();new_path=None
        with closing(self.connect())as c:
            c.execute('BEGIN IMMEDIATE')
            replay=c.execute('SELECT payload_sha256,result FROM receipts WHERE context_id=? AND request_key=? AND actor_id=?',(key,request['request_key'],actor)).fetchone()
            if replay:
                if replay['payload_sha256']!=payload_sha:raise Conflict('REQUEST_CHANGED')
                return json.loads(replay['result'])
            row=c.execute('SELECT * FROM contexts WHERE id=?',(key,)).fetchone();revision=row['revision']if row else 0;data=json.loads(row['data'])if row else blank()
            if request['revision']>revision:raise Conflict('REVISION_INVALID')
            action=request['action'];body=request['data'];result={};op_meta={}
            if not isinstance(body,dict):raise ValueError('REQUEST_INVALID')
            if action=='evidence':
                if set(body)-{'id','checked','note','hold'}or not {'id','checked','note'}<=set(body)or body['id']not in EVIDENCE or type(body['checked'])is not bool or type(body.get('hold',False))is not bool:raise ValueError('EVIDENCE_INVALID')
                previous=data['evidence'].get(body['id'],{})
                edit={k:v for k,v in body.items()if k!='id'}
                if isinstance(request.get('base'),dict):edit=merge_edits(request['base'],edit,{k:previous.get(k,False if k in {'checked','hold'}else '')for k in ['checked','note','hold']})
                note=cleaned(edit['note'],160);hold=edit.get('hold',False)
                data['evidence'][body['id']]={'checked':bool(edit['checked']or note),'hold':hold,'note':note,'by':name,'at':stamp}
            elif action=='monthly-link':
                result['monthly_source']=monthly_sources.link(data,key,request['period'],body,actor,name,stamp)
            elif action=='monthly-links':
                result['monthly_sources']=monthly_sources.link_many(data,key,request['period'],body,actor,name,stamp)
            elif action=='monthly-unlink':
                result['monthly_source']=monthly_sources.unlink(data,body,name,stamp)
            elif action in {'criterion-check','evidence-photo'}:
                from .evidence_checks import mutate as factual_check
                result.update(factual_check(data,action,body,name,actor,stamp))
            elif action in {'walk-start','walk-item','walk-report','walk-guidance'}:
                result.update(walkthrough.mutate(data,action,body,request['period'],actor,name,stamp,context_meta))
            elif action=='subject':
                if set(body)!={'form','name'}or body['form']not in {'manager','supervisor'}:raise ValueError('SUBJECT_INVALID')
                target=cleaned(body['name'],40)
                if not target:raise ValueError('SUBJECT_REQUIRED')
                if len(data['subjects'][body['form']])>=30:raise ValueError('SUBJECT_LIMIT')
                if any(s['name']==target for s in data['subjects'][body['form']]):raise ValueError('SUBJECT_EXISTS')
                subject={'id':uuid.uuid4().hex,'name':target};data['subjects'][body['form']].append(subject);result['subject']=subject
            elif action=='assessment':
                if set(body)!={'form','subject_id','answers','complete'}or type(body['complete'])is not bool:raise ValueError('ASSESSMENT_INVALID')
                if isinstance(request.get('base'),dict):
                    current=data['assessments'].get(body['form']+':'+body['subject_id'],{}).get('draft',{}).get('data')or request['base']
                    body={**body,'answers':merge_edits(request['base'],body['answers'],current)}
                form=body['form'];subject=body['subject_id'];answers,totals=validate_assessment(form,body['answers'],data['files'],data['subjects'],subject,body['complete']);subject_name=''
                day=answers['inspection_date'];actual_period=day[:4]+('-H1'if int(day[5:7])<=6 else'-H2')
                if actual_period!=request['period']:raise ValueError('DATE_PERIOD_MISMATCH')
                if form in {'manager','supervisor'}:subject_name=next(s['name']for s in data['subjects'][form]if s['id']==subject)
                selected_run=walkthrough.assessment_run(data,answers.get('walkthrough_run_id',''),day,(context_meta or{}).get('public_id'))
                if body['complete']:
                    for assessment_key,prior in data['assessments'].items():
                        if assessment_key!=form+':'+subject and set(answers['signed_table_photo_ids'])&set(prior.get('completed',{}).get('data',{}).get('signed_table_photo_ids',[])):
                            raise ValueError('SIGNED_PHOTO_ALREADY_USED')
                assessment=data['assessments'].setdefault(form+':'+subject,{})
                draft={'criterion_evidence':walkthrough.criterion_evidence(data,form,subject),'data':answers,'result':totals,'subject_name':subject_name,'inspector':name,'actor_id':actor,'at':stamp};assessment['draft']=draft
                if body['complete']:
                    complete={**draft,'id':uuid.uuid4().hex,'revision':revision+1,'evidence':data['evidence'].copy(),'monthly_sources':[dict(r)for r in data.get('monthly_sources',[])if r['active']],'photo_metadata':[{**f,'caption':answers['photo_captions'].get(f['id'],f['caption'])}for f in data['files']if f['id']in answers['photo_ids']]};complete['inspection_run']=selected_run;assessment['completed']=complete;result['completed_id']=complete['id']
                result['assessment']=assessment
            elif action=='prior-assessment':
                if set(body)!={'form','file_id','inspector','date_label','note','rotation'}or body['form']!='law'or type(body['rotation'])is not int or body['rotation']not in {0,90,180,270}:raise ValueError('PRIOR_ASSESSMENT_INVALID')
                inspector=cleaned(body['inspector'],40);date_label=cleaned(body['date_label'],40);note=cleaned(body['note'],240)
                if not inspector or not date_label:raise ValueError('PRIOR_ASSESSMENT_INVALID')
                content,meta=self.file(key,body['file_id'])
                if meta['evidence_id']!='paper_assessment'or meta['extension']!='.pdf':raise ValueError('PDF_REQUIRED')
                from .pdf_preview import information
                information(content,meta)
                fields={'form':'law','file':dict(meta),'inspector':inspector,'date_label':date_label,'note':note,'rotation':body['rotation']}
                prior=data.setdefault('prior_assessments',{}).get('law')
                if not prior or any(prior.get(k)!=v for k,v in fields.items()):
                    prior={**fields,'id':uuid.uuid4().hex,'at':stamp,'actor_id':actor,'by':name}
                    data.setdefault('prior_assessment_history',[]).append(prior);data['prior_assessments']['law']=prior
                result['prior_assessment']=prior
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
                if set(body)-{'evidence_id','filename','caption','walk_run_id','criterion_id','photo_stage','evidence_note'}or not {'evidence_id','filename','caption'}<=set(body)or body['evidence_id']not in {*EVIDENCE,'paper_assessment','paper_completion'}or attachment is None:raise ValueError('ATTACHMENT_INVALID')
                photo_target=walkthrough.photo_target(data,body,context_meta)
                evidence_note=cleaned(body.get('evidence_note',''),160)
                if evidence_note and not photo_target:raise ValueError('PHOTO_CONTEXT_REQUIRED')
                if photo_target and attachment[1]not in {'image/jpeg','image/png','image/webp'}:raise ValueError('ATTACHMENT_TYPE_INVALID')
                if len(data['files'])>=100:raise ValueError('ATTACHMENT_LIMIT')
                raw,mime=attachment;filename=cleaned(body['filename'],180);suffix=Path(filename).suffix.casefold();caption=cleaned(body['caption'],60)
                if not 0<len(raw)<=15*1024*1024:raise ValueError('ATTACHMENT_SIZE_INVALID')
                photo=None
                if body['evidence_id']=='paper_completion':
                    from .pdf_preview import document
                    if suffix!='.pdf':raise ValueError('PDF_REQUIRED')
                    with document(raw):pass
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
                if body['evidence_id']=='paper_completion':
                    meta=result['file']
                    prior=data.get('paper_completion')
                    if not prior or prior['file']['id']!=meta['id']:
                        completion={'id':uuid.uuid4().hex,'file':dict(meta),'actor_id':actor,'by':name,'at':stamp,'period':request['period']}
                        data.setdefault('paper_completion_history',[]).append(completion)
                        data['paper_completion']=completion
                    result['paper_completion']=data['paper_completion']
                if body['evidence_id']in EVIDENCE and result['file']['kind']=='image':confirm_evidence(data,body['evidence_id'],name,stamp)
                if photo_target:
                    result['field_photo']=walkthrough.record_photo(photo_target,body,result['file'],actor,name,stamp)
                    if evidence_note:data['evidence'][body['evidence_id']]={**data['evidence'].get(body['evidence_id'],{}),'note':evidence_note,'by':name,'at':stamp}
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
