from typing import Annotated
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,Field,ConfigDict
from app.core.auth import get_current_user
from app.modules.users.models import User
from .store import Store,CATEGORIES

router=APIRouter(prefix='/address-book',tags=['address-book'])
CurrentUser=Annotated[User,Depends(get_current_user)]
store=Store('/srv/besma/address-book/contacts.sqlite3')
READ={'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','HQ_OTHER','SITE','SITE_FUNCTIONAL_EVAL','FUNCTIONAL_EVAL_VIEWER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE'}
WRITE={'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','SITE','SITE_FUNCTIONAL_EVAL'}
def role(u):return getattr(u.role,'value',u.role)
def allowed(u,write=False):
 if not u.is_active or role(u)not in(WRITE if write else READ):raise HTTPException(403,'주소록 권한이 없습니다.')
def actor(u):return dict(id=u.id,login=u.login_id,name=u.name)
class Body(BaseModel):
 model_config=ConfigDict(extra='forbid')
 data:dict[str,str]
 reason:str=Field(min_length=1,max_length=300)
 revision:int|None=Field(default=None,ge=1)
 active:bool=True
def call(fn,*args,**kwargs):
 try:return fn(*args,**kwargs)
 except ValueError as e:raise HTTPException(422,str(e))
 except RuntimeError as e:raise HTTPException(409,str(e))
 except KeyError:raise HTTPException(404,'연락처가 없습니다.')
@router.get('/capabilities')
def capabilities(u:CurrentUser):
 allowed(u);return dict(can_read=True,can_edit=role(u)in WRITE,categories=CATEGORIES,actor_name=u.name)
@router.get('/contacts')
def contacts(u:CurrentUser,q:str=Query('',max_length=160),category:str=Query('',max_length=60),region:str=Query('',max_length=120),include_inactive:bool=False,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
 allowed(u);return store.listing(q,category,region,include_inactive,offset,limit)
@router.post('/contacts',status_code=201)
def create(b:Body,u:CurrentUser):
 allowed(u,True)
 if b.revision is not None:raise HTTPException(422,'새 연락처에는 버전을 지정할 수 없습니다.')
 return call(store.write,b.data,actor(u),b.reason,active=b.active)
@router.put('/contacts/{id}')
def update(id:str,b:Body,u:CurrentUser):
 allowed(u,True)
 if b.revision is None:raise HTTPException(422,'다시 조회한 뒤 수정해 주세요.')
 return call(store.write,b.data,actor(u),b.reason,id=id,revision=b.revision,active=b.active)
@router.get('/contacts/{id}/history')
def history(id:str,u:CurrentUser,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
 allowed(u);return call(store.history,id,offset,limit)
