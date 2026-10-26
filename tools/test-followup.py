"""Production interpreter, candidate modules, synthetic in-memory records only."""
import importlib.util, sys, json
from pathlib import Path
from types import SimpleNamespace as NS
from datetime import date, timedelta
from copy import deepcopy
sys.path.insert(0, '/srv/besma/backend')
root=Path(sys.argv[1])/'backend/app'
def load(name, relative):
    spec=importlib.util.spec_from_file_location(name, root/relative)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module
access=load('app.core.government_workspace_access','core/government_workspace_access.py')
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.auth import get_current_user, get_current_user_with_bypass, get_db
from app.core.enums import Role
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.government_contact.models import GovernmentContactMessage, GovernmentContactTestMessage
gov=load('app.modules.government_contact.routes','modules/government_contact/routes.py')
collection=load('app.modules.collection_monitor.routes','modules/collection_monitor/routes.py')
from app.modules.document_explorer import routes as explorer
stats=load('app.modules.functional_eval.grade_stats_cache','modules/functional_eval/grade_stats_cache.py')
engine=create_engine('sqlite://', connect_args={'check_same_thread':False},poolclass=StaticPool)
with engine.begin() as c:c.execute(text('CREATE TABLE users(id INTEGER PRIMARY KEY, name TEXT)'))
for model in (Site,GovernmentContactMessage,GovernmentContactTestMessage):model.__table__.create(engine)
db=sessionmaker(bind=engine)()
db.add_all([Site(id=1,site_code='QA-GOV-1',site_name='QA Government 1',contract_type='관급'),Site(id=2,site_code='QA-GOV-2',site_name='QA Government 2',contract_type='관급'),Site(id=3,site_code='QA-PRIVATE',site_name='QA Private',contract_type='민간')]);db.commit()
gov.in_active_scope=lambda site,*args:site.id in {1,2}
actor=NS(id=96,login_id='안전보건-정상익',name='정상익',role=Role.HQ_SAFE,ui_type='HQ_SAFE',is_active=True,site_id=None)
app=FastAPI()
for router in (gov.router,collection.router,explorer.router):app.include_router(router)
app.dependency_overrides[get_current_user]=lambda:actor
app.dependency_overrides[get_current_user_with_bypass]=lambda:actor
app.dependency_overrides[get_db]=lambda:db
client=TestClient(app);checks=[]
assert access.can_manage_government(actor)
actor.government_preview=True;assert not access.can_manage_government(actor);actor.government_preview=False
actor.id=97;assert not access.can_manage_government(actor);actor.id=96
for uid,login,role in [(8,'hq01',Role.ACCIDENT_ADMIN),(96,'안전보건-정상익',Role.HQ_SAFE)]:
    actor.id=uid;actor.login_id=login;actor.role=role
    assert client.get('/government-contact/access').json()['can_manage_forms']
    assert collection.settings_owner(actor) is actor
checks.append('only two verified owner principals; same-name impostor and preview denied')
for role in gov.HQ_ROLES:
    actor.id=999;actor.login_id='qa';actor.name='QA';actor.role=role
    d=client.get('/government-contact/access').json();assert d['allowed'] and d['side']=='HQ' and not d['can_manage_forms']
    assert client.get('/government-contact/sites').status_code==200
    for path in ['/document-explorer/government-folders','/document-explorer/government-document-catalog','/collection-monitor/settings']:
        assert client.get(path).status_code==403,(role,path)
    assert client.put('/document-explorer/government-folders',json={'folder':'관급 공개 양식/QA','visible':True}).status_code==403
    assert client.put('/document-explorer/government-files',json={'relative_path':'관급 공개 양식/QA.pdf','visible':True}).status_code==403
    assert client.put('/collection-monitor/settings',json={'revision':0,'groups':[],'items':[]}).status_code==403
    assert client.post('/document-explorer/upload',data={'relative_path':'관급 공개 양식/QA.pdf'},files={'file':('QA.pdf',b'QA','application/pdf')}).status_code==403
checks.append('all HQ correspondence enabled; owner-only catalogs, visibility, collection settings and public-copy upload')
actor.role=Role.SITE;actor.ui_type='SITE';actor.site_id=1
assert client.get('/government-contact/access').json()['allowed']
assert gov._authorized_site(db,actor,1)[0].id==1
try:gov._authorized_site(db,actor,2);raise AssertionError('cross-site allowed')
except HTTPException as e:assert e.status_code==403
actor.site_id=3;assert not client.get('/government-contact/access').json()['allowed']
assert client.get('/collection-monitor/settings').status_code==403
checks.append('active government SITE limited to own site; private SITE denied')
class NoDB:
    def __getattr__(self,key):raise AssertionError('closed snapshot touched database: '+key)
cached={'overall':{'functional':{'graded_total':1039},'safety':{'graded_total':1037}},'by_team':[{'team_no':1}],'by_site':[{'site_code':'00057','site_name':'현장 00057','functional':{'workers_total':0}},{'site_code':'24022','site_name':'양주 옥정','functional':{'workers_total':0}},{'site_code':'24023','site_name':'제3연륙교','functional':{'workers_total':0}},{'site_code':'99999','site_name':'99999','safety':{'graded_total':1}}],'computed_at':'2026-06-30T00:00:00','grade_stats_mode':'live'}
original=deepcopy(cached);period=NS(id=1,deadline_date=date(2026,6,30),hq_grade_stats_json=cached,hq_grade_stats_computed_at=None)
for fn in (stats.get_hq_grade_stats,stats.rebuild_and_persist,stats.compute_hq_grade_stats):
    result=fn(NoDB(),period)
    assert result['overall']==original['overall'] and result['by_team']==original['by_team']
    assert [x['site_code'] for x in result['by_site']]==['24022','24023','99999']
    result['overall'].clear();assert cached==original
stats.mark_dirty(NoDB(),period);assert cached==original
period.hq_grade_stats_json=None
for fn in (stats.get_hq_grade_stats,stats.rebuild_and_persist,stats.compute_hq_grade_stats):
    try:fn(NoDB(),period);raise AssertionError('closed period recomputed')
    except HTTPException as e:assert e.status_code==409
checks.append('closed cached totals, scores, timestamp unchanged; no query/commit/recompute or current criteria; missing snapshot fails closed')
assert not stats._named_site('현장명: 21009') and stats._named_site('[2.신성건설] 양주 옥정')
assert not stats._closed_period(NS(deadline_date=date.today()+timedelta(days=30)))
checks.append('numeric empty placeholders excluded from view only; real zero sites and historic graded rows preserved')
print(json.dumps({'passed':True,'checks':checks},ensure_ascii=True))
