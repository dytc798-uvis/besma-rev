"""Private supervisor signing copies; preparing a copy never completes an assessment."""
from pathlib import Path
from copy import deepcopy
from datetime import date
import json,hashlib,re,os
from .catalog import CATALOG,FORMS,report_schema,validate_assessment,Conflict
from . import signature_jobs,site_profile

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def sha(raw):return hashlib.sha256(raw).hexdigest()

def prepare(store,key,row,period,user,profile):
    state=store.load(key);snapshots={};missing=[];eligible=True
    for form in ['report','law']:
        record=state['data']['assessments'].get(form+':site',{});source=record.get('draft')or record.get('completed')or{}
        completed=record.get('completed');eligible=eligible and bool(completed and record.get('draft',{}).get('data')==completed.get('data'))
        version=source.get('criteria_version',CATALOG['version']);schema=report_schema({'criteria_version':version})if form=='report'else FORMS[form]
        data=deepcopy(source.get('data')or{});data.setdefault('inspection_date',row.scheduled_date.isoformat());data.setdefault('summary','');data.setdefault('photo_ids',[]);data.setdefault('photo_captions',{});data.setdefault('improvements',[]);data.setdefault('answers',{})
        for q in schema['criteria']:data['answers'].setdefault(q['id'],{'value':None,'note':''})
        normalized,result=validate_assessment(form,data,state['data']['files'],state['data']['subjects'],'site',False)
        unanswered=[str(i)+'. '+q['title']for i,q in enumerate(schema['criteria'],1)if normalized['answers'][q['id']]['value']is None]
        if unanswered:eligible=False;missing.append({'label':schema['title']+' '+str(len(unanswered))+'개 항목 작성','items':unanswered})
        if not normalized.get('summary','').strip():missing.append({'label':schema['title']+' 총평 작성','items':[]})
        if unanswered and form=='report':result['score']=None
        snapshot={**source,'form':form,'criteria_version':version,'inspector':source.get('inspector')or user.name,'data':normalized,'result':result}
        snapshot['id']=sha(encoded(snapshot).encode())[:32];snapshots[form]=snapshot
    if not profile.get('site_manager'):missing.append({'label':'현장소장 이름 입력','items':[]})
    fingerprint=sha(encoded({'key':key,'snapshots':snapshots,'profile':profile}).encode())
    return {'eligible':eligible,'fingerprint':fingerprint,'missing':missing,'snapshots':snapshots}

def public(prepared):return {k:prepared[k]for k in ['eligible','fingerprint','missing']}

def queue(store,key,user,row,period,body,profile):
    if set(body)!={'request_key','fingerprint','allow_incomplete'}or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',body['request_key'])or type(body['allow_incomplete'])is not bool:raise ValueError('SIGNATURE_REQUEST_INVALID')
    prepared=prepare(store,key,row,period,user,profile)
    if not prepared['eligible']:
        from fastapi import HTTPException
        raise HTTPException(422,'반기평가와 법령점검표를 모두 작성 완료한 뒤 다운로드해 주세요.')
    if body['fingerprint']!=prepared['fingerprint']:raise Conflict('SIGNATURE_SOURCE_CHANGED')
    if prepared['missing']and not body['allow_incomplete']:raise ValueError('SIGNATURE_INCOMPLETE_CONFIRM')
    jid=sha((key+'|'+str(user.id)+'|'+body['request_key']).encode())[:32];folder=store.root/'signature-bundles';folder.mkdir(mode=0o700,exist_ok=True);path=folder/(jid+'.json')
    if path.exists():
        prior=load(store,key,user.id,jid)
        if prior['fingerprint']!=prepared['fingerprint']:raise Conflict('SIGNATURE_SOURCE_CHANGED')
        return status(store,key,user.id,jid)
    jobs=[]
    for form,snapshot in prepared['snapshots'].items():
        request={'request_key':'bundle-'+jid+'-'+form,'form':form,'subject_id':'site','snapshot_id':snapshot['id'],'purpose':'SIGNATURE'}
        job=signature_jobs.queue(store,key,user,row,period,request,profile,prepared_snapshot=snapshot);jobs.append({'id':job['id'],'form':form})
    site=row.title.removeprefix('[점검] ').strip();filename=re.sub(r'[\\/:*?"<>|\x00-\x1f]','_',site+'_소장서명용_반기평가_법령점검표.pdf')
    value={'id':jid,'context_id':key,'owner':user.id,'fingerprint':prepared['fingerprint'],'missing':prepared['missing'],'filename':filename,'jobs':jobs}
    try:
        with path.open('x',encoding='utf8')as f:f.write(encoded(value))
        path.chmod(0o600)
    except FileExistsError:pass
    return status(store,key,user.id,jid)

def load(store,key,owner,jid):
    if not re.fullmatch('[0-9a-f]{32}',jid):raise KeyError('SIGNATURE_MISSING')
    path=store.root/'signature-bundles'/(jid+'.json')
    if not path.exists():raise KeyError('SIGNATURE_MISSING')
    value=json.loads(path.read_text('utf8'))
    if value['owner']!=owner or value['context_id']!=key:raise KeyError('SIGNATURE_MISSING')
    return value

def status(store,key,owner,jid):
    value=load(store,key,owner,jid);jobs=[]
    with signature_jobs.connect(store)as connection:
        for part in value['jobs']:
            row=connection.execute('SELECT * FROM jobs WHERE id=? AND context_id=? AND owner_id=?',(part['id'],key,owner)).fetchone();jobs.append(signature_jobs.visible(row)if row else None)
    if any(j is None for j in jobs):raise KeyError('SIGNATURE_MISSING')
    state='FAILED'if any(j['status']=='FAILED'for j in jobs)else'READY'if all(j['status']=='READY'for j in jobs)else'RENDERING'
    result=None
    if state=='READY':
        raw=merged(store,key,owner,jid);result={'sha256':sha(raw),'bytes':len(raw)}
    return {'id':jid,'status':state,'filename':value['filename'],'missing':value['missing'],'result':result,'delivery_status':'NOT_REQUESTED'}

def merged(store,key,owner,jid):
    value=load(store,key,owner,jid);target=store.root/'signature-bundles'/(jid+'.pdf')
    import fitz,fcntl
    lock=target.with_suffix('.lock');proof=target.with_suffix('.result.json')
    with lock.open('a+b')as guard:
        lock.chmod(0o600);fcntl.flock(guard.fileno(),fcntl.LOCK_EX)
        if target.exists()and proof.exists():
            if target.is_symlink()or proof.is_symlink():raise ValueError('SIGNATURE_OUTPUT_CHANGED')
            raw=target.read_bytes();record=json.loads(proof.read_text())
            if len(raw)!=record['bytes']or sha(raw)!=record['sha256']:raise ValueError('SIGNATURE_OUTPUT_CHANGED')
            return raw
        with fitz.open()as pdf:
            for job in value['jobs']:
                raw,_=signature_jobs.output(store,key,owner,job['id'])
                with fitz.open(stream=raw,filetype='pdf')as part:pdf.insert_pdf(part)
            if not 1<=len(pdf)<=60:raise ValueError('PDF_INVALID')
            raw=pdf.tobytes(garbage=4,deflate=True);pages=len(pdf)
        if not 100<len(raw)<=30*1024*1024:raise ValueError('PDF_INVALID')
        target.write_bytes(raw);target.chmod(0o600);proof.write_text(encoded({'sha256':sha(raw),'bytes':len(raw),'pages':pages}));proof.chmod(0o600)
        return raw
