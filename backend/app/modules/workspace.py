"""Authenticated headquarters workspace. Existing operational records remain authoritative."""
import hashlib,json,re
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import JSONResponse,FileResponse,Response
from pydantic import BaseModel,ConfigDict,StrictBool
from sqlalchemy import text
from app.core.auth import DbDep,get_current_user
from app.config.settings import settings

router=APIRouter(prefix='/workspace',tags=['headquarters-workspace'])
DATA=Path(settings.storage_root)/'headquarters-workspace'/'workspace-data.json'
HQ_ROLES={'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','HQ_OTHER','FUNCTIONAL_EVAL_VIEWER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE'}
SAFETY_TEAMS={'김지모':{4,5},'문상희':{1,6},'조영흠':{2,3}}

def authorized(user=Depends(get_current_user)):
 role=getattr(user.role,'value',user.role)
 if not user.is_active or role not in HQ_ROLES or getattr(user,'ui_type','') not in {'HQ_SAFE','HQ_OTHER'}:
  raise HTTPException(403,'본사 로그인 후 이용할 수 있습니다.')
 return user

def result(data):return JSONResponse(data,headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})
@lru_cache(maxsize=2)
def _read(path,stamp):return json.loads(Path(path).read_text(encoding='utf-8'))
def dataset():
 if not DATA.is_file():raise HTTPException(503,'업무자료를 준비하고 있습니다.')
 return _read(str(DATA),DATA.stat().st_mtime_ns)

def migrate(conn):
 from app.modules.workspace_site_notes import migrate as migrate_notes
 migrate_notes(conn)
 conn.execute(text('CREATE TABLE IF NOT EXISTS workspace_site_preferences (user_id INTEGER NOT NULL REFERENCES users(id),site_code TEXT NOT NULL,is_favorite INTEGER NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,site_code))'))

@router.get('/bootstrap')
def bootstrap(db:DbDep,user=Depends(get_current_user)):
 if getattr(user.role,'value',user.role)=='SITE':
  from app.modules.workspace_site import bootstrap as site_bootstrap
  return site_bootstrap(db,user)
 authorized(user)
 data=dataset()
 from app.core.government_workspace_access import can_manage_government
 role=getattr(user.role,'value',user.role);safe_ui=getattr(user,'ui_type','')=='HQ_SAFE'
 return result({'permissions':{'manage_government_forms':can_manage_government(user),'worker_voice_read':safe_ui and role in {'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','FUNCTIONAL_EVAL_VIEWER'},'worker_voice_ledger':safe_ui and role in {'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN'}},'version':'2026.10.27.11','user':{'name':user.name,'role':getattr(user.role,'value',user.role)},'sources':data['sources'],
  'menus':[{'id':1,'title':'기능인인정제'},{'id':2,'title':'업무분장'},{'id':3,'title':'위험성평가 DB'},{'id':4,'title':'양식·법령 탐색'},
   {'id':5,'title':'현장 정보 검색'},{'id':6,'title':'고객사 안전기준'},{'id':7,'title':'관급공사 현장 소통'},{'id':8,'title':'사용설명서'},{'id':9,'title':'근로자의견청취'}]})

@router.get('/duties')
def duties(user=Depends(authorized)):return result({'items':dataset()['duties'],'source':dataset()['sources']['duties'],'site_assignments':[{'name':name,'teams':sorted(teams)} for name,teams in SAFETY_TEAMS.items()]})

@router.get('/functional-overview')
def functional_overview(db:DbDep,user=Depends(authorized)):
 period=db.execute(text('SELECT id,title,deadline_date FROM functional_eval_periods WHERE is_active=1 ORDER BY id DESC LIMIT 1')).mappings().first()
 if not period:return result({'period':None,'grades':[]})
 rows=db.execute(text('SELECT a.eval_type,a.grade_code,COUNT(*) AS count FROM functional_eval_assessments a JOIN functional_eval_workers w ON w.id=a.worker_id WHERE w.period_id=:pid GROUP BY a.eval_type,a.grade_code'),{'pid':period['id']}).mappings().all()
 return result({'period':dict(period),'grades':[dict(r) for r in rows]})

@router.get('/risks')
def risks(q:str=Query('',max_length=120),work:str=Query('',max_length=100),case:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(40,ge=1,le=100),user=Depends(authorized)):
 data=dataset();words=q.lower().split();rows=data['risks']
 rows=[r for r in rows if (not work or r['work']==work) and (case is None or case in r['cases']) and all(w in (r['work']+' '+r['process']+' '+r['risk']+' '+r['measure']).lower() for w in words)]
 used={n for r in rows[offset:offset+limit] for n in r['cases']}
 return result({'items':rows[offset:offset+limit],'total':len(rows),'works':sorted({r['work'] for r in data['risks']}),
  'cases':[c for c in data['cases'] if c['number'] in used],'source':data['sources']['risk'],'case_basis':data['sources']['accident_basis']})

@router.get('/cases')
def cases(q:str=Query('',max_length=120),user=Depends(authorized)):
 words=q.lower().split();rows=dataset()['cases']
 return result({'items':[r for r in rows if all(w in (r['work']+' '+r['description']+' '+r['prevention']).lower() for w in words)],'basis':dataset()['sources']['accident_basis']})

@router.get('/forms')
def forms(q:str=Query('',max_length=120),user=Depends(authorized)):
 from app.modules.document_explorer.routes import _scan_document_file_entries
 words=q.lower().split();items=[]
 for item,_ in _scan_document_file_entries():
  if item.category=='field':continue
  if all(w in (item.name+' '+item.relative_path).lower() for w in words):
   items.append({'name':item.name,'category':item.category,'path':item.relative_path,'modified_at':str(item.modified_at)})
 return result({'items':items,'source':'BESMA 등록 양식·법령','drive_latest_verified':False})

@router.get('/government-sites')
def government_sites(db:DbDep,user=Depends(authorized)):
 from app.modules.workspace_site_scope import annual_unit_contract
 from app.modules.sites.models import Site
 from app.modules.document_explorer.government_access import is_government_site_record
 from app.modules.documents.active_site_scope import in_active_scope,today_kst
 sites=[{'code':s.site_code,'name':s.site_name} for s in db.query(Site).all() if is_government_site_record(s) and in_active_scope(s,today_kst(),'government') and not annual_unit_contract({'site_name':s.site_name,'contract_type':s.contract_type})]
 return result({'items':sites})

_POLICY_PREVIEW_PAGES={13: 2, 15: 151, 21: 11, 32: 5, 33: 1, 34: 4, 35: 7, 36: 2, 38: 2, 39: 2, 40: 2, 50: 2, 55: 151}

def _policy_item_sha(item):
 return hashlib.sha256(json.dumps(item,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()

def _policy_previews(data,only_id=None,keep_page=None,fingerprints=None):
 # A private derived catalog never changes the canonical workspace dataset.
 try:
  catalog=json.loads((DATA.parent/'policy-preview-catalog.json').read_text(encoding='utf-8'))
  entries=catalog['items']
  if type(catalog.get('version')) is not int or catalog['version']!=1 or not isinstance(entries,list) or len(entries)!=len(_POLICY_PREVIEW_PAGES):return {}
  ids=[entry['id'] for entry in entries]
  if any(type(ident) is not int for ident in ids) or set(ids)!=set(_POLICY_PREVIEW_PAGES):return {}
  # Fresh row bytes also reject stale overlays if a replacement retained its mtime.
  current=json.loads(DATA.read_text(encoding='utf-8'))['policies']
 except (OSError,UnicodeError,ValueError,KeyError,TypeError):return {}
 verified={}
 for entry in entries:
  ident=entry['id']
  if only_id is not None and ident!=only_id:continue
  try:
   rows=[row for row in data['policies'] if row.get('id')==ident]
   fresh=[row for row in current if row.get('id')==ident]
   if len(rows)!=1 or len(fresh)!=1 or type(rows[0].get('pages')) is not int or rows[0]['pages']!=0:continue
   if _policy_item_sha(rows[0])!=entry['item_sha256'] or _policy_item_sha(fresh[0])!=entry['item_sha256']:continue
   pages=entry['pages']
   if not isinstance(pages,list) or len(pages)!=_POLICY_PREVIEW_PAGES[ident]:continue
   payloads=[];digests=[]
   for number,descriptor in enumerate(pages,1):
    size=descriptor['size'];digest=descriptor['sha256']
    if type(descriptor['page']) is not int or descriptor['page']!=number or type(size) is not int or not 5<=size<=8*1024*1024 or not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError()
    file=DATA.parent/'policy-previews'/f'{ident}-{number}.jpg'
    if file.is_symlink() or not file.is_file() or file.stat().st_size!=size:raise ValueError()
    with file.open('rb') as stream:payload=stream.read(size+1)
    if len(payload)!=size or not payload.startswith(b'\xff\xd8\xff') or not payload.endswith(b'\xff\xd9') or hashlib.sha256(payload).hexdigest()!=digest:raise ValueError()
    payloads.append(payload if keep_page is None or keep_page==number else None);digests.append(digest)
   verified[ident]=payloads
   if fingerprints is not None:fingerprints[ident]=tuple(digests)
  except (OSError,UnicodeError,ValueError,KeyError,TypeError,AttributeError):continue
 return verified

def _policy_legacy_fingerprint(item):
 try:
  ident=item['id'];pages=item['pages']
  if type(ident) is not int or type(pages) is not int or not 1<=pages<=151:return None
  values=[]
  for number in range(1,pages+1):
   file=DATA.parent/'policy-previews'/f'{ident}-{number}.jpg'
   if file.is_symlink() or not file.is_file():return None
   with file.open('rb') as stream:payload=stream.read(8*1024*1024+1)
   if len(payload)>8*1024*1024 or not payload.startswith(b'\xff\xd8\xff') or not payload.endswith(b'\xff\xd9'):return None
   values.append(hashlib.sha256(payload).hexdigest())
  return tuple(values)
 except (OSError,KeyError,TypeError,ValueError):return None


@router.get('/contractors')
def contractors(user=Depends(authorized)):
 return result(contractor_catalog())

def contractor_catalog():
 data=dataset();fingerprints={};previews=_policy_previews(data,keep_page=0,fingerprints=fingerprints);items=[dict(item) for item in data['policies']]
 for item in items:
  if item['id'] in previews:
   item['pages']=len(previews[item['id']])
   if item['id'] in {15,55} and item.get('contractor')=='기타' and str(item.get('folder','')).replace(chr(92),'/').rstrip('/').split('/')[-1]=='현대산업개발':
    item['source_contractor']=item['contractor'];item['contractor']='현대산업개발'
 by_id={item['id']:item for item in items}
 # Source pairs were byte-identical; require the same current full preview sequence too.
 for alias,primary in {24:5,42:6,43:7,44:8,45:9,47:10,48:11,49:12,50:13,51:14,55:15}.items():
  if alias not in by_id or primary not in by_id:continue
  if any(by_id[alias].get(key)!=by_id[primary].get(key) for key in ('contractor','source_file')):continue
  for ident in (alias,primary):
   if ident not in fingerprints and ident not in _POLICY_PREVIEW_PAGES:
    value=_policy_legacy_fingerprint(by_id[ident])
    if value:fingerprints[ident]=value
  if alias in fingerprints and primary in fingerprints and fingerprints[alias]==fingerprints[primary]:
   by_id[alias]['duplicate_of']=primary;by_id[primary].setdefault('duplicate_ids',[]).append(alias)
 return {'items':items,'posco_criteria':data['posco_criteria']}

@router.get('/contractors/{item_id}/pages/{page}')
def contractor_page(item_id:int,page:int,user=Depends(authorized)):
 data=dataset();item=next((p for p in data['policies'] if p['id']==item_id),None)
 if not item or page<1:raise HTTPException(404,'자료를 찾지 못했습니다.')
 if item_id in _POLICY_PREVIEW_PAGES and item.get('pages')==0:
  payloads=_policy_previews(data,item_id,keep_page=page).get(item_id,[])
  if page>len(payloads):raise HTTPException(404,'미리보기를 준비하고 있습니다.')
  return Response(payloads[page-1],media_type='image/jpeg',headers={'Cache-Control':'private, no-store','Vary':'Authorization'})
 if page>item.get('pages',0):raise HTTPException(404,'자료를 찾지 못했습니다.')
 file=DATA.parent/'policy-previews'/f'{item_id}-{page}.jpg'
 if not file.is_file():raise HTTPException(404,'미리보기를 준비하고 있습니다.')
 return FileResponse(file,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','Vary':'Authorization'})

@router.get('/contractors/{item_id}/pages/{page}/guide')
def contractor_page_guide(item_id:int,page:int,user=Depends(authorized)):
 from app.modules.policy_guides import page_guide
 if item_id<1 or page<1:raise HTTPException(404,'자료를 찾지 못했습니다.')
 return result(page_guide(DATA,dataset(),item_id,page))


def site_data(db,user):
 from app.modules.site_directory import catalog,favorites
 from app.modules.workspace_site_scope import annual_unit_contract
 _,sites=catalog(db)
 sites=[s for s in sites if not annual_unit_contract(s)]
 role=getattr(user.role,'value',user.role)
 safety=role in {'HQ_SAFE','HQ_SAFE_ADMIN'} or (role=='ACCIDENT_ADMIN' and getattr(user,'login_id','') in {'sijung','안전보건-정상익','hq01'})
 from app.modules.workspace_favorites import default_favorite_codes
 defaults=default_favorite_codes(DATA.parent/'workspace-default-favorites.json',user.name,{s['code'] for s in sites}) if safety else set()
 saved=set(favorites(db,user.id));prefs=dict(db.execute(text('SELECT site_code,is_favorite FROM workspace_site_preferences WHERE user_id=:uid'),{'uid':user.id}).all())
 stars=(defaults|saved|{k for k,v in prefs.items() if v})-{k for k,v in prefs.items() if not v}
 out=[]
 for site in sites:
  contractor=next((d['value'] for d in site['details'] if d['key']=='contractor'),'')
  out.append({'code':site['code'],'name':site['name'],'address':site['address'],'latitude':site['latitude'],'longitude':site['longitude'],
   'contacts':[{k:c.get(k,'') for k in ['name','role','rank','label','phone','contact_id','rank_revision','rank_confirmed']} for c in site['contacts']],
   'info_revision':site['info_revision'],'description':site.get('description',''),'edit_revision':site.get('edit_revision',0),'client':next((d['value'] for d in site['details'] if d['key']=='client'),''),'contractor':contractor,'favorite':site['code'] in stars,'default_favorite':site['code'] in defaults,
   'management':{'status':'미등록','note':'현장별 평가점수·제재 현황이 확인되면 표시합니다.'}})
 return out

@router.get('/sites')
def sites(db:DbDep,user=Depends(authorized)):return result({'items':site_data(db,user)})

@router.get('/home')
def home_dashboard(db:DbDep,user=Depends(authorized)):
 from app.modules.workspace_home import home
 return result(home(db,user))

@router.get('/functional-readiness')
def functional_readiness(db:DbDep,user=Depends(authorized)):
 from app.modules.workspace_home import readiness
 return result(readiness(db))

@router.get('/site-weather/{code}')
def site_weather(code:str,db:DbDep,user=Depends(authorized)):
 from app.modules.workspace_home import weather
 return result(weather(db,code))

class FavoriteBody(BaseModel):
 model_config=ConfigDict(extra='forbid')
 favorite:StrictBool

@router.put('/sites/{code}/favorite')
def favorite(code:str,body:FavoriteBody,db:DbDep,user=Depends(authorized)):
 if code not in {s['code'] for s in site_data(db,user)}:raise HTTPException(404,'현장을 찾지 못했습니다.')
 db.execute(text('INSERT INTO workspace_site_preferences(user_id,site_code,is_favorite) VALUES(:uid,:code,:value) ON CONFLICT(user_id,site_code) DO UPDATE SET is_favorite=excluded.is_favorite,updated_at=CURRENT_TIMESTAMP'),{'uid':user.id,'code':code,'value':int(body.favorite)});db.commit()
 return result({'code':code,'favorite':body.favorite})


from app.modules.site_directory import SiteInfoCompletion

@router.put('/sites/{code}/missing-info')
def complete_site_info(code:str,body:SiteInfoCompletion,db:DbDep,user=Depends(authorized)):
 from app.modules.site_directory import complete_missing_info
 return result(complete_missing_info(code,body,db,user))

@router.get('/seoul-weather')
def seoul_weather_forecast(user=Depends(authorized)):
 from app.modules.workspace_home import seoul_weather
 return result(seoul_weather())


@router.get('/site-manager-photo/{site_code}')
def site_manager_photo(site_code:str,db:DbDep,user=Depends(authorized)):
 if getattr(user.role,'value',user.role)!='HQ_SAFE':raise HTTPException(403,'사진 조회 권한을 확인하세요.')
 from app.modules.site_directory import catalog
 from app.modules.workspace_manager_photos import manager_registry,verified_manager_photo
 _,sites=catalog(db);site=next((s for s in sites if s['code']==site_code),None)
 photo=verified_manager_photo(site,DATA.parent,manager_registry(DATA.parent)) if site else None
 if photo is None:raise HTTPException(404,'소장 사진을 확인하고 있습니다.')
 return Response(photo['bytes'],media_type='image/webp',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})

@router.get('/organization-chart/{kind}')
def organization_chart(kind:str,user=Depends(authorized)):
 files={'company':'company.png','safety':'safety.png'}
 if kind not in files:raise HTTPException(404,'조직도를 찾지 못했습니다.')
 file=DATA.parent/'organization'/files[kind]
 if not file.is_file():raise HTTPException(404,'조직도를 확인하고 있습니다.')
 with file.open('rb') as stream:
  if stream.read(8)!=b'\x89PNG\r\n\x1a\n':raise HTTPException(503,'조직도를 확인하고 있습니다.')
 return FileResponse(file,media_type='image/png',headers={'Cache-Control':'private, no-store','Vary':'Authorization','X-Content-Type-Options':'nosniff'})

@router.get('/organization-chart/{kind}/people')
def organization_chart_people(kind:str,user=Depends(authorized)):
 import hashlib,math
 if kind not in {'company','safety'}:raise HTTPException(404,'조직도를 찾지 못했습니다.')
 folder=DATA.parent/'organization';file=folder/'people.json';image=folder/(kind+'.png')
 if not file.is_file() or not image.is_file():raise HTTPException(404,'인물 정보를 확인하고 있습니다.')
 try:
  meta=json.loads(file.read_text(encoding='utf-8-sig'))
  charts=[item for item in meta['charts'] if item.get('kind')==kind]
  if len(charts)!=1:raise ValueError()
  chart=charts[0];digest=hashlib.sha256(image.read_bytes()).hexdigest()
  if digest!=chart['png_sha256']:raise ValueError()
  data_bytes=DATA.read_bytes();rows=json.loads(data_bytes.decode('utf-8-sig'))['duties'];bound=hashlib.sha256(data_bytes).hexdigest()==meta['workspace_duties']['sha256'];out=[];seen=set()
  for person in chart['people']:
   box=person['hitbox'];values=[box[k] for k in ('x','y','w','h')]
   if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in values):continue
   x,y,w,h=values
   if not (0<=x<1 and 0<=y<1 and w>0 and h>0 and x+w<=1.000001 and y+h<=1.000001):continue
   ident=person['occurrence_id']
   if not isinstance(ident,str) or not ident or ident in seen:continue
   seen.add(ident);match=person.get('duty_match',{});key=match.get('match_key') or {};identity=(key.get('department'),key.get('rank'),key.get('name'))
   indices=match.get('row_indices',[]);actual=[i for i,r in enumerate(rows) if (r['department'],r['rank'],r['name'])==identity]
   matched=bound and match.get('status') in {'matched_provisional','matched_mixed','matched_confirmed'} and bool(actual) and indices==actual and identity==(person.get('department'),person.get('rank'),person.get('name'))
   out.append({'id':ident,'name':person.get('name',''),'rank':person.get('rank',''),'department':person.get('department',''),'position':person.get('position',''),'site_name':person.get('site_name',''),'hitbox':dict(zip(('x','y','w','h'),values)),'match_key':key if matched else None})
  return result({'kind':kind,'image_sha256':digest,'people':out})
 except (KeyError,TypeError,ValueError,OSError):raise HTTPException(503,'인물 정보를 확인하고 있습니다.')

# New positioned signing does not mutate legacy /pdf-signing or evaluation records.
from app.modules.workspace_signing import install as install_document_signing
install_document_signing(router,authorized)

from app.modules.workspace_inspections import install as install_inspection_publications
install_inspection_publications(router,authorized,result)

from app.modules.workspace_site_notes import install as install_site_notes
install_site_notes(router,result)

from app.modules.workspace_site_info import install as install_site_info
install_site_info(router,result)


from app.modules.workspace_site import router as site_workspace_router
router.include_router(site_workspace_router)


@router.get('/evaluation-status')
def evaluation_status(db:DbDep,user=Depends(authorized)):
 from app.modules.workspace_evaluation import evaluation_status as project
 return result(project(db,user))
