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
    if not isinstance(value,str)or len(value)>limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value):raise ValueError('TEXT_INVALID')
    return value.strip()
def validate_assessment(form,data,files,subjects,subject_id,complete):
    if form not in FORMS or not isinstance(data,dict)or set(data)-{'answers','summary','inspection_date','photo_ids','photo_captions','improvements','entry_mode','paper_file_ids'}:raise ValueError('ASSESSMENT_INVALID')
    schema=FORMS[form]
    if schema.get('needs_subject'):
        subject=next((r for r in subjects[form]if r['id']==subject_id),None)
        if subject is None:raise ValueError('SUBJECT_REQUIRED')
    elif subject_id!='site':raise ValueError('SUBJECT_INVALID')
    day=cleaned(data.get('inspection_date',''),10);date.fromisoformat(day)
    summary=cleaned(data.get('summary',''),240)
    if len(summary.splitlines())>6:raise ValueError('SUMMARY_TOO_LONG')
    answers=data.get('answers',{})
    if not isinstance(answers,dict)or set(answers)-{r['id']for r in schema['criteria']}:raise ValueError('ANSWER_INVALID')
    result={};missing=0;score=0
    for criterion in schema['criteria']:
        entry=answers.get(criterion['id'],{})
        if not isinstance(entry,dict)or set(entry)-{'value','note'}:raise ValueError('ANSWER_INVALID')
        value=entry.get('value');note=cleaned(entry.get('note',''),30 if form=='law'else 20)
        if len(note.splitlines())>2:raise ValueError('NOTE_TOO_LONG')
        if value is None:missing+=1
        elif schema['scoring']=='THREE_LEVEL':
            if value not in {'EXCELLENT','NORMAL','POOR'}:raise ValueError('SCORE_INVALID')
            score+=criterion['max_score']*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[value]
        elif schema['scoring']=='POINTS':
            if type(value)is not int or not 0<=value<=criterion['max_score']:raise ValueError('SCORE_INVALID')
            score+=value
        elif value not in {'PASS','FAIL','NA'}or value=='NA'and not note:raise ValueError('VERDICT_INVALID')
        result[criterion['id']]={'value':value,'note':note}
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
        clean_improvements.append({key:cleaned(item.get(key,''),40 if key in {'finding','action'}else 15)for key in ['finding','action','owner','due']})
    entry_mode=data.get('entry_mode','SCREEN')
    if entry_mode not in {'SCREEN','PAPER','PAPER_PDF'}:raise ValueError('ENTRY_MODE_INVALID')
    paper_ids=data.get('paper_file_ids',[])
    if not isinstance(paper_ids,list)or len(paper_ids)>10 or len(set(paper_ids))!=len(paper_ids)or not set(paper_ids)<={r['id']for r in files}:raise ValueError('PAPER_FILES_INVALID')
    if complete and(missing or form=='report'and not photos and entry_mode=='SCREEN'):raise ValueError('UNREVIEWED_ITEMS_REMAIN')
    return {'answers':result,'summary':summary,'inspection_date':day,'photo_ids':photos,'photo_captions':captions,'improvements':clean_improvements,'entry_mode':entry_mode,'paper_file_ids':paper_ids}, {'missing':missing,'score':score if not missing and schema['scoring']!='COMPLIANCE'else None,'graded':len(schema['criteria'])-missing}
