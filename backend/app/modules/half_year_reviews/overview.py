"""Owner-authorized, read-only summaries of persisted evaluation snapshots."""
from contextlib import closing
from pathlib import Path
import json,sqlite3
from .catalog import CATALOG,FORMS,context_key

def summarize(data):
    forms=[];completed=0;required=0
    assessments=data.get('assessments',{})
    for form in CATALOG['order']:
        schema=FORMS[form]
        subjects=data.get('subjects',{}).get(form,[])if schema.get('needs_subject')else[{'id':'site','name':''}]
        required+=max(1,len(subjects))
        for subject in subjects:
            saved=assessments.get(form+':'+subject['id'],{});snapshot=saved.get('completed')
            if snapshot:
                completed+=1
                answers=snapshot['data'].get('answers',{})
                forms.append({'form':form,'subject_id':subject['id'],'subject_name':snapshot.get('subject_name',''),
                    'snapshot_id':snapshot['id'],'at':snapshot['at'],'inspection_date':snapshot['data']['inspection_date'],
                    'score':snapshot.get('result',{}).get('score'),
                    'verdicts':{v:sum(a.get('value')==v for a in answers.values())for v in ['PASS','FAIL','NA']}if schema['scoring']=='COMPLIANCE'else None,
                    'draft_changed':saved.get('draft',{}).get('data')!=snapshot['data']})
    prior=data.get('prior_assessments',{}).get('law')
    if prior and any(f.get('id')==prior.get('file',{}).get('id')and f.get('sha256')==prior['file'].get('sha256')and f.get('evidence_id')=='paper_assessment'and f.get('extension')=='.pdf'for f in data.get('files',[])):
        if not any(f['form']=='law'for f in forms):
            completed+=1;forms.append({'form':'law','subject_id':'site','subject_name':'','source_type':'PRIOR_PDF','score':None,'verdicts':None,'inspector':prior['inspector'],'date_label':prior['date_label'],'file':prior['file']})
    else:prior=None
    active=bool(completed or any(v.get('draft')for v in assessments.values())or data.get('files')or
        any(r.get('items')or r.get('field_photos')for r in data.get('inspection_runs',[])))
    paper=data.get('paper_completion')
    if paper and not any(f.get('id')==paper.get('file',{}).get('id')and f.get('sha256')==paper['file'].get('sha256')and f.get('evidence_id')=='paper_completion'and f.get('extension')=='.pdf'for f in data.get('files',[])):paper=None
    reported=data.get('reported_completion')
    # Administrative completion is recorded separately from answers and uploaded evidence.
    if not isinstance(reported,dict)or reported.get('status')!='COMPLETED'or not reported.get('inspector')or not reported.get('inspection_date')or not reported.get('id'):reported=None
    form_status={}
    for kind in CATALOG['order']:
        subjects=data.get('subjects',{}).get(kind,[])if FORMS[kind].get('needs_subject')else[{'id':'site'}]
        required_kind=max(1,len(subjects));records=[assessments.get(kind+':'+person['id'],{})for person in subjects]
        done_kind=sum(bool(a.get('completed'))and a.get('draft',{}).get('data')==a['completed']['data']for a in records)
        prior_kind=kind=='law'and prior is not None
        form_status[kind]={'completed':bool(paper or reported or prior_kind or done_kind==required_kind),'required':required_kind,'written':done_kind,'started':bool(prior_kind or any(a.get('draft')for a in records))}
    return {'status':'COMPLETED'if paper or reported else'IN_PROGRESS'if active else'NOT_STARTED',
        'form_status':form_status,'completed':completed,'required':required,'forms':forms,'paper_completion':paper,'reported_completion':reported,'prior_assessments':{'law':prior}if prior else{},'screen_completed':bool(completed==required and required and not any(f.get('source_type')=='PRIOR_PDF'for f in forms))}

def summaries(root,rows):
    targets=[(r,r.scheduled_date.strftime('%Y')+('-H1'if r.scheduled_date.month<=6 else'-H2'))for r in rows]
    keys=list({context_key(r,p)for r,p in targets});data={}
    path=Path(root)/'reviews.sqlite3'
    if keys and path.exists():
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10))as db:
            for start in range(0,len(keys),400):
                group=keys[start:start+400]
                data.update({key:json.loads(raw)for key,raw in db.execute('SELECT id,data FROM contexts WHERE id IN ('+','.join('?'for _ in group)+')',group)})
    return [{'public_id':r.public_id,'period':p,**summarize(data.get(context_key(r,p),{}))}for r,p in targets]
