"""HQ safety site directory; contact snapshots are private, favorites belong to the caller."""
import hashlib,json,re
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,StrictBool,StrictInt,Field,field_validator
from sqlalchemy import text
from app.config.settings import settings
from app.core.auth import DbDep,get_current_user

router=APIRouter(prefix='/site-directory',tags=['site-directory'])
DATA=Path(settings.storage_root)/'site-directory'/'directory.json'
VERSION='2026.10.20.4'

def migrate(connection):
 connection.execute(text('''CREATE TABLE IF NOT EXISTS site_directory_favorites (
 user_id INTEGER NOT NULL REFERENCES users(id),site_code TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,site_code))'''))
 connection.execute(text('''CREATE TABLE IF NOT EXISTS site_directory_contact_ranks (
 contact_id TEXT PRIMARY KEY,rank TEXT NOT NULL,revision INTEGER NOT NULL,
 updated_by INTEGER NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)'''))

def contact_id(contact,site_code):
 identity=contact['name']+'\0'+(re.sub(r'\D','',contact['phone']) or site_code)
 return hashlib.sha256(identity.encode()).hexdigest()[:32]

def ranked_contact(contact,site_code,ranks):
 entry=dict(contact);key=contact_id(contact,site_code);entry.update(contact_id=key,rank_revision=0)
 if key in ranks:
  override=ranks[key];rank=override['rank'];role=entry['role'];entry.update(rank=rank,rank_revision=override['revision'],rank_confirmed=bool(rank) or '소장' in role.split('·'))
  entry['label']=entry['name']+(rank+'('+role+')' if rank else '소장'+('('+role.replace('소장·','')+')' if role!='소장' else '') if '소장' in role.split('·') else '('+role+')')
 return entry

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
 ranks={r['contact_id']:dict(r) for r in db.execute(text('SELECT contact_id,rank,revision FROM site_directory_contact_ranks')).mappings()}
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
  contract_info=item.get('contract_info',{});contracts=contract_info.get('contracts',[])
  amount=contract_info.get('total') if contracts else value('project_amount',erp.get('amount'))
  if amount is not None and float(amount)<=0:amount=None
  amount_label='현장 총 공사금액 (VAT 별도)' if contracts else '공사금액'
  fields=[detail('amount',amount_label,amount,'원'),detail('period','공사기간',period),
   detail('contractor','원도급사',value('contractor_name',erp.get('contractor'))),detail('client','발주처',value('client_name',erp.get('client'))),
   detail('contract_type','계약구분',value('contract_type')),detail('contract_date','계약일',value('contract_date')),
   detail('work_types','공종',value('work_types',erp.get('work_types'))),detail('buildings','동수',value('building_count'),'동'),
   detail('underground','지하층',value('floor_underground'),'층'),detail('ground','지상층',value('floor_ground'),'층'),
   detail('households','세대수',value('household_count'),'세대'),detail('area','연면적',value('gross_area'),value('gross_area_unit','')),
   detail('usage','주용도',value('main_usage'))]
  if contract_info and not contract_info.get('complete'):
   fields.extend([detail('contract_status','계약금액 확인',contract_info.get('status')),detail('confirmed_subtotal','확인분 합계 (VAT 별도)',contract_info.get('confirmed_subtotal') or None,'원')])
  result.append({'code':item['code'],'name':item['name'],'address':value('address',erp.get('address','')) or '',
    'latitude':current.get('latitude'),'longitude':current.get('longitude'),'contacts':[ranked_contact(c,item['code'],ranks) for c in item['contacts']],
    'contracts':[{'name':c['name'],'amount':c['amount'],'basis':c['basis'],'start':c.get('start',''),'end':c.get('end','')} for c in contracts],
    'contract_total_complete':contract_info.get('complete',False),'details':[f for f in fields if f is not None]})
 return data,result

@router.get('')
def listing(db:DbDep,user=Depends(authorized)):
 data,sites=catalog(db)
 return response({'sites':sites,'favorite_codes':favorites(db,user.id),'source':data.get('source',{}),'version':data.get('version',VERSION)})

class ContactRankChange(BaseModel):
 model_config=ConfigDict(extra='forbid')
 contact_id:str=Field(pattern=r'^[0-9a-f]{32}$')
 rank:str=Field(max_length=20)
 expected_revision:StrictInt=Field(ge=0)
 @field_validator('rank')
 @classmethod
 def validate_rank(cls,value):
  value=value.strip()
  if value and not re.fullmatch(r'[가-힣A-Za-z ]+',value):raise ValueError('직급을 확인해 주세요.')
  return value

class ContactRankChanges(BaseModel):
 model_config=ConfigDict(extra='forbid')
 changes:list[ContactRankChange]=Field(min_length=1,max_length=100)

@router.put('/contact-ranks')
def set_contact_ranks(payload:ContactRankChanges,db:DbDep,user=Depends(authorized)):
 data=snapshot();known={contact_id(c,s['code']) for s in data['sites'] for c in s['contacts']}
 keys=[c.contact_id for c in payload.changes]
 if len(keys)!=len(set(keys)):raise HTTPException(422,'같은 담당자가 중복되었습니다.')
 if any(k not in known for k in keys):raise HTTPException(404,'담당자를 찾지 못했습니다.')
 try:
  for change in payload.changes:
   row=db.execute(text('SELECT revision FROM site_directory_contact_ranks WHERE contact_id=:key'),{'key':change.contact_id}).first()
   if (row[0] if row else 0)!=change.expected_revision:raise HTTPException(409,'다른 팀원이 먼저 수정했습니다. 새로고침한 뒤 다시 확인해 주세요.')
   result=db.execute(text('''INSERT INTO site_directory_contact_ranks(contact_id,rank,revision,updated_by)
    VALUES(:key,:rank,1,:uid) ON CONFLICT(contact_id) DO UPDATE SET rank=excluded.rank,
    revision=site_directory_contact_ranks.revision+1,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP
    WHERE site_directory_contact_ranks.revision=:revision'''),{'key':change.contact_id,'rank':change.rank,'uid':user.id,'revision':change.expected_revision})
   if result.rowcount!=1:raise HTTPException(409,'다른 팀원이 먼저 수정했습니다. 새로고침한 뒤 다시 확인해 주세요.')
  db.commit()
 except Exception:
  db.rollback();raise
 return response({'saved':len(payload.changes),'version':VERSION})

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
