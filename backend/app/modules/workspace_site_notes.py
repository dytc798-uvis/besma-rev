"""Append-only site communication within the existing safety-team boundary."""
import datetime
from uuid import UUID
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.core.auth import DbDep, get_current_user

DDL='''CREATE TABLE IF NOT EXISTS workspace_site_notes (
 id TEXT PRIMARY KEY,site_code TEXT NOT NULL,author_user_id INTEGER NOT NULL REFERENCES users(id),
 body TEXT NOT NULL CHECK(length(body) BETWEEN 1 AND 600),created_at TEXT NOT NULL)'''

def migrate(connection):
 connection.execute(text(DDL))

def member(user=Depends(get_current_user)):
 if not user.is_active or getattr(user.role,'value',user.role)!='HQ_SAFE' or getattr(user,'ui_type','')!='HQ_SAFE':
  raise HTTPException(403,'안전보건실에서 이용할 수 있습니다.')
 return user

class SiteNote(BaseModel):
 model_config=ConfigDict(extra='forbid')
 request_id:UUID
 body:str=Field(min_length=1,max_length=600)
 @field_validator('body')
 @classmethod
 def clean(cls,value):
  value=value.strip()
  if not value or any(ord(c)<32 and c not in '\n\t' for c in value):raise ValueError('메모를 입력해 주세요.')
  return value

def check_site(site_code,db):
 from app.modules.site_directory import catalog
 from app.modules.workspace_site_scope import annual_unit_contract
 if not any(s['code']==site_code and not annual_unit_contract(s) for s in catalog(db)[1]):
  raise HTTPException(404,'현장을 찾지 못했습니다.')

def install(router,result):
 @router.get('/sites/{site_code}/notes')
 def notes(site_code:str,db:DbDep,user=Depends(member)):
  check_site(site_code,db)
  rows=db.execute(text('''SELECT n.id,n.body,n.created_at,u.name AS author_name
   FROM workspace_site_notes n JOIN users u ON u.id=n.author_user_id
   WHERE n.site_code=:site ORDER BY n.created_at DESC,n.id DESC LIMIT 51'''),{'site':site_code}).mappings().all()
  return result({'site_code':site_code,'items':[dict(r) for r in rows[:50]],'has_more':len(rows)>50})
 @router.post('/sites/{site_code}/notes',status_code=201)
 def add_note(site_code:str,payload:SiteNote,db:DbDep,user=Depends(member)):
  check_site(site_code,db);ident=str(payload.request_id)
  existing=db.execute(text('SELECT site_code,author_user_id,body FROM workspace_site_notes WHERE id=:id'),{'id':ident}).mappings().first()
  if existing:
   if existing['site_code']!=site_code or existing['author_user_id']!=user.id or existing['body']!=payload.body:raise HTTPException(409,'메모를 다시 확인해 주세요.')
   return result({'saved':True,'id':ident,'site_code':site_code})
  try:
   db.execute(text('INSERT INTO workspace_site_notes(id,site_code,author_user_id,body,created_at) VALUES (:id,:site,:uid,:body,:at)'),{'id':ident,'site':site_code,'uid':user.id,'body':payload.body,'at':datetime.datetime.now(datetime.timezone.utc).isoformat()});db.commit()
  except IntegrityError:
   db.rollback();raise HTTPException(409,'저장 결과를 확인한 뒤 다시 시도해 주세요.')
  return result({'saved':True,'id':ident,'site_code':site_code})
