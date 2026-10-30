"""Strict PDF transcription contract. A transcription never completes an evaluation."""
from datetime import date
import copy,re
from .catalog import FORMS,cleaned

def schema(form=None):
    fields={'form':{'type':'string','enum':list(FORMS)+['unknown']},'site_name':{'type':'string'},'subject_name':{'type':'string'},'inspection_date':{'type':'string'},'summary':{'type':'string'},'total_score':{'type':['number','null']},'answers':{'type':'array','items':{'type':'object','additionalProperties':False,'properties':{'id':{'type':'string'},'value':{'type':['string','integer','null']},'note':{'type':'string'},'confidence':{'type':'number'},'page':{'type':'integer'},'observed':{'type':'string'}},'required':['id','value','note','confidence','page','observed']}}}
    if form in FORMS:
        scoring=FORMS[form]['scoring'];fields['answers']['items']['properties']['id']={'type':'string','enum':[c['id']for c in FORMS[form]['criteria']]}
        fields['answers']['items']['properties']['value']=({'type':['integer','null']}if scoring=='POINTS'else{'type':['string','null'],'enum':(['EXCELLENT','NORMAL','POOR',None]if scoring=='THREE_LEVEL'else['PASS','FAIL','NA',None])})
    return {'type':'object','additionalProperties':False,'properties':fields,'required':list(fields)}

def normalize(s):return re.sub(r'[^가-힣A-Za-z0-9]','',s).casefold()

def validate(value,form,pages):
    if not isinstance(value,dict)or set(value)!=set(schema()['required']):raise ValueError('PARSE_RESULT_INVALID')
    if value['form']not in {*FORMS,'unknown'}:raise ValueError('PARSE_FORM_INVALID')
    result={k:cleaned(value[k],limit)for k,limit in [('site_name',180),('subject_name',40),('inspection_date',10),('summary',240)]}
    if result['inspection_date']:date.fromisoformat(result['inspection_date'])
    total=value['total_score']
    if total is not None and(type(total)not in{int,float}or not 0<=total<=100):raise ValueError('PARSE_TOTAL_INVALID')
    criteria={r['id']:r for r in FORMS[form]['criteria']};answers=value['answers'];seen=set();rows=[]
    if not isinstance(answers,list)or len(answers)>len(criteria):raise ValueError('PARSE_ANSWERS_INVALID')
    for row in answers:
        if not isinstance(row,dict)or set(row)!={'id','value','note','confidence','page','observed'}or row['id']not in criteria or row['id']in seen:raise ValueError('PARSE_ANSWERS_INVALID')
        seen.add(row['id']);v=row['value'];scoring=FORMS[form]['scoring']
        if v is not None:
            if scoring=='POINTS'and(type(v)is not int or not 0<=v<=criteria[row['id']]['max_score']):raise ValueError('PARSE_SCORE_INVALID')
            if scoring=='THREE_LEVEL'and v not in {'EXCELLENT','NORMAL','POOR'}:raise ValueError('PARSE_SCORE_INVALID')
            if scoring=='COMPLIANCE'and v not in {'PASS','FAIL','NA'}:raise ValueError('PARSE_VERDICT_INVALID')
        if type(row['confidence'])not in {float,int}or not 0<=row['confidence']<=1 or type(row['page'])is not int or row['page']not in pages:raise ValueError('PARSE_REFERENCE_INVALID')
        note=cleaned(row['note'],30 if form=='law'else 20);observed=cleaned(row['observed'],160)
        ready=v is not None and row['confidence']>=.95 and bool(observed)and(v!='NA'or bool(note))
        rows.append({**row,'note':note,'observed':observed,'eligible':ready})
    return {**result,'form':value['form'],'total_score':total,'answers':rows}

def merge(result,job,data,selected=None,confirm_identity=False):
    """Merge only into a draft. Existing completed snapshots are never mutated."""
    form=job['form'];key=form+':'+job['subject_id'];prior=data['assessments'].get(key,{}).get('draft',{});answers=copy.deepcopy(prior.get('data')or{'answers':{},'summary':'','inspection_date':'','photo_ids':[],'photo_captions':{},'improvements':[]})
    identity=(result['form']==form and normalize(result['site_name'])==normalize(job['site_name'])and (not FORMS[form].get('needs_subject')or normalize(result['subject_name'])==normalize(job['subject_name'])))
    mismatched=result['form']not in {form,'unknown'}or bool(result['site_name'])and normalize(result['site_name'])!=normalize(job['site_name'])or bool(result['subject_name'])and FORMS[form].get('needs_subject')and normalize(result['subject_name'])!=normalize(job['subject_name'])
    day=result['inspection_date'];day_ok=bool(day)and day[:4]+('-H1'if int(day[5:7])<=6 else'-H2')==job['period']
    total_ok=True
    rows=result['answers'];schema=FORMS[form]
    if result['total_score']is not None and schema['scoring']!='COMPLIANCE':
        if len(rows)!=len(schema['criteria'])or any(r['value']is None for r in rows):total_ok=False
        else:
            maxima={r['id']:r['max_score']for r in schema['criteria']}
            actual=sum(r['value']if schema['scoring']=='POINTS'else maxima[r['id']]*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[r['value']]for r in rows)
            total_ok=abs(actual-result['total_score'])<.001
    automatic=selected is None
    allowed=not mismatched and total_ok and day_ok and(identity or confirm_identity)
    if automatic and prior!=job['baseline']:allowed=False
    applied=[];pending=[]
    for item in rows:
        previous=answers['answers'].get(item['id'],{});different=previous.get('value')is not None and previous.get('value')!=item['value']
        chosen=item['id']in selected if selected is not None else item['eligible']and not different
        if allowed and chosen and item['value']is not None:
            answers['answers'][item['id']]={'value':item['value'],'note':item['note']};applied.append(item['id'])
        elif item['value']is not None:pending.append(item['id'])
    if allowed and applied:
        answers['inspection_date']=day
        if result['summary']and not answers['summary']:answers['summary']=result['summary']
        answers['entry_mode']='PAPER_PDF';answers['paper_file_ids']=list(dict.fromkeys([*answers.get('paper_file_ids',[]),job['file_id']]))
    return answers,{'applied':applied,'pending':pending,'identity_matched':identity,'identity_mismatched':bool(mismatched),'date_matched':day_ok,'total_matched':total_ok,'draft_changed':prior!=job['baseline']}
