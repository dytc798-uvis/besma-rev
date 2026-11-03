"""Factual checks and revisit bookmarks are independent of grades."""
from .catalog import FORMS,cleaned

def mutate(data,action,body,name,actor,stamp):
    if action=='evidence-photo':
        if set(body)!={'file_id','checked'}or type(body['checked'])is not bool:raise ValueError('PHOTO_CHECK_INVALID')
        photo=next((f for f in data['files']if f['id']==body['file_id']and f['kind']=='image'and f['evidence_id']not in {'paper_assessment','paper_completion'}),None)
        if photo is None:raise ValueError('PHOTO_CHECK_INVALID')
        record={'checked':body['checked'],'evidence_id':photo['evidence_id'],'by':name,'actor_id':actor,'at':stamp}
        data.setdefault('evidence_photo_checks',{})[photo['id']]=record
        return {'photo_check':record}
    if set(body)!={'form','subject_id','criterion_id','checked','hold','evidence_ids'}or type(body['checked'])is not bool or type(body['hold'])is not bool:raise ValueError('CRITERION_CHECK_INVALID')
    form=body['form'];subject=body['subject_id'];schema=FORMS.get(form)
    if not schema:raise ValueError('FORM_INVALID')
    if schema.get('needs_subject'):
        if not any(s['id']==subject for s in data['subjects'][form]):raise ValueError('SUBJECT_REQUIRED')
    elif subject!='site':raise ValueError('SUBJECT_INVALID')
    criterion=next((c for c in schema['criteria']if c['id']==body['criterion_id']),None)
    ids=body['evidence_ids']
    if not criterion or not isinstance(ids,list)or any(not isinstance(x,str)for x in ids)or len(set(ids))!=len(ids)or not set(ids)<=set(criterion['evidence']):raise ValueError('CRITERION_CHECK_INVALID')
    record={'checked':body['checked'],'hold':body['hold'],'evidence_ids':ids,'by':name,'actor_id':actor,'at':stamp}
    data.setdefault('criterion_checks',{})[form+':'+subject+':'+criterion['id']]=record
    if body['checked']:
        for eid in ids:
            old=data['evidence'].get(eid,{})
            data['evidence'][eid]={**old,'checked':True,'hold':bool(old.get('hold')),'by':name,'at':stamp}
    return {'criterion_check':record}
