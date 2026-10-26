"""Run with the production Python environment against an isolated in-memory DB only."""
import importlib.util,json,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
sys.path.insert(0,'/srv/besma/backend')
from app.core.auth import get_current_user,get_db
from app.modules import site_directory

R=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('workspace_candidate',R/'workspace.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.DATA=R/'workspace-data.json'
engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
with engine.begin() as c:
 c.execute(text('CREATE TABLE users(id INTEGER PRIMARY KEY)'));c.execute(text('INSERT INTO users(id) VALUES(1),(2),(3)'))
 site_directory.migrate(c);m.migrate(c)
 c.execute(text('CREATE TABLE functional_eval_periods(id INTEGER PRIMARY KEY,title TEXT,deadline_date TEXT,is_active INTEGER)'))
 c.execute(text("INSERT INTO functional_eval_periods VALUES(1,'기능인인정제','2026-06-30',1)"))
 c.execute(text('CREATE TABLE functional_eval_workers(id INTEGER PRIMARY KEY,period_id INTEGER)'))
 c.execute(text('CREATE TABLE functional_eval_assessments(worker_id INTEGER,eval_type TEXT,grade_code TEXT)'))
Session=sessionmaker(bind=engine);db=Session()
sample=lambda code,name:{'code':code,'name':name,'address':'서울','latitude':None,'longitude':None,'contacts':[],'details':[{'key':'contractor','value':'포스코이앤씨'}]}
site_directory.catalog=lambda db:({},[sample('1','[4.롯데건설] 현장'),sample('2','[1.포스코] 현장'),sample('3','[6.삼성] 현장')])
actor=SimpleNamespace(id=1,name='김지모',role='HQ_SAFE',ui_type='HQ_SAFE',is_active=True)
app=FastAPI();app.include_router(m.router);app.dependency_overrides[get_current_user]=lambda:actor;app.dependency_overrides[get_db]=lambda:db
client=TestClient(app);checks=[]
r=client.get('/workspace/bootstrap');assert r.status_code==200 and len(r.json()['menus'])==8 and r.headers['cache-control']=='private, no-store';checks.append('HQ access; eight menus; no-store')
assert client.get('/workspace/functional-overview').json()['period']['deadline_date']=='2026-06-30';checks.append('existing evaluation deadline remains unchanged')
for role,ui in [('SITE','SITE'),('SITE_FUNCTIONAL_EVAL','SITE'),('WORKER','WORKER')]:
 actor.role=role;actor.ui_type=ui
 for endpoint in ['bootstrap','duties','risks','cases','contractors','sites','functional-overview','forms','government-sites','contractors/1/pages/1']:
  assert client.get('/workspace/'+endpoint).status_code==403,(role,endpoint)
checks.append('SITE/worker cannot access any workspace datasets')
actor.role='ACCIDENT_ADMIN';actor.ui_type='HQ_SAFE';actor.name='정상익';assert client.get('/workspace/bootstrap').status_code==200;checks.append('owner account included')
actor.login_id='hq01';assert all(x['favorite'] for x in client.get('/workspace/sites').json()['items']);actor.login_id='qa-only';checks.append('existing owner safety favorites')
for role in sorted(m.HQ_ROLES):
 actor.role=role
 assert client.get('/workspace/bootstrap').status_code==200,role
checks.append('all existing HQ roles included')
actor.role='HQ_OTHER';actor.ui_type='HQ_OTHER';assert client.get('/workspace/duties').status_code==200;assert not any(x['favorite'] for x in client.get('/workspace/sites').json()['items']);checks.append('HQ_OTHER read access without assigned safety favorites')
actor.role='HQ_SAFE';actor.ui_type='HQ_SAFE';actor.name='김지모'
rows=client.get('/workspace/sites').json()['items'];assert [s['code'] for s in rows if s['favorite']]==['1'];checks.append('verified team assignment default favorites')
assert client.put('/workspace/sites/2/favorite',json={'favorite':True,'user_id':2}).status_code==422
assert client.put('/workspace/sites/2/favorite',json={'favorite':'true'}).status_code==422
assert client.put('/workspace/sites/missing/favorite',json={'favorite':True}).status_code==404
assert client.put('/workspace/sites/2/favorite',json={'favorite':True}).status_code==200
assert client.put('/workspace/sites/1/favorite',json={'favorite':False}).status_code==200
assert [s['code'] for s in client.get('/workspace/sites').json()['items'] if s['favorite']]==['2']
actor.id=2;actor.name='文상희';assert db.execute(text('select count(*) from workspace_site_preferences where user_id=2')).scalar()==0
actor.name='문상희';assert [s['code'] for s in client.get('/workspace/sites').json()['items'] if s['favorite']]==['2','3'];checks.append('favorite strict validation, unstar override, account isolation')
actor.is_active=False;assert client.get('/workspace/bootstrap').status_code==403;actor.is_active=True
r=client.get('/workspace/risks?q=감전&limit=5');assert r.status_code==200 and len(r.json()['items'])<=5 and all('감전' in x['work']+x['process']+x['risk']+x['measure'] for x in r.json()['items']);assert client.get('/workspace/risks?limit=10000').status_code==422;checks.append('risk search; pagination bound')
cases=client.get('/workspace/cases').json()['items'];assert len(cases)==43 and all('사고ID' not in x and 'name' not in x for x in cases);checks.append('43 confirmed anonymous accident cases')
policies=client.get('/workspace/contractors').json();assert len(policies['items'])==61;assert sum(x['points'] for x in policies['posco_criteria'])==40;checks.append('contractor catalog and POSCO point reconciliation')
assert client.get('/workspace/contractors/9999/pages/1').status_code==404;checks.append('invalid source page rejected')
from app.modules.document_explorer import routes as explorer
original_scan=explorer._scan_document_file_entries
explorer._scan_document_file_entries=lambda:[(SimpleNamespace(name='업무양식',category='general',relative_path='base/양식/업무양식.xlsx',modified_at='2026-10-01'),None),(SimpleNamespace(name='비공개 현장자료',category='field',relative_path='field/private.pdf',modified_at='2026-10-01'),None)]
forms=client.get('/workspace/forms').json();assert len(forms['items'])==1 and forms['items'][0]['name']=='업무양식' and not forms['drive_latest_verified'];assert client.get('/workspace/forms?q=없는양식').json()['items']==[]
explorer._scan_document_file_entries=original_scan
assert client.get('/workspace/forms').status_code==200;checks.append('registered form catalog works; field records excluded; latest Drive not claimed')
from app.modules.sites.models import Site
from app.modules.documents import active_site_scope
Site.__table__.create(engine)
from datetime import date,timedelta
db.add_all([Site(site_code='QA-GOV-A',site_name='관급 활성 현장',contract_type='관급',end_date=date.today()+timedelta(days=30)),Site(site_code='QA-GOV-C',site_name='관급 준공 현장',contract_type='관급',status='COMPLETED'),Site(site_code='QA-PRIVATE',site_name='민간 현장',contract_type='민간')]);db.commit()
active_site_scope.active_site_codes=lambda:frozenset({'QA-GOV-A','QA-GOV-C','QA-PRIVATE'})
assert [x['code'] for x in client.get('/workspace/government-sites').json()['items']]==['QA-GOV-A'];checks.append('government catalog excludes completed and private sites')
rows=client.get('/workspace/duties').json()['items'];assert all(x.get('temporary') for x in rows if x['department']=='안전보건실' or x['kind']=='emergency');assert not any(x.get('temporary') for x in rows if x['department']=='재무회계팀' and x['kind']=='main');checks.append('reference duties temporary; HRD accounting tasks preserved')
print(json.dumps({'passed':True,'checks':checks},ensure_ascii=False));db.close()
