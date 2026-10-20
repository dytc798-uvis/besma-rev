"""HQ safety site directory; contact snapshots are private, favorites belong to the caller."""
import json
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,StrictBool
from sqlalchemy import text
from app.config.settings import settings
from app.core.auth import DbDep,get_current_user

router=APIRouter(prefix='/site-directory',tags=['site-directory'])
DATA=Path(settings.storage_root)/'site-directory'/'directory.json'
VERSION='2026.10.20.2'

def migrate(connection):
 connection.execute(text('''CREATE TABLE IF NOT EXISTS site_directory_favorites (
 user_id INTEGER NOT NULL REFERENCES users(id),site_code TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,site_code))'''))

def authorized(user=Depends(get_current_user)):
 if getattr(user.role,'value',user.role)!='HQ_SAFE' or not user.is_active:raise HTTPException(403,'안전보건실에서 이용할 수 있습니다.')
 return user

def response(value):return JSONResponse(value,headers={'Cache-Control':'private, no-store','Vary':'Authorization'})

def snapshot():
 if not DATA.is_file():raise HTTPException(503,'현장 정보를 준비하고 있습니다.')
 return json.loads(DATA.read_text(encoding='utf-8'))

def favorites(db,user_id):
 return [r[0] for r in db.execute(text('SELECT site_code FROM site_directory_favorites WHERE user_id=:uid ORDER BY created_at,site_code'),{'uid':user_id})]

def detail(key,label,value,unit=''):
 if value is None or value=='':return None
 return {'key':key,'label':label,'value':str(value),'unit':unit}

def catalog(db):
 data=snapshot();aliases=data.get('aliases',{})
 rows={str(r['site_code']):dict(r) for r in db.execute(text('''SELECT id,site_code,site_name,address,latitude,longitude,project_amount,start_date,end_date,
 client_name,contractor_name,contract_type,contract_date,work_types,building_count,floor_underground,floor_ground,household_count,gross_area,gross_area_unit,main_usage FROM sites''')).mappings()}
 for alias,code in aliases.items():
  if code not in rows and alias in rows:rows[code]=rows[alias]
 result=[]
 for item in data['sites']:
  current=rows.get(item['code'],{});erp=item.get('erp',{})
  def value(name,fallback=None):
   x=current.get(name)
   return fallback if x is None or x=='' else x
  start=value('start_date');end=value('end_date')
  period=(str(start or '미등록')+' ~ '+str(end or '미등록')) if start or end else erp.get('period')
  fields=[detail('amount','공사금액',value('project_amount',erp.get('amount')),'원'),detail('period','공사기간',period),
   detail('contractor','원도급사',value('contractor_name',erp.get('contractor'))),detail('client','발주처',value('client_name',erp.get('client'))),
   detail('contract_type','계약구분',value('contract_type')),detail('contract_date','계약일',value('contract_date')),
   detail('work_types','공종',value('work_types',erp.get('work_types'))),detail('buildings','동수',value('building_count'),'동'),
   detail('underground','지하층',value('floor_underground'),'층'),detail('ground','지상층',value('floor_ground'),'층'),
   detail('households','세대수',value('household_count'),'세대'),detail('area','연면적',value('gross_area'),value('gross_area_unit','')),
   detail('usage','주용도',value('main_usage'))]
  result.append({'code':item['code'],'name':item['name'],'address':value('address',erp.get('address','')) or '',
    'latitude':current.get('latitude'),'longitude':current.get('longitude'),'contacts':item['contacts'],
    'details':[f for f in fields if f is not None]})
 return data,result

@router.get('')
def listing(db:DbDep,user=Depends(authorized)):
 data,sites=catalog(db)
 return response({'sites':sites,'favorite_codes':favorites(db,user.id),'source':data.get('source',{}),'version':VERSION})

class FavoriteChange(BaseModel):
 model_config=ConfigDict(extra='forbid')
 favorite:StrictBool

@router.put('/favorites/{site_code}')
def set_favorite(site_code:str,payload:FavoriteChange,db:DbDep,user=Depends(authorized)):
 data=snapshot();code=data.get('aliases',{}).get(site_code,site_code)
 if code not in {s['code'] for s in data['sites']}:raise HTTPException(404,'현장을 찾지 못했습니다.')
 if payload.favorite:
  db.execute(text('INSERT INTO site_directory_favorites(user_id,site_code) VALUES(:uid,:code) ON CONFLICT(user_id,site_code) DO NOTHING'),{'uid':user.id,'code':code})
 else:
  db.execute(text('DELETE FROM site_directory_favorites WHERE user_id=:uid AND site_code=:code'),{'uid':user.id,'code':code})
 db.commit()
 return response({'favorite_codes':favorites(db,user.id)})
