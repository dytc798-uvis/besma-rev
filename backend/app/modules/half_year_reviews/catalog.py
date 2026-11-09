from pathlib import Path
from datetime import date
import json,re,math
ASSETS=Path(__file__).parent/'assets'
CATALOG=json.loads((ASSETS/'catalog.json').read_text('utf8'))
FORMS=CATALOG['forms'];EVIDENCE={r['id']:r for r in CATALOG['evidence']}
class Conflict(ValueError):pass
def period_value(value):
    if not isinstance(value,str)or not re.fullmatch(r'20\d{2}-H[12]',value):raise ValueError('PERIOD_INVALID')
    return value
def context_key(row,period):
    period_value(period)
    match=re.fullmatch(r'inspection:\d{6}:(site-\d{1,6})(?::[A-Za-z0-9_-]+)?',row.client_item_key or'')
    return (match.group(1)if match else'plan-'+row.public_id)+'|'+period
def blank():return {'evidence':{},'subjects':{'manager':[],'supervisor':[]},'assessments':{},'files':[]}
def cleaned(value,limit):
    if not isinstance(value,str)or (limit is not None and len(value)>limit) or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value):raise ValueError('TEXT_INVALID')
    return value.strip()
def validate_assessment(form,data,files,subjects,subject_id,complete):
    if form not in FORMS or not isinstance(data,dict)or set(data)-{'answers','summary','inspection_date','photo_ids','photo_captions','improvements','entry_mode','paper_file_ids','walkthrough_run_id','signed_table_photo_ids','required_signatures_confirmed','signed_pages_complete'}:raise ValueError('ASSESSMENT_INVALID')
    schema=FORMS[form]
    if form=='supervisor':
        from .supervisor_group import subject as grouped
        group=grouped({'subjects':subjects})
        if group is None or subject_id!=group['id']:raise ValueError('SUBJECT_REQUIRED')
    elif schema.get('needs_subject'):
        subject=next((r for r in subjects[form]if r['id']==subject_id),None)
        if subject is None:raise ValueError('SUBJECT_REQUIRED')
    elif subject_id!='site':raise ValueError('SUBJECT_INVALID')
    day=cleaned(data.get('inspection_date',''),10);date.fromisoformat(day)
    summary=cleaned(data.get('summary',''),None)
    answers=data.get('answers',{})
    if not isinstance(answers,dict)or set(answers)-{r['id']for r in schema['criteria']}:raise ValueError('ANSWER_INVALID')
    result={};missing=0;score=0;field_score=0;headquarters_pending=False
    for criterion in schema['criteria']:
        entry=answers.get(criterion['id'],{})
        if not isinstance(entry,dict)or set(entry)-{'value','note'}:raise ValueError('ANSWER_INVALID')
        value=entry.get('value');note=cleaned(entry.get('note',''),None)
        if value is None:
            if form=='manager'and criterion.get('evaluation_scope')=='HEADQUARTERS':headquarters_pending=True
            else:missing+=1
        elif form=='report'and type(value)is int:
            if not 0<=value<=criterion['max_score']:raise ValueError('SCORE_INVALID')
            score+=value
        elif criterion.get('scoring',schema['scoring'])=='THREE_LEVEL':
            if value not in {'EXCELLENT','NORMAL','POOR'}:raise ValueError('SCORE_INVALID')
            score+=criterion['max_score']*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[value]
        elif criterion.get('scoring',schema['scoring'])=='POINTS':
            if form=='report'and criterion['id']=='p10'and value in {'EXCELLENT','NORMAL','POOR'}:score+=criterion['max_score']*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[value]
            elif type(value)is not int or not 0<=value<=criterion['max_score']:raise ValueError('SCORE_INVALID')
            else:score+=value
        elif value not in {'PASS','FAIL','NA'}or value=='NA'and not note:raise ValueError('VERDICT_INVALID')
        result[criterion['id']]={'value':value,'note':note}
        if form=='manager'and criterion.get('evaluation_scope')!='HEADQUARTERS'and type(value)is int:field_score+=value
    photos=data.get('photo_ids',[])
    if not isinstance(photos,list)or len(photos)>24 or len(set(photos))!=len(photos)or any(not isinstance(p,str)for p in photos):raise ValueError('PHOTOS_INVALID')
    known={r['id']for r in files if r['kind']=='image'}
    if not set(photos)<=known:raise ValueError('PHOTO_NOT_IN_THIS_REVIEW')
    captions=data.get('photo_captions',{})
    if not isinstance(captions,dict)or not set(captions)<=known:raise ValueError('PHOTO_CAPTION_INVALID')
    captions={key:cleaned(value,60)for key,value in captions.items()}
    if any(len(value.splitlines())>3 for value in captions.values()):raise ValueError('PHOTO_CAPTION_INVALID')
    improvements=data.get('improvements',[])
    if not isinstance(improvements,list)or len(improvements)>5:raise ValueError('IMPROVEMENTS_INVALID')
    clean_improvements=[]
    for item in improvements:
        if not isinstance(item,dict)or set(item)-{'finding','action','owner','due'}:raise ValueError('IMPROVEMENTS_INVALID')
        clean_improvements.append({key:cleaned(item.get(key,''),None if key in {'finding','action'}else 15)for key in ['finding','action','owner','due']})
    entry_mode=data.get('entry_mode','SCREEN')
    if entry_mode not in {'SCREEN','PAPER','PAPER_PDF'}:raise ValueError('ENTRY_MODE_INVALID')
    paper_ids=data.get('paper_file_ids',[])
    if not isinstance(paper_ids,list)or len(paper_ids)>10 or len(set(paper_ids))!=len(paper_ids)or not set(paper_ids)<={r['id']for r in files}:raise ValueError('PAPER_FILES_INVALID')
    run_id=data.get('walkthrough_run_id','')
    if not isinstance(run_id,str)or run_id and not re.fullmatch('[a-f0-9]{32}',run_id):raise ValueError('WALK_RUN_INVALID')
    signed=data.get('signed_table_photo_ids',[])
    signed_flag=data.get('required_signatures_confirmed',False);pages_flag=data.get('signed_pages_complete',False)
    signed_known={r['id']for r in files if r['kind']=='image'and r['evidence_id']=='paper_assessment'}
    if type(signed_flag)is not bool or type(pages_flag)is not bool or not isinstance(signed,list)or len(signed)>10 or any(not isinstance(p,str)for p in signed)or len(set(signed))!=len(signed)or not set(signed)<=signed_known:raise ValueError('SIGNED_PHOTO_INVALID')
    if complete and missing:raise ValueError('UNREVIEWED_ITEMS_REMAIN')
    return {'answers':result,'summary':summary,'inspection_date':day,'photo_ids':photos,'photo_captions':captions,'improvements':clean_improvements,'entry_mode':entry_mode,'paper_file_ids':paper_ids,'walkthrough_run_id':run_id,'signed_table_photo_ids':signed,'required_signatures_confirmed':signed_flag,'signed_pages_complete':pages_flag}, {'missing':missing,'score':score if not missing and not headquarters_pending and schema['scoring']!='COMPLIANCE'else None,'graded':len([q for q in schema['criteria']if q.get('evaluation_scope')!='HEADQUARTERS'])-missing,**({'field_score':field_score,'field_max_score':93,'headquarters_pending':headquarters_pending,'headquarters_score':result['m10']['value'],'max_score':100}if form=='manager'else{})}


def report_schema(snapshot=None):
    """Keep historical completed forms tied to their original criterion text."""
    if snapshot is not None and snapshot.get("criteria_version",1)<2:
        return json.loads((ASSETS/"report-criteria-v1.json").read_text("utf8"))
    if snapshot is not None and snapshot.get("criteria_version",1)<3:
        return json.loads((ASSETS/"report-criteria-v2.json").read_text("utf8"))
    return FORMS["report"]


def criterion_points(criterion,value):
    if value is None:raise ValueError('COMPLETE_FIRST')
    if not isinstance(value,str):
        if type(value)is not int or not 0<=value<=criterion['max_score']:raise ValueError('SCORE_INVALID')
        return value
    return criterion['max_score']*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[value]
