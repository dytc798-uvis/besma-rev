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
    active=bool(completed or any(v.get('draft')for v in assessments.values())or data.get('files')or
        any(r.get('items')or r.get('field_photos')for r in data.get('inspection_runs',[])))
    paper=data.get('paper_completion')
    if paper and not any(f.get('id')==paper.get('file',{}).get('id')and f.get('sha256')==paper['file'].get('sha256')and f.get('evidence_id')=='paper_completion'and f.get('extension')=='.pdf'for f in data.get('files',[])):paper=None
    return {'status':'COMPLETED'if paper else'IN_PROGRESS'if active else'NOT_STARTED',
        'completed':completed,'required':required,'forms':forms,'paper_completion':paper,'screen_completed':bool(completed==required and required)}

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
