"""Authenticated site address/description corrections with immutable prior values."""
import json
from uuid import UUID
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,StrictInt,field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError,OperationalError
from app.core.auth import DbDep
from app.modules.workspace_site_notes import member

DDL='''CREATE TABLE IF NOT EXISTS site_directory_corrections_v1 (
 request_id TEXT PRIMARY KEY,site_code TEXT NOT NULL,revision INTEGER NOT NULL,
 before_address TEXT NOT NULL,before_description TEXT NOT NULL,address TEXT NOT NULL,description TEXT NOT NULL,
 updated_by INTEGER NOT NULL REFERENCES users(id),updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(site_code,revision))'''

def migrate(conn):conn.execute(text(DDL))

def apply(db,sites):
 rows=db.execute(text('''SELECT c.* FROM site_directory_corrections_v1 c
 JOIN (SELECT site_code,MAX(revision)AS rev FROM site_directory_corrections_v1 GROUP BY site_code)x
 ON c.site_code=x.site_code AND c.revision=x.rev''')).mappings().all()
 latest={r['site_code']:r for r in rows}
 for s in sites:
  s.update(description=s.get('description',''),edit_revision=0)
  if s['code']not in latest:continue
  r=latest[s['code']];changed=s.get('address','')!=r['address']
  s.update(address=r['address'],description=r['description'],edit_revision=r['revision'])
  # A coordinate registered for a different address cannot represent the correction.
  if changed:s.update(latitude=None,longitude=None)
 return sites

class SiteInfoChange(BaseModel):
 model_config=ConfigDict(extra='forbid')
 request_id:UUID
 expected_revision:StrictInt=Field(ge=0)
 expected_address:str=Field(max_length=400)
 expected_description:str=Field(max_length=1200)
 address:str=Field(min_length=1,max_length=400)
 description:str=Field(max_length=1200)
 @field_validator('address')
 @classmethod
 def address_text(cls,v):
  v=v.strip()
  if not v or any(ord(c)<32 for c in v):raise ValueError('주소를 확인해 주세요.')
  return v
 @field_validator('description')
 @classmethod
 def description_text(cls,v):
  v=v.strip()
  if any(ord(c)<32 and c not in '\n\t'for c in v):raise ValueError('현장 설명을 확인해 주세요.')
  return v

def save(code,payload,db,user):
 from app.modules.site_directory import catalog
 from app.modules.workspace_site_scope import annual_unit_contract
 member(user)
 request=str(payload.request_id)
 old=db.execute(text('SELECT * FROM site_directory_corrections_v1 WHERE request_id=:id'),{'id':request}).mappings().first()
 if old:
  if old['site_code']!=code or old['updated_by']!=user.id or old['address']!=payload.address or old['description']!=payload.description:raise HTTPException(409,'저장 요청을 다시 확인해 주세요.')
  return {'saved':True,'site_code':code,'revision':old['revision']}
 _,sites=catalog(db);site=next((s for s in sites if s['code']==code and not annual_unit_contract(s)),None)
 if site is None:raise HTTPException(404,'현장을 찾지 못했습니다.')
 if (site['edit_revision'],site['address'],site['description'])!=(payload.expected_revision,payload.expected_address,payload.expected_description):raise HTTPException(409,'다른 사용자가 먼저 수정했거나 현장 원장이 바뀌었습니다. 새로고침 후 확인해 주세요.')
 if(site['address'],site['description'])==(payload.address,payload.description):return {'saved':True,'site_code':code,'revision':site['edit_revision']}
 try:
  row=db.execute(text('''INSERT INTO site_directory_corrections_v1
  (request_id,site_code,revision,before_address,before_description,address,description,updated_by)
  SELECT :id,:code,:rev,:before_address,:before_description,:address,:description,:uid
  WHERE COALESCE((SELECT MAX(revision)FROM site_directory_corrections_v1 WHERE site_code=:code),0)=:expected'''),
  {'id':request,'code':code,'rev':payload.expected_revision+1,'before_address':site['address'],'before_description':site['description'],'address':payload.address,'description':payload.description,'uid':user.id,'expected':payload.expected_revision})
  if row.rowcount!=1:raise HTTPException(409,'다른 사용자가 먼저 수정했습니다. 새로고침 후 확인해 주세요.')
  db.commit()
 except (IntegrityError,OperationalError):db.rollback();raise HTTPException(409,'저장 결과를 다시 확인해 주세요.')from None
 except Exception:db.rollback();raise
 return {'saved':True,'site_code':code,'revision':payload.expected_revision+1}

def install(router,result):
 @router.put('/sites/{code}/info')
 def update_info(code:str,payload:SiteInfoChange,db:DbDep,user=Depends(member)):
  return result(save(code,payload,db,user))
