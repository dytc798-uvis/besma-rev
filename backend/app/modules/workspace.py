"""Authenticated headquarters workspace. Existing operational records remain authoritative."""
import json,re
from pathlib import Path
from functools import lru_cache
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import JSONResponse,FileResponse
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
 conn.execute(text('CREATE TABLE IF NOT EXISTS workspace_site_preferences (user_id INTEGER NOT NULL REFERENCES users(id),site_code TEXT NOT NULL,is_favorite INTEGER NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,site_code))'))

@router.get('/bootstrap')
def bootstrap(user=Depends(authorized)):
 data=dataset()
 from app.core.government_workspace_access import can_manage_government
 return result({'permissions':{'manage_government_forms':can_manage_government(user)},'version':'2026.10.26.3','user':{'name':user.name,'role':getattr(user.role,'value',user.role)},'sources':data['sources'],
  'menus':[{'id':1,'title':'기능인인정제'},{'id':2,'title':'업무분장'},{'id':3,'title':'위험성평가 DB'},{'id':4,'title':'양식·법령 탐색'},
   {'id':5,'title':'현장 정보 검색'},{'id':6,'title':'도급사 안전기준'},{'id':7,'title':'관급공사 현장 소통'},{'id':8,'title':'사용설명서'}]})

@router.get('/duties')
def duties(user=Depends(authorized)):return result({'items':dataset()['duties'],'source':dataset()['sources']['duties']})

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
 from app.modules.sites.models import Site
 from app.modules.document_explorer.government_access import is_government_site_record
 from app.modules.documents.active_site_scope import in_active_scope,today_kst
 sites=[{'code':s.site_code,'name':s.site_name} for s in db.query(Site).all() if is_government_site_record(s) and in_active_scope(s,today_kst(),'government')]
 return result({'items':sites})

@router.get('/contractors')
def contractors(user=Depends(authorized)):
 data=dataset();return result({'items':data['policies'],'posco_criteria':data['posco_criteria']})

@router.get('/contractors/{item_id}/pages/{page}')
def contractor_page(item_id:int,page:int,user=Depends(authorized)):
 item=next((p for p in dataset()['policies'] if p['id']==item_id),None)
 if not item or page<1 or page>item.get('pages',0):raise HTTPException(404,'자료를 찾지 못했습니다.')
 file=DATA.parent/'policy-previews'/f'{item_id}-{page}.jpg'
 if not file.is_file():raise HTTPException(404,'미리보기를 준비하고 있습니다.')
 return FileResponse(file,media_type='image/jpeg',headers={'Cache-Control':'private, no-store','Vary':'Authorization'})

def site_data(db,user):
 from app.modules.site_directory import catalog,favorites
 _,sites=catalog(db)
 role=getattr(user.role,'value',user.role)
 safety=role in {'HQ_SAFE','HQ_SAFE_ADMIN'} or (role=='ACCIDENT_ADMIN' and getattr(user,'login_id','') in {'sijung','안전보건-정상익','hq01'})
 defaults=set()
 if safety:
  teams=SAFETY_TEAMS.get(user.name)
  defaults={s['code'] for s in sites if teams is None or (m:=re.match(r'\[(\d+)\.',s['name'])) and int(m.group(1)) in teams}
 saved=set(favorites(db,user.id));prefs=dict(db.execute(text('SELECT site_code,is_favorite FROM workspace_site_preferences WHERE user_id=:uid'),{'uid':user.id}).all())
 stars=(defaults|saved|{k for k,v in prefs.items() if v})-{k for k,v in prefs.items() if not v}
 out=[]
 for site in sites:
  contractor=next((d['value'] for d in site['details'] if d['key']=='contractor'),'')
  out.append({'code':site['code'],'name':site['name'],'address':site['address'],'latitude':site['latitude'],'longitude':site['longitude'],
   'contacts':[{k:c.get(k,'') for k in ['name','role','rank','label','phone']} for c in site['contacts']],
   'contractor':contractor,'favorite':site['code'] in stars,'default_favorite':site['code'] in defaults,
   'management':{'status':'미등록','note':'현장별 평가점수·제재 현황이 확인되면 표시합니다.'}})
 return out

@router.get('/sites')
def sites(db:DbDep,user=Depends(authorized)):return result({'items':site_data(db,user)})

class FavoriteBody(BaseModel):
 model_config=ConfigDict(extra='forbid')
 favorite:StrictBool

@router.put('/sites/{code}/favorite')
def favorite(code:str,body:FavoriteBody,db:DbDep,user=Depends(authorized)):
 if code not in {s['code'] for s in site_data(db,user)}:raise HTTPException(404,'현장을 찾지 못했습니다.')
 db.execute(text('INSERT INTO workspace_site_preferences(user_id,site_code,is_favorite) VALUES(:uid,:code,:value) ON CONFLICT(user_id,site_code) DO UPDATE SET is_favorite=excluded.is_favorite,updated_at=CURRENT_TIMESTAMP'),{'uid':user.id,'code':code,'value':int(body.favorite)});db.commit()
 return result({'code':code,'favorite':body.favorite})
