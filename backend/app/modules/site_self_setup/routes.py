import re
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import text
from app.core.auth import DbDep, get_current_user
from app.modules.site_self_setup import service as s
from app.modules.sites.models import Site
from app.modules.documents.models import Document
from app.modules.opinions.models import Opinion

router=APIRouter(prefix='/site-invitations',tags=['site-invitations'])

async def body(request, response):
 response.headers['Cache-Control']='no-store';s.throttle(request)
 raw=await request.body()
 if len(raw)>8192:raise HTTPException(413,'입력 길이를 확인해 주세요.')
 try:
  import json
  value=json.loads(raw)
 except Exception:raise HTTPException(400,'입력 내용을 확인해 주세요.')
 if not isinstance(value,dict):raise HTTPException(400,'입력 내용을 확인해 주세요.')
 return value

@router.post('/inspect')
async def inspect(request:Request,response:Response,db:DbDep):
 value=await body(request,response)
 if set(value)!={'token'}:raise HTTPException(400,'링크를 확인해 주세요.')
 return s.inspect_invite(db,value['token'])

@router.post('/accept')
async def accept(request:Request,response:Response,db:DbDep):return s.accept(db,await body(request,response))

@router.get('/owner')
def invitations(response:Response,db:DbDep,user=Depends(get_current_user)):
 s.require_owner(user);response.headers['Cache-Control']='no-store'
 rows=db.execute(text('SELECT * FROM site_setup_invites ORDER BY site_id,issued_at,id')).mappings().all();result=[]
 for r in rows:
  site=db.get(Site,r['site_id']);state=r['state'] if r['expires_at']>time.time() or r['state']!='ACTIVE' else 'EXPIRED'
  result.append({'id':r['id'],'site_code':site.site_code,'site_name':site.site_name,'name':r['expected_name'],'job_title':r['job_title'],'email':r['email'] or '',
  'state':state,'expires_at':r['expires_at'],'claimed_user_id':r['claimed_user_id'],
  'url':'https://www.besma.co.kr/site-setup.html#invite='+s.credential(r['id']) if state=='ACTIVE' else None})
 requests=[dict(r) for r in db.execute(text('SELECT id,site_code,name,email,created_at FROM site_setup_reset_requests WHERE resolved_at IS NULL ORDER BY id DESC')).mappings()]
 return {'version':s.VERSION,'invitations':result,'reset_requests':requests}

@router.post('/owner/renew')
async def renew(request:Request,response:Response,db:DbDep,user=Depends(get_current_user)):
 s.require_owner(user);value=await body(request,response)
 if set(value)!={'id'} or not isinstance(value['id'],str):raise HTTPException(422,'초대 항목을 확인해 주세요.')
 db.rollback();db.execute(text('BEGIN IMMEDIATE'))
 try:
  old=db.execute(text('SELECT * FROM site_setup_invites WHERE id=:id'),{'id':value['id']}).mappings().first()
  if not old or old['state']=='REVOKED':raise HTTPException(409,'최신 링크에서 다시 발급해 주세요.')
  db.execute(text("UPDATE site_setup_invites SET state='REVOKED' WHERE id=:id"),{'id':old['id']})
  ident=s.issue(db,site_id=old['site_id'],name=old['expected_name'],job_title=old['job_title'],email=old['email'],user_id=old['claimed_user_id'] or old['target_user_id'],issued_by=user.id,purpose='RESET' if old['claimed_user_id'] else 'SETUP')
  site=db.get(Site,old['site_id'])
  db.execute(text('UPDATE site_setup_reset_requests SET resolved_at=:now WHERE site_code=:code AND name=:name AND resolved_at IS NULL'),{'now':int(time.time()),'code':site.site_code,'name':old['expected_name']})
  db.commit();return {'result':'ok','id':ident}
 except Exception:db.rollback();raise

@router.get('/access')
def access(response:Response,db:DbDep,user=Depends(get_current_user)):
 response.headers['Cache-Control']='no-store';p=s.profile(db,user)
 if not p:return {'restricted':False,'owner':s.owner(user),'version':s.VERSION}
 site=db.get(Site,user.site_id)
 return {'restricted':True,'owner':False,'name':user.name,'job_title':p['job_title'],'email':p['email'],'site_name':site.site_name,'site_code':site.site_code,'version':s.VERSION}

def require_profile(db,user):
 if not s.profile(db,user):raise HTTPException(403,'현장문서 전용 계정이 아닙니다.')

@router.get('/documents')
def documents(response:Response,db:DbDep,user=Depends(get_current_user)):
 require_profile(db,user);response.headers['Cache-Control']='no-store'
 rows=db.query(Document).filter(Document.site_id==user.site_id).order_by(Document.created_at.desc(),Document.id.desc()).limit(1000).all()
 return {'items':[{'id':r.id,'title':r.title,'status':r.current_status,'date':r.period_start.isoformat() if r.period_start else '', 'file_name':r.file_name or '', 'has_file':bool(r.file_path)} for r in rows]}

@router.get('/documents/{ident}/content')
def content(ident:int,db:DbDep,user=Depends(get_current_user)):
 require_profile(db,user);doc=db.query(Document).filter(Document.id==ident,Document.site_id==user.site_id).first()
 if not doc:raise HTTPException(404,'해당 현장의 문서를 찾을 수 없습니다.')
 from app.modules.documents.routes import download_document_file
 response=download_document_file(ident,db,user,'attachment');response.headers['Cache-Control']='no-store';return response

@router.get('/ideas')
def ideas(response:Response,db:DbDep,user=Depends(get_current_user)):
 require_profile(db,user);response.headers['Cache-Control']='no-store'
 rows=db.query(Opinion).filter(Opinion.site_id==user.site_id).order_by(Opinion.created_at.desc(),Opinion.id.desc()).limit(500).all()
 return {'items':[{'id':r.id,'category':r.category,'content':r.content,'status':getattr(r.status,'value',r.status),'reporter':r.reporter_type,'date':r.created_at.isoformat(),'action_result':r.action_result or ''} for r in rows]}

@router.post('/reset-request')
async def reset_request(request:Request,response:Response,db:DbDep):
 value=await body(request,response)
 if set(value)!={'site_code','name','email'} or any(not isinstance(v,str) for v in value.values()):raise HTTPException(422,'현장·이름·이메일을 입력해 주세요.')
 code=value['site_code'];name=value['name'].strip();email=value['email'].strip()
 if code not in s.SITES or not name or len(name)>100 or len(email)>254 or not re.fullmatch(r'[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+',email):raise HTTPException(422,'현장·이름·이메일을 확인해 주세요.')
 now=int(time.time())
 exists=db.execute(text('SELECT id FROM site_setup_reset_requests WHERE site_code=:code AND name=:name AND email=:email AND created_at>:recent AND resolved_at IS NULL'),{'code':code,'name':name,'email':email,'recent':now-86400}).first()
 if not exists:
  db.execute(text('INSERT INTO site_setup_reset_requests (site_code,name,email,created_at) VALUES (:code,:name,:email,:now)'),{'code':code,'name':name,'email':email,'now':now});db.commit()
 return {'message':'관리자에게 요청을 접수했습니다. 본인 확인 후 새 링크를 안내받으세요.'}
