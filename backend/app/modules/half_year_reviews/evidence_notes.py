"""Copy the first saved material comment once; preserve evaluator prose/history."""
from .catalog import FORMS

def apply(data,form,subject,answers,stamp):
    key=form+':'+subject
    if data['assessments'].get(key,{}).get('completed'):return
    links=data.setdefault('material_comment_links',{}).setdefault(key,{})
    for q in FORMS[form]['criteria']:
        for evidence in q['evidence']:
            note=data['evidence'].get(evidence,{}).get('note','').strip()
            marker=q['id']+':'+evidence
            if not note or marker in links:continue
            answer=answers.setdefault('answers',{}).setdefault(q['id'],{'value':None,'note':''})
            old=answer.get('note','')
            if note not in old.split('\n\n'):answer['note']=old+('\n\n'if old else'')+note
            links[marker]={'at':stamp,'note':note}

def refresh_existing(data,stamp):
    for key,assessment in data['assessments'].items():
        if assessment.get('completed')or not assessment.get('draft'):continue
        form,subject=key.split(':',1)
        if form not in FORMS:continue
        apply(data,form,subject,assessment['draft']['data'],stamp)
