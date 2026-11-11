"""Prepare one recent received reference per evidence kind, without certifying it."""
import hashlib,json,re
from . import monthly_sources,opinion_defaults

def select(available):
    selected={}
    for source in available.get('items',[]):
        category=source['category'];name=source['filename'];ids=[]
        if category=='opinions':ids=['worker_ledger']
        elif category=='safety-cost':ids=['budget']
        elif category=='theme':ids=['daily_inspection']
        elif category=='legal-training':
            # Filename clues select references only; category alone proves no training type.
            normalized=re.sub(r'\s+','',name).casefold()
            if '관리감독자'in normalized:ids=['supervisor_training']
            else:
                for words,evidence in [(('정기교육',),'education_regular'),(('특별교육',),'education_special'),(('msds','물질안전보건'),'msds'),(('채용시','신규채용','신규교육'),'education_hire'),(('tbm','작업전안전회의'),'tbm')]:
                    if any(word in normalized for word in words):ids.append(evidence)
        elif category=='risk':
            kind=source.get('document_facts',{}).get('assessment_kind')
            if kind=='INITIAL':ids=['risk_initial']
            elif kind in {'CONTINUOUS','OCCASIONAL'}:ids=['risk_ongoing']
            elif kind=='REGULAR':continue
            elif '상시'in name or '수시'in name:ids=['risk_ongoing']
            elif '최초'in name:ids=['risk_initial']
            else:continue
        if category=='risk'and ids:
            if '회의'in name:ids.append('risk_minutes')
            if '개선'in name or '조치'in name:ids.append('risk_actions')
        for evidence in ids:
            rank=(source.get('month',''),source.get('first_seen',''),source['id'])
            prior=selected.get(evidence)
            if prior is None or rank>(prior.get('month',''),prior.get('first_seen',''),prior['id']):selected[evidence]=source
    return selected

def for_plan(db,row,period):
    available=monthly_sources.sources(monthly_sources.monthly.load(),monthly_sources.site_for_plan(db,row),period)
    choices=select(available);sources=[]
    for evidence,source in sorted(choices.items()):
        # Reuse exactly the same server resolver and stable source contract as manual linking.
        stable={k:source[k]for k in ('id','category','month','team','filename','size','site_id','context_key','site_code','sha256','period','source_version')}
        for field in ('document_facts','initial_only','context_site_codes','site_name'):
            if field in source:stable[field]=source[field]
        resolved={'evidence_id':evidence,'source':stable}
        sources.append(resolved)
    opinion=opinion_defaults.for_plan(db,row,period)
    stable={'sources':sources,'opinion':opinion}
    fingerprint=hashlib.sha256(json.dumps(stable,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {**stable,'fingerprint':fingerprint}

def apply(data,key,period,body,actor,name,stamp):
    previous=data.get('prepared_defaults',{})
    if previous.get('fingerprint')==body['fingerprint']:return previous
    for item in body['sources']:
        evidence=item['evidence_id'];active=[r for r in data.get('monthly_sources',[])if r['active']and r['evidence_id']==evidence]
        if any(not r.get('prepared_default')for r in active):continue
        for row in active:
            if row['source_id']!=item['source']['id']:row.update(active=False,removed_at=stamp,removed_by=name)
        linked=monthly_sources.link(data,key,period,item,actor,name,stamp);linked['prepared_default']=True
    value={'fingerprint':body['fingerprint'],'opinion':body['opinion'],'at':stamp,'by':name,'sources':[{'evidence_id':item['evidence_id'],'filename':item['filename'],'month':item['month'],'source_id':item['source_id']}for item in data.get('monthly_sources',[])if item['active']]}
    data['prepared_defaults']=value
    return value
