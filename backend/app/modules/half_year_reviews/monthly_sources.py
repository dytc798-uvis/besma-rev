"""Existing monthly receipts as references, without copying or grading originals."""
import hashlib,json,re,uuid
from fastapi import HTTPException
from .catalog import EVIDENCE,Conflict,period_value
from app.modules.monthly_collection import routes as monthly
from app.modules.monthly_collection.source_quality import notes_by_id,document_facts_by_id

FIELDS=('id','category','month','team','site','filename','first_seen','last_seen','state','size')
def site_for_plan(db,row):
    from app.modules.inspection_reports.site_identity import resolve_sources
    contracts=resolve_sources(db,row)
    if not contracts or any(not site.site_code for site in contracts):return None
    site=contracts[0]
    match=re.fullmatch(r'inspection:\d{6}:site-(\d{1,6})(?::[A-Za-z0-9_-]+)?',row.client_item_key or'')
    context='site-'+match[1]if match else'plan-'+row.public_id
    scope={'id':int(match[1])if match else None,'context_id':context,'code':site.site_code,'name':site.site_name,'registry_confirmed':all(s.id is not None for s in contracts)}
    if len(contracts)>1:
        scope.update(code=None,name=row.title.removeprefix('[점검] ').strip(),contracts=[{'code':s.site_code,'name':s.site_name,'registry_confirmed':s.id is not None}for s in contracts])
    return scope

def reference_sources(snapshot,site,period,quality):
    """Reviewed shared scope is for reading, never a classified/gradable source."""
    if 'reviewed_source_references'not in snapshot:return {}
    references=monthly.reviewed_references(snapshot)
    codes={c['code']for c in site.get('contracts',[{'code':site['code']}])};index={r['id']:r for r in snapshot['items']};found=[];pending=0
    lo=period[:4]+('-01'if period.endswith('H1')else'-07');hi=period[:4]+('-06'if period.endswith('H1')else'-12')
    for reference in references:
        contracts=reference['contracts'];scope=[c['code']for c in contracts]
        if not codes.intersection(scope):continue
        row=index.get(reference['id'])
        if row is None:pending+=1;continue
        if not isinstance(row.get('month'),str)or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',row['month']):raise HTTPException(503,'공동 참고자료의 자료월을 확인해야 합니다.')
        if not lo<=row.get('month','')<=hi:continue
        if row.get('sha256')!=reference['sha256']or row.get('site_code')or row.get('state')!='SITE_REVIEW':pending+=1;continue
        if row.get('category')not in monthly.LABELS or type(row.get('size'))is not int or row['size']<1 or not isinstance(row.get('filename'),str)or not 1<=len(row['filename'])<=260 or re.search(r'[\\/\x00-\x1f\x7f]',row['filename']):raise HTTPException(503,'공동 참고자료의 원본 정보를 확인해야 합니다.')
        source={k:row[k]for k in FIELDS};source.update(site_id=site['id'],context_key=site.get('context_id','site-'+str(site['id']))+'|'+period,site_code='',sha256=row['sha256'],period=period,reference_only=True,reference_contracts=contracts,reference_context_site_codes=sorted(codes),site_name=' / '.join(c['name']for c in contracts),quality_notes=quality.get(row['id'],[]));source.update(monthly.storage_fields(row))
        identity={k:source[k]for k in ('id','category','month','team','sha256','size','filename','site_id','context_key','period','reference_only','reference_contracts','reference_context_site_codes')};source['source_version']=hashlib.sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();found.append(source)
    if not found and not pending:return {}
    found.sort(key=lambda r:(r['month'],r['filename'],r['id']),reverse=True)
    return {'reference_items':found,'reference_count':len(found)if found else None,'reference_pending_count':pending,'reference_state':'AVAILABLE'if found else'CHECK_REQUIRED'}

def sources(snapshot,site,period):
    period_value(period)
    if site is None:return {'state':'SITE_UNCONFIRMED','items':[],'count':None,'unverified_count':None}
    if not snapshot.get('generated_at')or snapshot.get('collection_state')=='NOT_RECEIVED':return {'state':'NOT_RECEIVED','items':[],'count':None,'unverified_count':None}
    lo=period[:4]+('-01'if period.endswith('H1')else'-07');hi=period[:4]+('-06'if period.endswith('H1')else'-12')
    contracts=site.get('contracts',[{'code':site['code'],'name':site['name']}]);codes=sorted(c['code']for c in contracts);by_code={c['code']:c for c in contracts}
    if not 1<=len(codes)<=8 or len(set(codes))!=len(codes)or any(not isinstance(c,str)or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',c)for c in codes):raise HTTPException(503,'점검계획의 계약 연결을 확인해야 합니다.')
    found=[];seen=set();unverified=0;unassigned=0;quality=notes_by_id(snapshot);facts=document_facts_by_id(snapshot)
    for row in snapshot['items']:
        if lo<=row.get('month','')<=hi and not row.get('site_code'):unassigned+=1
        fact=facts.get(row.get('id'));after_period=fact if fact and fact['document_date']>hi+'-31'else None
        if after_period:fact=None
        prior_initial=bool(fact and fact['assessment_kind']=='INITIAL'and row.get('month','')<lo)
        if row.get('site_code')not in by_code or not(lo<=row.get('month','')<=hi or prior_initial):continue
        if row.get('state')!='SAVED':unverified+=1;continue
        if not re.fullmatch(r'[a-f0-9]{64}',row.get('id',''))or row['id']in seen or row.get('category')not in monthly.LABELS or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',row.get('month',''))or not re.fullmatch(r'[a-f0-9]{64}',row.get('sha256',''))or type(row.get('size'))is not int or row['size']<=0:raise HTTPException(503,'취합자료 수신기록을 확인해야 합니다.')
        seen.add(row['id']);name=row.get('filename','')
        if not isinstance(name,str)or not 1<=len(name)<=260 or re.search(r'[\\/\x00-\x1f\x7f]',name):raise HTTPException(503,'취합자료 파일명을 확인해야 합니다.')
        source={k:row[k]for k in FIELDS};source.update(site_id=site['id'],context_key=site.get('context_id','site-'+str(site['id']))+'|'+period,site_code=row['site_code'],sha256=row['sha256'],period=period)
        identity={k:source[k]for k in ('id','category','month','team','site_code','sha256','size','filename','site_id','context_key','period')}
        if fact:source['document_facts']=dict(fact);identity['document_facts']=dict(fact)
        if prior_initial:source['initial_only']=True;identity['initial_only']=True
        if len(contracts)>1:
            source.update(context_site_codes=codes,site_name=by_code[row['site_code']]['name']);identity.update(context_site_codes=codes,site_name=source['site_name'])
        canonical=json.dumps(identity,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
        source['source_version']=hashlib.sha256(canonical).hexdigest();source.update(monthly.storage_fields(row));source['quality_notes']=list(quality.get(row['id'],[]))
        if after_period:source['quality_notes'].append('원문 작성일 '+after_period['document_date'].replace('-','.')+'은 평가기간 이후입니다. 적용 여부를 확인해 주세요.')
        found.append(source)
    found.sort(key=lambda r:(r['month'],r['filename'],r['id']),reverse=True)
    quality_count=sum(bool(row['quality_notes'])for row in found)
    incomplete=bool(unverified or unassigned or quality_count)
    result={'state':'SOURCE_REVIEW_REQUIRED'if not found and incomplete else'AVAILABLE','items':found,'count':None if not found and incomplete else len(found),'unverified_count':unverified,'unassigned_count':unassigned,'scope_complete':not incomplete,'quality_review_count':quality_count,'generated_at':snapshot['generated_at'],'site_name':site['name'],'period':period,'site_registry_confirmed':site.get('registry_confirmed',True)}
    result.update(reference_sources(snapshot,site,period,quality))
    if len(contracts)>1:result.update(contracts=contracts,publication_site_confirmed=False)
    return result

def resolve(db,row,period,body):
    if set(body)!={'evidence_id','source_id','source_version'}or body['evidence_id']not in EVIDENCE:raise ValueError('MONTHLY_SOURCE_INVALID')
    site=site_for_plan(db,row);available=sources(monthly.load(),site,period)
    source=next((r for r in available['items']if r['id']==body['source_id']),None)
    if source is None or source['source_version']!=body['source_version']:raise Conflict('MONTHLY_SOURCE_CHANGED')
    stable={k:source[k]for k in ('id','category','month','team','filename','size','site_id','context_key','site_code','sha256','period','source_version')}
    if source.get('initial_only')and body['evidence_id']!='risk_initial':raise ValueError('INITIAL_SOURCE_ONLY')
    for key in ('document_facts','initial_only'):
        if key in source:stable[key]=source[key]
    if 'context_site_codes'in source:stable.update(context_site_codes=source['context_site_codes'],site_name=source['site_name'])
    return {'evidence_id':body['evidence_id'],'source':stable}

def resolve_many(db,row,period,body):
    if set(body)!={'evidence_id','sources'}or body['evidence_id']not in EVIDENCE or not isinstance(body['sources'],list)or not 1<=len(body['sources'])<=20:raise ValueError('MONTHLY_SOURCE_INVALID')
    site=site_for_plan(db,row);available=sources(monthly.load(),site,period)
    index={r['id']:r for r in available['items']};seen=set();selected=[]
    for entry in body['sources']:
        if not isinstance(entry,dict)or set(entry)!={'source_id','source_version'}or not isinstance(entry['source_id'],str)or not isinstance(entry['source_version'],str)or entry['source_id']in seen:raise ValueError('MONTHLY_SOURCE_INVALID')
        source=index.get(entry['source_id'])
        if source is None or source['source_version']!=entry['source_version']:raise Conflict('MONTHLY_SOURCE_CHANGED')
        seen.add(entry['source_id']);stable={k:source[k]for k in ('id','category','month','team','filename','size','site_id','context_key','site_code','sha256','period','source_version')}
        if source.get('initial_only')and body['evidence_id']!='risk_initial':raise ValueError('INITIAL_SOURCE_ONLY')
        for key in ('document_facts','initial_only'):
            if key in source:stable[key]=source[key]
        if 'context_site_codes'in source:stable.update(context_site_codes=source['context_site_codes'],site_name=source['site_name'])
        selected.append(stable)
    return {'evidence_id':body['evidence_id'],'sources':selected}

def link_many(data,key,period,body,actor,name,stamp):
    if set(body)!={'evidence_id','sources'}or body['evidence_id']not in EVIDENCE or not isinstance(body['sources'],list)or not 1<=len(body['sources'])<=20:raise ValueError('MONTHLY_SOURCE_INVALID')
    ids=[s.get('id')if isinstance(s,dict)else None for s in body['sources']]
    if any(not isinstance(s,str)for s in ids)or len(set(ids))!=len(ids):raise ValueError('MONTHLY_SOURCE_INVALID')
    return [link(data,key,period,{'evidence_id':body['evidence_id'],'source':s},actor,name,stamp)for s in body['sources']]

def link(data,key,period,body,actor,name,stamp):
    if set(body)!={'evidence_id','source'}or body['evidence_id']not in EVIDENCE:raise ValueError('MONTHLY_SOURCE_INVALID')
    s=body['source']
    if not isinstance(s,dict)or s.get('period')!=period or key!=s.get('context_key')or not re.fullmatch(r'[a-f0-9]{64}',s.get('source_version',''))or not re.fullmatch(r'[a-f0-9]{64}',s.get('id',''))or not re.fullmatch(r'[a-f0-9]{64}',s.get('sha256','')):raise ValueError('MONTHLY_SOURCE_INVALID')
    if s.get('initial_only')and body['evidence_id']!='risk_initial':raise ValueError('INITIAL_SOURCE_ONLY')
    rows=data.setdefault('monthly_sources',[])
    codes=s.get('context_site_codes',[s['site_code']])
    if not isinstance(codes,list)or not 1<=len(codes)<=8 or codes!=sorted(set(codes))or any(not isinstance(code,str)or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',code)for code in codes)or s['site_code']not in codes:raise ValueError('MONTHLY_SOURCE_INVALID')
    if any(r['site_code']not in codes for r in rows):raise Conflict('MONTHLY_CONTEXT_SITE_CHANGED')
    same=next((r for r in rows if r['active']and r['evidence_id']==body['evidence_id']and r['source_id']==s['id']and r['source_version']==s['source_version']),None)
    if same:return same
    if len(rows)>=500:raise ValueError('MONTHLY_SOURCE_LIMIT')
    for row in rows:
        if row['active']and row['evidence_id']==body['evidence_id']and row['source_id']==s['id']:row.update(active=False,removed_by=name,removed_at=stamp)
    row={'id':uuid.uuid4().hex,'evidence_id':body['evidence_id'],'source_id':s['id'],'source_version':s['source_version'],'filename':s['filename'],'month':s['month'],'category':s['category'],'team':s['team'],'sha256':s['sha256'],'bytes':s['size'],'site_code':s['site_code'],'by':name,'actor_id':actor,'at':stamp,'active':True}
    if 'context_site_codes'in s:row.update(context_site_codes=list(codes),site_name=s['site_name'])
    if 'document_facts'in s:row['document_facts']=dict(s['document_facts'])
    if s.get('initial_only'):row['initial_only']=True
    rows.append(row);return row

def unlink(data,body,name,stamp):
    if set(body)!={'id'}:raise ValueError('MONTHLY_SOURCE_INVALID')
    row=next((r for r in data.get('monthly_sources',[])if r['id']==body['id']),None)
    if row is None:raise KeyError('MONTHLY_SOURCE_MISSING')
    row.update(active=False,removed_by=name,removed_at=stamp);return row
