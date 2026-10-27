"""HQ home: current ERP attendance, shared site-directory locations and H2 readiness. Read-only."""
import hashlib,json,re,math,time,datetime as dt
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from sqlalchemy import text,bindparam
from app.config.settings import settings
from app.core.datetime_utils import kst_today
from app.modules.home_fields import home_site_fields,home_site_scope,bound_location_region
from app.modules.workspace_manager_photos import manager_registry,verified_manager_photo
from app.modules.workspace_site_scope import annual_unit_contract

ROOT=Path(settings.storage_root)/'headquarters-workspace'
REGIONS=('서울','경기','인천','강원권','충청권','호남권','영남권','제주권','주소 확인 중')
def region(address):
    value=re.sub(r'\s+','',address or '')
    for prefixes,label in ((('서울',),'서울'),(('인천',),'인천'),(('경기','오산시','용인시','평택시'),'경기'),(('강원','철원','춘천'),'강원권'),(('충북','충남','충청','대전','세종'),'충청권'),(('전북','전남','전라','광주'),'호남권'),(('경북','경남','경상','부산','대구','울산'),'영남권'),(('제주',),'제주권')):
        if value.startswith(prefixes):return label
    return '주소 확인 중'

def map_exclusion(name):
    value=re.sub(r'\s+','',name or '')
    if re.search(r'(?<![배간전])선공사',value):return '선공사'
    return next((kind for kind in ('임시동력','임시전력','임시가설','가설공사','가설전기') if kind in value),None)

def photo_records():
    path=ROOT/'site-photos.json'
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        return value['photos'] if isinstance(value,dict) and value.get('schema')==1 and isinstance(value.get('photos'),dict) else {}
    except (OSError,ValueError,TypeError):return {}

def verified_photo(code,photos):
    value=photos.get(code)
    if not isinstance(value,dict) or value.get('site_code')!=code or value.get('verified') is not True:return None
    def valid_url(raw,local=False):
        if not isinstance(raw,str) or not raw or len(raw)>2000 or any(ord(c)<32 for c in raw) or '\\' in raw:return False
        try:uri=urlsplit(raw)
        except ValueError:return False
        if local and raw.startswith('/workspace-assets/') and not uri.netloc and '..' not in uri.path.split('/'):return True
        scheme_ok=uri.scheme=='https' or (not local and uri.scheme=='http' and uri.hostname in {'boohyun.kr','www.boohyun.kr'})
        return scheme_ok and bool(uri.hostname) and not uri.username and not uri.password
    if not valid_url(value.get('url'),True) or not valid_url(value.get('source_url')):return None
    output={'site_code':code,'url':value['url'],'thumbnail_url':value.get('thumbnail_url') if valid_url(value.get('thumbnail_url'),True) else value['url'],'source_url':value['source_url'],'caption':str(value.get('caption') or '')[:200],'verified':True}
    alternative=value.get('rendering')
    if isinstance(alternative,dict) and alternative.get('verified') is True and alternative.get('site_code')==code and valid_url(alternative.get('url'),True) and valid_url(alternative.get('source_url')):
        output['rendering']={k:alternative[k] for k in ['site_code','url','source_url','caption','verified']}
    return output

def seoul_weather():
    from app.modules.seoul_forecast import seoul_forecast
    return seoul_forecast(Path(settings.storage_root)/'weather_snapshots'/'seoul_forecast'/'met.json')


def daily():
    path=ROOT/'daily-attendance/latest.json'
    if not path.is_file():return None
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        assert data['schema']==1 and re.fullmatch(r'\d{4}-\d{2}-\d{2}',data['date'])
        assert isinstance(data['people'],int) and data['people']>=0 and sum(s['people'] for s in data['sites'])==data['people']
        return data
    except (ValueError,KeyError,TypeError,AssertionError):return None

def location_records():
    path=ROOT/'site-locations.json'
    return json.loads(path.read_text(encoding='utf-8')).get('locations',{}) if path.is_file() else {}

def active_sites(db,attendance,user=None):
    from app.modules.site_directory import catalog
    from app.modules.documents.active_site_scope import active_site_codes
    from app.modules.document_explorer.government_access import is_government_site_record
    data,items=catalog(db);aliases=data.get('aliases',{})
    active={aliases.get(c,c) for c in active_site_codes()}
    rows={str(r['site_code']):dict(r) for r in db.execute(text('SELECT id,site_code,site_name,contract_type,status,end_date FROM sites')).mappings()}
    for alias,code in aliases.items():
        if code not in rows and alias in rows:rows[code]=rows[alias]
    today=str(kst_today());current=attendance if attendance and attendance['date']==today else None
    counts={s['code']:s['people'] for s in current['sites'] if s.get('code')} if current else {}
    loc=location_records();photos=photo_records();managers=manager_registry(ROOT);result=[]
    for site in items:
        if annual_unit_contract(site):continue
        code=site['code'];row=rows.get(code,{})
        current_active=(code in active or str(row.get('status') or '').upper()=='ACTIVE') and not(row.get('end_date') and str(row['end_date'])<today) and '준공' not in site['name'] and str(row.get('status') or '').upper() not in {'COMPLETED','CLOSED','INACTIVE'}
        if not(current_active or counts.get(code,0)>0):continue
        if not site['name'] or re.fullmatch(r'[\d\s.,_-]+',site['name']):continue
        address=site.get('address') or '';point=loc.get(code,{})
        lat,lon=site.get('latitude'),site.get('longitude');precision='registered' if lat is not None and lon is not None else 'unresolved'
        if precision=='unresolved' and point.get('address_sha256')==hashlib.sha256(address.encode()).hexdigest():lat,lon,precision=point.get('latitude'),point.get('longitude'),point.get('precision','unresolved')
        if lat is None or lon is None or not(33<=float(lat)<=39 and 124<=float(lon)<=132):lat,lon,precision=None,None,'unresolved'
        classification=is_government_site_record(SimpleNamespace(**{**row,'site_code':code})) if row else None
        site_region=region(address)
        if site_region=='주소 확인 중':site_region=bound_location_region(address,point,lat,lon) or site_region
        portrait=verified_manager_photo(site,ROOT,managers) if getattr(getattr(user,'role',None),'value',getattr(user,'role',None))=='HQ_SAFE' else None
        result.append({'code':code,'name':site['name'],'address':address,'region':site_region,'latitude':lat,'longitude':lon,'location_precision':precision,'manager_photo':portrait['metadata'] if portrait else None,'today_people':counts.get(code) if current else None,
                       'is_government':classification,'photo':verified_photo(code,photos),'map_visible':map_exclusion(site['name']) is None,'map_exclusion_reason':map_exclusion(site['name']),**home_site_fields(site,user)})
    return result

def readiness(db,attendance=None):
    attendance=attendance if attendance is not None else daily();today=str(kst_today())
    base={'target_start':'2026-11-02','deadline':'2026-11-20','state':'PREPARING','can_evaluate':False,'source_date':attendance['date'] if attendance else None,'source_current':bool(attendance and attendance['date']==today),'today_people':attendance['people'] if attendance and attendance['date']==today else None}
    periods=[dict(r) for r in db.execute(text('SELECT id,title,deadline_date,is_active FROM functional_eval_periods ORDER BY id DESC')).mappings()]
    base['previous_periods']=periods
    if not base['source_current']:
        return {**base,'sites':[],'blockers':['오늘 ERP 출역자료 수집이 필요합니다.','11월 2일 시작 가능·11월 20일 마감으로 하반기 평가를 준비합니다.']}
    hashes=[x['rrn_hash'] for x in attendance.get('identities',[]) if x.get('rrn_hash')]
    known=set();prior=set();functional=set();safety=set()
    # Bind the hashes; never log identities or mix old assessment rows with current criteria.
    for offset in range(0,len(hashes),400):
        part=hashes[offset:offset+400]
        q=text('''SELECT w.rrn_hash,a.eval_type,a.grade_code FROM functional_eval_workers w JOIN functional_eval_periods p ON p.id=w.period_id LEFT JOIN functional_eval_assessments a ON a.worker_id=w.id WHERE w.rrn_hash IN :hashes AND p.deadline_date < :today''').bindparams(bindparam('hashes',expanding=True))
        for row in db.execute(q,{'hashes':part,'today':today}).mappings():
            known.add(row['rrn_hash'])
            if row['grade_code']:
                prior.add(row['rrn_hash']);(functional if row['eval_type']=='FUNCTIONAL' else safety).add(row['rrn_hash'])
    registry={str(r['site_code']):dict(r) for r in db.execute(text('SELECT site_code,manager_login_id FROM functional_eval_site_registry')).mappings()}
    active_evaluators={r['login_id'] for r in db.execute(text("SELECT login_id FROM users WHERE is_active=1 AND role='SITE_FUNCTIONAL_EVAL'")).mappings()}
    site_people={}
    for person in attendance.get('identities',[]):
        code=person.get('site_code');count=site_people.setdefault(code,{'prior':0,'new':0})
        count['prior' if person.get('rrn_hash') in prior else 'new']+=1
    sites=[]
    for site in attendance['sites']:
        code=site.get('code');reg=registry.get(code,{})
        sites.append({'code':code,'name':site['name'],'people':site['people'],'prior_grade_people':site_people.get(code,{}).get('prior',0),'new_or_ungraded_people':site_people.get(code,{}).get('new',0),'evaluator_registered':bool(reg.get('manager_login_id') in active_evaluators)})
    missing=sum(not s['evaluator_registered'] for s in sites)
    blockers=['11월 2일 시작 가능·11월 20일 마감의 하반기 평가기간을 별도로 등록해야 합니다.','시작일의 실제 출역명부로 하반기 평가대상을 등록해야 합니다.']
    if missing:blockers.append(f'{missing}개 현장의 소장·평가자 배정을 확인해야 합니다.')
    return {**base,'source_sha256':attendance['source_sha256'],'captured_at':attendance['captured_at'],'sites':sites,'site_count':len(sites),'prior_roster_people':len(known),'prior_grade_people':len(prior),'prior_functional_people':len(functional),'prior_safety_people':len(safety),'new_or_ungraded_people':attendance['people']-len(prior),'evaluator_check_sites':missing,'blockers':blockers}

def home(db,user=None):
    data=daily();today=str(kst_today());current=bool(data and data['date']==today);sites=active_sites(db,data,user)
    notices=[dict(r) for r in db.execute(text('SELECT id,title,created_at FROM notices ORDER BY created_at DESC,id DESC LIMIT 3')).mappings()]
    return {**home_site_scope(sites),'date':today,'attendance':{'current':current,'people':data['people'] if current else None,'source_date':data['date'] if data else None,'captured_at':data['captured_at'] if data else None,'last_people':data['people'] if data else None,'site_count':len(data['sites']) if current else None},'sites':sites,'regions':[{'name':name,'count':sum(s['region']==name for s in sites)} for name in REGIONS],'notices':notices,'location_source':'ERP 주소 · 현장검색 공통','map_attribution':'Natural Earth · © OpenStreetMap contributors'}

def weather(db,code):
    from fastapi import HTTPException
    from app.modules.dashboard.weather_service import build_weather_snapshot,WeatherLocation
    site=next((s for s in active_sites(db,daily()) if s['code']==code),None)
    if not site:raise HTTPException(404,'ACTIVE_SITE_REQUIRED')
    if site['latitude'] is None:return {'available':False,'site_code':code,'reason':'현장 주소의 위치를 확인하고 있습니다.'}
    value=build_weather_snapshot(WeatherLocation(name=site['name'],latitude=float(site['latitude']),longitude=float(site['longitude']),address=site['address'],site_code=code))
    observed=value.get('observed_at') or value.get('updated_at')
    if hasattr(observed,'isoformat'):observed=observed.isoformat()
    return {'site_code':code,'available':bool(value.get('available')),'temperature':value.get('temperature'),'humidity':value.get('humidity'),'wind_speed':value.get('wind_speed'),'weather_label':value.get('weather_label'),'observed_at':observed,'source':value.get('temperature_source'),'status_text':value.get('status_text'),'advisory_flags':value.get('advisory_flags',[])}
