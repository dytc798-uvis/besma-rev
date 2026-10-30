"""Site-specific workspace read routes. HQ routes keep their original authorization."""
from fastapi import APIRouter,Depends,HTTPException,Query
from app.core.auth import DbDep,get_current_user
from app.modules.sites.models import Site
from app.modules.workspace_site_access import require_site_identity,require_own_site,site_menus,policy_belongs_to_site

router=APIRouter(prefix='/site',tags=['site-workspace'])


def actor(db,user):
    ident=require_site_identity(user)
    return require_own_site(user,db.get(Site,ident))


def current_policy(site,item_id):
    from app.modules.workspace import contractor_catalog
    item=next((item for item in contractor_catalog()['items']if item['id']==item_id),None)
    if not item or not policy_belongs_to_site(item,site):raise HTTPException(404,'이 현장에 해당하는 안전기준을 확인해 주세요.')
    return item


@router.get('/bootstrap')
def bootstrap(db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import result
    from app.modules.document_explorer.government_access import is_government_site_record
    site=actor(db,user);government=bool(is_government_site_record(site))
    return result({'user':{'name':user.name,'role':'SITE','site_id':site.id},
        'site':{'id':site.id,'code':site.site_code,'name':site.site_name,'client':site.client_name,'contractor':site.contractor_name},
        'menus':site_menus(user,site,government),'government_document_collection':government,
        'permissions':{'work_requests':False,'hq_approval':False,'other_site_opinions':False,'worker_voice_read':True,'worker_voice_ledger':True},
        'opinion_path':'/site/google-feedback','functional_eval_path':'/site/functional-eval/roster',
        'general_feedback_ready':True,'general_feedback_path':'/site/opinions'})


@router.get('/duties')
def duties(db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import duties as existing
    actor(db,user)
    return existing(user)


@router.get('/organization-chart/{kind}')
def organization(kind:str,db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import organization_chart as existing
    actor(db,user)
    return existing(kind,user)


@router.get('/organization-chart/{kind}/people')
def organization_people(kind:str,db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import organization_chart_people as existing
    actor(db,user)
    return existing(kind,user)


@router.get('/forms')
def forms(db:DbDep,q:str=Query('',max_length=120),user=Depends(get_current_user)):
    from app.modules.workspace import result
    from app.modules.document_explorer.routes import _visible_entries
    actor(db,user);words=q.casefold().split();items=[]
    for item,_ in _visible_entries(db,user):
        if item.category=='field':continue
        if all(word in (item.name+' '+item.relative_path).casefold()for word in words):
            items.append({'name':item.name,'category':item.category,'path':item.relative_path,'modified_at':str(item.modified_at)})
    return result({'items':items,'source':'현장 열람이 허용된 양식·법령','drive_latest_verified':False,'scope':'authenticated-site'})


@router.get('/contractors')
def contractors(db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import contractor_catalog,result
    site=actor(db,user);data=contractor_catalog();items=[item for item in data['items']if policy_belongs_to_site(item,site)]
    # Existing published policy files/previews stay intact; only the visible catalog is narrowed.
    return result({'items':items,'posco_criteria':data['posco_criteria']if any(item.get('contractor')=='포스코'for item in items)else[],
        'scope':'authenticated-site','site_id':site.id,'customer_verified':bool(items)})


@router.get('/contractors/{item_id}/pages/{page}')
def contractor_page(item_id:int,page:int,db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import contractor_page as existing
    current_policy(actor(db,user),item_id)
    return existing(item_id,page,user)


@router.get('/contractors/{item_id}/pages/{page}/guide')
def contractor_guide(item_id:int,page:int,db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import contractor_page_guide as existing
    current_policy(actor(db,user),item_id)
    return existing(item_id,page,user)


from pydantic import BaseModel,ConfigDict,Field
from typing import Literal

class SiteImprovement(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    category:Literal['업무 개선','홈페이지 개선']
    content:str=Field(min_length=1,max_length=5000)

@router.get('/opinions')
def general_opinions(db:DbDep,user=Depends(get_current_user)):
    from app.modules.opinions.models import Opinion
    from app.schemas.opinions import OpinionOut
    from app.modules.workspace import result
    site=actor(db,user)
    rows=db.query(Opinion).filter(Opinion.site_id==site.id).order_by(Opinion.created_at.desc()).limit(200).all()
    return result({'site_id':site.id,'items':[OpinionOut.model_validate(row).model_dump(mode='json')for row in rows]})

@router.post('/opinions',status_code=201)
def create_general_opinion(body:SiteImprovement,db:DbDep,user=Depends(get_current_user)):
    from app.modules.opinions.routes import create_opinion
    from app.schemas.opinions import OpinionCreate,OpinionOut
    site=actor(db,user);content=body.content.strip()
    if not content:raise HTTPException(422,'의견 내용을 입력해 주세요.')
    row=create_opinion(db,user,OpinionCreate(site_id=site.id,category=body.category,content=content))
    return OpinionOut.model_validate(row).model_dump(mode='json')

@router.get('/current-site')
def current_site(db:DbDep,user=Depends(get_current_user)):
    from app.modules.workspace import result
    site=actor(db,user)
    return result({'id':site.id,'code':site.site_code,'name':site.site_name,'address':site.address,
        'description':site.description or'','client':site.client_name,'contractor':site.contractor_name})


@router.get('/risks')
def risks(db:DbDep,q:str=Query('',max_length=120),work:str=Query('',max_length=100),case:int|None=None,offset:int=Query(0,ge=0),limit:int=Query(40,ge=1,le=100),user=Depends(get_current_user)):
    from app.modules.workspace import risks as existing
    actor(db,user)
    return existing(q,work,case,offset,limit,user)

@router.get('/cases')
def cases(db:DbDep,q:str=Query('',max_length=120),user=Depends(get_current_user)):
    from app.modules.workspace import cases as existing
    actor(db,user)
    return existing(q,user)
