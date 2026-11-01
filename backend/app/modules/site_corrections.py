"""Scoped, append-only corrections over site-directory source data."""
from copy import deepcopy
import hashlib,json,re
from datetime import datetime,timezone,timedelta
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field,StrictInt,model_validator
from sqlalchemy import inspect,text
from sqlalchemy.exc import IntegrityError,OperationalError
from app.config.settings import settings
from app.core.auth import DbDep,get_current_user

router=APIRouter(prefix='/site-corrections',tags=['site-corrections'])
TABLE='site_directory_correction_events'
def private(value):return JSONResponse(value,headers={'Cache-Control':'private, no-store','Vary':'Authorization'})

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def store_ready(db):
 try:
  cols={c['name']for c in inspect(db.get_bind()).get_columns(TABLE)}
  required={'site_code','revision','field','contact_id','field_label','value','before_value','source_sha256','request_id','request_sha256','changed_by','actor_name','changed_at'}
  if cols!=required:return False
  triggers={r[0]for r in db.execute(text("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name=:table"),{'table':TABLE})}
  return {'site_corrections_no_update','site_corrections_no_delete'}<=triggers
 except Exception:return False

def availability(db):
 try:
  exists=db.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:table"),{'table':TABLE}).first()
  if exists and not store_ready(db):return 'UNAVAILABLE'
 except Exception:return 'UNAVAILABLE'
 path=settings.storage_root/'site-corrections/config.json'
 try:
  if not path.is_file():return 'DISABLED'
  if path.stat().st_size>4096:return 'UNAVAILABLE'
  cfg=json.loads(path.read_text('utf8'))
  if set(cfg)!={'schema','enabled'}or type(cfg['schema'])is not int or cfg['schema']!=1 or type(cfg['enabled'])is not bool:return 'UNAVAILABLE'
  if not cfg['enabled']:return 'DISABLED'
  return 'READY'if store_ready(db)else'UNAVAILABLE'
 except Exception:return 'UNAVAILABLE'

def base_fields(site):
 out=[{'field':key,'contact_id':'','label':label,'value':str(site.get(key)or'')}for key,label in [('address','주소'),('description','현장 설명')]]
 seen=set()
 for c in site.get('contacts',[]):
  key=c.get('contact_id')
  if not key:continue
  if key in seen:raise HTTPException(409,'담당자 연결을 확인해 주세요. 기존 정보는 유지됩니다.')
  seen.add(key)
  for field,label in [('phone','전화번호'),('rank','직급')]:
   out.append({'field':field,'contact_id':key,'label':str(c.get('name')or'담당자')+' '+label,'value':str(c.get(field)or'')})
 for row in out:row['source_sha256']=digest([site['code'],row['field'],row['contact_id'],row['value']])
 return out

def local_time(value):
 value=datetime.fromisoformat(str(value))
 if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
 return value.astimezone(timezone(timedelta(hours=9))).isoformat()

def rows_for(db,code):
 return [dict(r)for r in db.execute(text('SELECT * FROM '+TABLE+' WHERE site_code=:code ORDER BY revision'),{'code':code}).mappings()]

def state(db,site):
 rows=rows_for(db,site['code']);latest={(r['field'],r['contact_id']):r for r in rows};fields=base_fields(site)
 for field in fields:
  event=latest.get((field['field'],field['contact_id']));field['source_value']=field['value'];field['review_required']=bool(event and event['source_sha256']!=field['source_sha256']and event['value']!=field['source_value'])
  if event and not field['review_required']:field['value']=event['value']
  field['previous_correction']=event['value']if event and field['review_required']else None
 return {'available':True,'code':site['code'],'name':site['name'],'revision':max((r['revision']for r in rows),default=0),'fields':fields,'unmatched_corrections':[{'field':r['field'],'contact_id':r['contact_id'],'label':r['field_label']}for key,r in latest.items()if key not in {(f['field'],f['contact_id'])for f in fields}],'history':[{'revision':r['revision'],'field':r['field'],'contact_id':r['contact_id'],'label':r['field_label'],'before_value':r['before_value'],'value':r['value'],'actor_name':r['actor_name'],'changed_at':local_time(r['changed_at'])}for r in rows]}

def project(db,sites):
 mode=availability(db)
 if not store_ready(db):
  sites=deepcopy(sites)
  for site in sites:
   site.update(correction_available=False,correction_can_edit=False,correction_status=mode)
   if mode=='UNAVAILABLE':
    site.update(address=None,description=None,latitude=None,longitude=None)
    for contact in site.get('contacts',[]):
     contact.update(phone='',rank='',rank_confirmed=False,label=str(contact.get('name')or'담당자')+' ('+str(contact.get('role')or'담당')+') · 정보 확인 중')
  return sites
 result=deepcopy(sites)
 for site in result:
  site.update(correction_available=True,correction_can_edit=mode=='READY',correction_status=mode);current=state(db,site);contacts={c['contact_id']:c for c in site['contacts']};site['correction_revision']=current['revision'];site['correction_review_required']=bool(current['unmatched_corrections'])or any(f['review_required']for f in current['fields'])
  if any(r['field']=='address'for r in current['history']):site['latitude']=site['longitude']=None
  for field in current['fields']:
   if field['value']==field['source_value']:continue
   if field['field']in {'address','description'}:
    if field['field']=='address'and field['value']!=field['source_value']:site['latitude']=site['longitude']=None
    site[field['field']]=field['value']
   elif field['contact_id']in contacts:
    c=contacts[field['contact_id']];c[field['field']]=field['value']
    if field['field']=='rank':
     c['rank_confirmed']=bool(field['value'])or'소장'in str(c.get('role','')).split('·');role=str(c.get('role',''));c['label']=c['name']+(field['value']+'('+role+')'if field['value']else'소장'+('('+role.replace('소장·','')+')'if role!='소장'else'')if'소장'in role.split('·')else'('+role+')')
 return result

def canonical_site_code(db,site,aliases,*,forbidden=False):
 canonical=aliases.get(site.site_code,site.site_code);codes={canonical}|{key for key,value in aliases.items()if value==canonical}
 if len(codes)>500:raise HTTPException(503,'현장 연결을 확인해 주세요.')
 from app.modules.sites.models import Site
 identities={row[0]for row in db.query(Site.id).filter(Site.site_code.in_(codes)).all()}
 if identities!={site.id}:raise HTTPException(403 if forbidden else 409,'소속 현장의 연결을 확인해 주세요. 다른 현장으로 연결하지 않습니다.')
 return canonical

def actor_site(db,user,code):
 role=getattr(user.role,'value',user.role)
 if not user.is_active or getattr(user,'must_change_password',False)or getattr(user,'government_preview',False):raise HTTPException(403,'현장 정보 수정 권한을 확인해 주세요.')
 if role=='SITE':
  from app.modules.workspace_site_access import require_site_identity,require_own_site
  from app.modules.sites.models import Site
  ident=require_site_identity(user);own=require_own_site(user,db.get(Site,ident))
 elif role!='HQ_SAFE'or getattr(user,'ui_type',None)!='HQ_SAFE':raise HTTPException(403,'현장 정보 수정 권한을 확인해 주세요.')
 from app.modules.site_directory import catalog
 data,sites=catalog(db,include_corrections=False);aliases=data.get('aliases',{});canonical=aliases.get(code,code)
 if role=='SITE'and canonical!=canonical_site_code(db,own,aliases,forbidden=True):raise HTTPException(403,'로그인한 현장만 수정할 수 있습니다.')
 if role!='SITE':
  from app.modules.sites.models import Site
  codes={canonical}|{key for key,value in aliases.items()if value==canonical}
  if len(codes)>500:raise HTTPException(503,'현장 연결을 확인해 주세요.')
  existing=db.query(Site).filter(Site.site_code.in_(codes)).first()
  if existing is not None:canonical_site_code(db,existing,aliases)
 site=next((s for s in sites if s['code']==canonical),None)
 from app.modules.workspace_site_scope import annual_unit_contract
 if site is None or annual_unit_contract(site):raise HTTPException(404,'현장 정보를 찾지 못했습니다.')
 return site

class Change(BaseModel):
 model_config=ConfigDict(extra='forbid')
 field:Literal['address','description','phone','rank']
 contact_id:str=''
 value:str=Field(max_length=2000)
 expected_source_sha256:str=Field(pattern=r'^[0-9a-f]{64}$')
 @model_validator(mode='after')
 def valid(self):
  self.value=self.value.strip()
  if any(ord(c)<32 and c not in '\n\t'for c in self.value):raise ValueError('입력 내용을 확인해 주세요.')
  if self.field in {'phone','rank'}:
   if not re.fullmatch(r'[0-9a-f]{32}',self.contact_id):raise ValueError('담당자를 확인해 주세요.')
  elif self.contact_id:raise ValueError('현장 항목에는 담당자를 지정하지 않습니다.')
  if self.field=='phone'and self.value and(not re.fullmatch(r'[+0-9() -]+',self.value)or not 4<=len(re.sub(r'\D','',self.value))<=20):raise ValueError('전화번호를 확인해 주세요.')
  if self.field=='rank'and self.value and(not re.fullmatch(r'[가-힣A-Za-z ]+',self.value)or len(self.value)>20):raise ValueError('직급을 확인해 주세요.')
  if self.field=='address'and(len(self.value)>400 or '\n'in self.value or'\t'in self.value):raise ValueError('주소를 확인해 주세요.')
  return self
class Save(BaseModel):
 model_config=ConfigDict(extra='forbid')
 expected_revision:StrictInt=Field(ge=0)
 request_id:str=Field(pattern=r'^[0-9a-f]{32}$')
 changes:list[Change]=Field(min_length=1,max_length=100)

@router.get('/{code}')
def read_corrections(code:str,db:DbDep,user=Depends(get_current_user)):
 site=actor_site(db,user,code);mode=availability(db)
 if not store_ready(db):return private({'available':False,'status':mode,'code':site['code']})
 return private({**state(db,site),'can_edit':mode=='READY','status':mode})

@router.put('/{code}')
def save_corrections(code:str,body:Save,db:DbDep,user=Depends(get_current_user)):
 site=actor_site(db,user,code)
 if availability(db)!='READY':raise HTTPException(404,'현장 정보 수정 연결을 준비하고 있습니다.')
 from app.modules.site_directory import DATA
 source_hash=hashlib.sha256(DATA.read_bytes()).hexdigest();site=actor_site(db,user,code)
 if hashlib.sha256(DATA.read_bytes()).hexdigest()!=source_hash:raise HTTPException(409,'현장 원본이 바뀌었습니다. 새로고침해 주세요.')
 current=state(db,site);payload_sha=digest(body.model_dump());events=rows_for(db,site['code']);prior=[r for r in events if r['changed_by']==user.id and r['request_id']==body.request_id]
 if prior:
  if any(r['request_sha256']!=payload_sha for r in prior):raise HTTPException(409,'같은 저장 요청의 내용이 달라졌습니다.')
  return private({'saved':len(prior),'revision':max(r['revision']for r in prior),'request_id':body.request_id,'replayed':True})
 conflict='현장 정보가 바뀌었습니다. 새로고침한 뒤 수정해 주세요.'
 if body.expected_revision!=current['revision']:raise HTTPException(409,conflict)
 fields={(r['field'],r['contact_id']):r for r in current['fields']};seen=set()
 for change in body.changes:
  key=(change.field,change.contact_id)
  if key in seen:raise HTTPException(422,'같은 항목이 중복되었습니다.')
  seen.add(key)
  if key not in fields:raise HTTPException(404,'담당 항목을 찾지 못했습니다.')
  if change.expected_source_sha256!=fields[key]['source_sha256']:raise HTTPException(409,conflict)
  if change.value==fields[key]['value']and not fields[key]['review_required']:raise HTTPException(422,'바뀐 내용을 입력해 주세요.')
 try:
  for i,change in enumerate(body.changes):
   old=fields[(change.field,change.contact_id)];revision=current['revision']+i+1
   result=db.execute(text('INSERT INTO '+TABLE+'(site_code,revision,field,contact_id,field_label,value,before_value,source_sha256,request_id,request_sha256,changed_by,actor_name) SELECT :code,:rev,:field,:contact,:label,:value,:before,:source,:request,:hash,:uid,:name WHERE COALESCE((SELECT MAX(revision) FROM '+TABLE+' WHERE site_code=:code),0)=:expected'),{'code':site['code'],'rev':revision,'field':change.field,'contact':change.contact_id,'label':old['label'],'value':change.value,'before':old['value'],'source':old['source_sha256'],'request':body.request_id,'hash':payload_sha,'uid':user.id,'name':user.name,'expected':revision-1})
   if result.rowcount!=1:raise HTTPException(409,conflict)
  if hashlib.sha256(DATA.read_bytes()).hexdigest()!=source_hash or availability(db)!='READY':raise HTTPException(409,conflict)
  db.commit()
 except (IntegrityError,OperationalError)as error:
  db.rollback();raise HTTPException(409,conflict)from error
 except BaseException:db.rollback();raise
 return private({'saved':len(body.changes),'revision':current['revision']+len(body.changes),'request_id':body.request_id,'replayed':False})


@router.get('/{code}/receipts/{request_id}')
def read_receipt(code:str,request_id:str,db:DbDep,user=Depends(get_current_user)):
 site=actor_site(db,user,code)
 if not re.fullmatch(r'[0-9a-f]{32}',request_id):raise HTTPException(422,'저장 요청을 확인해 주세요.')
 if not store_ready(db):raise HTTPException(503,'저장 결과를 확인하지 못했습니다.')
 rows=[r for r in rows_for(db,site['code'])if r['changed_by']==user.id and r['request_id']==request_id]
 if not rows:raise HTTPException(404,'아직 저장 결과를 확인하지 못했습니다.')
 return private({'saved':len(rows),'revision':max(r['revision']for r in rows),'request_id':request_id,'replayed':True})


def overlay_site_models(db,rows):
 mode=availability(db)
 if not store_ready(db):
  if mode=='DISABLED':return rows
  raise HTTPException(503,'현장 수정 정보를 확인하지 못했습니다. 잠시 뒤 다시 조회해 주세요.')
 corrected={row[0]for row in db.execute(text('SELECT DISTINCT site_code FROM '+TABLE))}
 if not corrected:return rows
 from app.modules.site_directory import catalog
 from app.schemas.sites import SiteResponse
 from pydantic import BaseModel
 data,sites=catalog(db);aliases=data.get('aliases',{});by_code={s['code']:s for s in sites};out=[]
 for row in rows:
  if aliases.get(row.site_code,row.site_code)not in corrected:out.append(row);continue
  code=canonical_site_code(db,row,aliases);item=by_code.get(code)
  if not item:out.append(row);continue
  updates={'address':item['address'],'latitude':item.get('latitude'),'longitude':item.get('longitude')}
  if not isinstance(row,BaseModel)or'description'in type(row).model_fields:updates['description']=item.get('description','')
  value=row if isinstance(row,BaseModel)else SiteResponse.model_validate(row)
  out.append(value.model_copy(update=updates))
 return out
