from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import text
from app.core.auth import DbDep, get_current_user
from app.core.datetime_utils import utc_now
from app.modules.government_contact.models import GovernmentContactMessage
from app.modules.sites.models import Site
from app.modules.users.models import User
from .routes import router,body,require_profile
from . import service as s

def actor(db,user,site_id=None):
 if s.owner(user):
  site=db.get(Site,site_id) if site_id else None;side='HQ'
 else:
  require_profile(db,user)
  if site_id is not None and site_id!=user.site_id:raise HTTPException(403,'다른 현장에 접근할 수 없습니다.')
  site=db.get(Site,user.site_id);side='SITE'
 if not site or site.site_code not in s.SITES:raise HTTPException(403,'대상 현장을 확인해 주세요.')
 return site,side

def thread(db,user,ident):
 row=db.execute(text('SELECT * FROM site_setup_threads WHERE id=:id'),{'id':ident}).mappings().first()
 if not row:raise HTTPException(404,'게시글을 찾을 수 없습니다.')
 site,side=actor(db,user,row['site_id']);return row,site,side

def add(db,user,site,side,content,title=None,thread_id=None):
 m=GovernmentContactMessage(site_id=site.id,sender_user_id=user.id,sender_side=side,body=content)
 db.add(m);db.flush()
 if thread_id is None:
  thread_id=m.id;db.execute(text('INSERT INTO site_setup_threads (id,site_id,title) VALUES (:id,:site,:title)'),{'id':thread_id,'site':site.id,'title':title})
 db.execute(text('INSERT INTO site_setup_thread_messages (message_id,thread_id) VALUES (:id,:thread)'),{'id':m.id,'thread':thread_id})
 db.commit();return {'id':m.id,'thread_id':thread_id}

@router.get('/threads')
def threads(response:Response,db:DbDep,user=Depends(get_current_user),site_id:int|None=None):
 site,side=actor(db,user,site_id);response.headers['Cache-Control']='no-store'
 rows=db.execute(text('''SELECT t.id,t.title,MAX(m.id) AS latest_id,COUNT(m.id) AS message_count,
 SUM(CASE WHEN m.sender_side!=:side AND m.read_at IS NULL THEN 1 ELSE 0 END) AS unread_count
 FROM site_setup_threads t JOIN site_setup_thread_messages x ON x.thread_id=t.id
 JOIN government_contact_messages m ON m.id=x.message_id WHERE t.site_id=:site
 GROUP BY t.id,t.title ORDER BY latest_id DESC LIMIT 500'''),{'side':side,'site':site.id}).mappings()
 return {'site_name':site.site_name,'site_id':site.id,'side':side,'items':[dict(r) for r in rows]}

@router.post('/threads',status_code=201)
async def create(request:Request,response:Response,db:DbDep,user=Depends(get_current_user)):
 p=await body(request,response)
 if set(p)-{'title','body','site_id'} or not isinstance(p.get('title'),str) or not isinstance(p.get('body'),str):raise HTTPException(422,'제목과 내용을 입력해 주세요.')
 title=p['title'].strip();content=p['body'].strip()
 if not title or len(title)>160 or not content or len(content)>4000:raise HTTPException(422,'제목은 160자, 내용은 4000자 이내로 입력해 주세요.')
 site,side=actor(db,user,p.get('site_id'));return add(db,user,site,side,content,title=title)

@router.get('/threads/{ident}')
def messages(ident:int,response:Response,db:DbDep,user=Depends(get_current_user)):
 row,site,side=thread(db,user,ident);response.headers['Cache-Control']='no-store'
 ids=[r[0] for r in db.execute(text('SELECT message_id FROM site_setup_thread_messages WHERE thread_id=:id ORDER BY message_id'),{'id':ident})]
 rows=db.query(GovernmentContactMessage,User).join(User,User.id==GovernmentContactMessage.sender_user_id).filter(GovernmentContactMessage.id.in_(ids),GovernmentContactMessage.site_id==site.id).order_by(GovernmentContactMessage.id).limit(2000).all()
 return {'id':ident,'title':row['title'],'site_name':site.site_name,'site_id':site.id,'side':side,'items':[{'id':m.id,'side':m.sender_side,'sender':u.name,'body':m.body,'created_at':m.created_at.isoformat(),'read_at':m.read_at.isoformat() if m.read_at else None} for m,u in rows]}

@router.post('/threads/{ident}/reply',status_code=201)
async def reply(ident:int,request:Request,response:Response,db:DbDep,user=Depends(get_current_user)):
 p=await body(request,response)
 if set(p)!={'body'} or not isinstance(p['body'],str) or not p['body'].strip() or len(p['body'])>4000:raise HTTPException(422,'답글은 4000자 이내로 입력해 주세요.')
 _,site,side=thread(db,user,ident);return add(db,user,site,side,p['body'].strip(),thread_id=ident)

@router.post('/threads/{ident}/read')
async def read(ident:int,request:Request,response:Response,db:DbDep,user=Depends(get_current_user)):
 p=await body(request,response)
 if set(p)!={'through_id'} or not isinstance(p['through_id'],int) or p['through_id']<1:raise HTTPException(422,'확인한 메시지를 지정해 주세요.')
 _,site,side=thread(db,user,ident)
 ids=[r[0] for r in db.execute(text('SELECT message_id FROM site_setup_thread_messages WHERE thread_id=:id AND message_id<=:through'),{'id':ident,'through':p['through_id']})]
 count=db.query(GovernmentContactMessage).filter(GovernmentContactMessage.id.in_(ids),GovernmentContactMessage.site_id==site.id,GovernmentContactMessage.sender_side!=side,GovernmentContactMessage.read_at.is_(None)).update({'read_at':utc_now()},synchronize_session=False)
 db.commit();return {'read_count':count}

@router.get('/owner/updates')
def updates(response:Response,db:DbDep,user=Depends(get_current_user)):
 s.require_owner(user);response.headers['Cache-Control']='no-store'
 rows=db.execute(text('''SELECT t.id AS thread_id,t.title,t.site_id,s.site_name,COUNT(m.id) AS unread_count,MAX(m.id) AS latest_id
 FROM site_setup_threads t JOIN sites s ON s.id=t.site_id JOIN site_setup_thread_messages x ON x.thread_id=t.id
 JOIN government_contact_messages m ON m.id=x.message_id
 WHERE m.sender_side='SITE' AND m.read_at IS NULL GROUP BY t.id,t.title,t.site_id,s.site_name
 ORDER BY latest_id DESC''')).mappings().all()
 items=[dict(r) for r in rows]
 return {'count':sum(r['unread_count'] for r in items),'items':items,'version':s.VERSION}
