"""Synthetic in-memory DB and private temp files; no production writes or weather requests."""
import importlib.util,json,sys,tempfile,hashlib,datetime as dt
from pathlib import Path
from types import SimpleNamespace as NS
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
sys.path.insert(0,'/srv/besma/backend');root=Path(sys.argv[1])
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,root/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
home=load('app.modules.workspace_home','backend/app/modules/workspace_home.py');workspace=load('candidate_workspace','backend/app/modules/workspace.py')
from app.core.auth import get_current_user,get_db
from app.modules import site_directory
from app.modules.documents import active_site_scope
engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool);db=Session(engine)
for sql in ['CREATE TABLE sites(id INTEGER,site_code TEXT,status TEXT,end_date TEXT)','CREATE TABLE notices(id INTEGER,title TEXT,created_at TEXT)','CREATE TABLE functional_eval_periods(id INTEGER,title TEXT,deadline_date TEXT,is_active INTEGER)','CREATE TABLE functional_eval_workers(id INTEGER,period_id INTEGER,rrn_hash TEXT)','CREATE TABLE functional_eval_assessments(worker_id INTEGER,eval_type TEXT,grade_code TEXT)','CREATE TABLE functional_eval_site_registry(site_code TEXT,manager_login_id TEXT)','CREATE TABLE users(login_id TEXT,is_active INTEGER,role TEXT)']:
    db.execute(text(sql))
db.execute(text("INSERT INTO sites VALUES(1,'QA1','ACTIVE',NULL),(2,'QA2','COMPLETED',NULL),(3,'QA3','ACTIVE','2020-01-01')"))
db.execute(text("INSERT INTO notices VALUES(1,'QA Notice','2026-10-26T00:00:00')"))
db.execute(text("INSERT INTO functional_eval_periods VALUES(1,'Fixed old period','2026-06-30',1)"))
hash_a='a'*64;hash_b='b'*64
db.execute(text('INSERT INTO functional_eval_workers VALUES(1,1,:hash)'),{'hash':hash_a});db.execute(text("INSERT INTO functional_eval_assessments VALUES(1,'SAFETY','S')"));db.execute(text("INSERT INTO functional_eval_site_registry VALUES('QA1','qa-manager')"));db.execute(text("INSERT INTO users VALUES('qa-manager',1,'SITE_FUNCTIONAL_EVAL')"));db.commit()
home.kst_today=lambda:dt.date(2026,10,26);tmp=Path(tempfile.mkdtemp());home.ROOT=tmp;(tmp/'daily-attendance').mkdir()
daily={'schema':1,'date':'2026-10-26','captured_at':'2026-10-26T10:00:00+09:00','source_sha256':'c'*64,'source_filename':'qa.xls','people':2,'unidentified_people':0,'sites':[{'code':'QA1','name':'QA site','people':2,'representatives':[]}],'identities':[{'rrn_hash':hash_a,'site_code':'QA1'},{'rrn_hash':hash_b,'site_code':'QA1'}]}
path=tmp/'daily-attendance/latest.json';path.write_text(json.dumps(daily))
address='서울특별시 성북구 안암로 145';location={'latitude':37.59,'longitude':127.03,'precision':'address','address_sha256':hashlib.sha256(address.encode()).hexdigest()};(tmp/'site-locations.json').write_text(json.dumps({'locations':{'QA1':location}}))
catalog=[{'code':'QA1','name':'QA site','address':address,'latitude':None,'longitude':None},{'code':'QA2','name':'Completed','address':'부산','latitude':None,'longitude':None},{'code':'QA3','name':'Expired','address':'인천','latitude':None,'longitude':None}]
site_directory.catalog=lambda db:({'aliases':{}},catalog);active_site_scope.active_site_codes=lambda:frozenset({'QA1','QA2','QA3'})
actor=NS(id=999,name='QA',login_id='qa',role='HQ_SAFE',ui_type='HQ_SAFE',is_active=True)
app=FastAPI();app.include_router(workspace.router);app.dependency_overrides[get_current_user]=lambda:actor;app.dependency_overrides[get_db]=lambda:db;client=TestClient(app)
checks=[]
before=list(db.execute(text('SELECT * FROM functional_eval_periods')))
value=client.get('/workspace/home').json();assert value['attendance']['people']==2 and len(value['sites'])==1 and value['sites'][0]['latitude']==37.59
assert 'identities' not in json.dumps(value) and 'rrn_hash' not in json.dumps(value)
assert value['notices'][0]['title']=='QA Notice';checks.append('HQ-only aggregate payload; current source; active scope; notices; no identities')
r=client.get('/workspace/functional-readiness').json();assert r['today_people']==2 and r['prior_grade_people']==1 and r['new_or_ungraded_people']==1 and r['evaluator_check_sites']==0 and not r['can_evaluate'];assert r['previous_periods'][0]['deadline_date']=='2026-06-30';checks.append('previous grade as reference only; readiness does not create period or evaluations')
from app.modules.dashboard import weather_service
weather_service.build_weather_snapshot=lambda location:{'available':True,'temperature':13,'updated_at':dt.datetime(2026,10,26,1,0),'temperature_source':'qa-only'}
weather=client.get('/workspace/site-weather/QA1');assert weather.status_code==200 and weather.json()['observed_at']=='2026-10-26T01:00:00';assert 'apparent_temperature' not in weather.json();checks.append('existing weather timestamps serialize; no heat-stress fields or new provider calls')
catalog[0]['address']='서울특별시 다른 주소';assert client.get('/workspace/home').json()['sites'][0]['latitude'] is None;catalog[0]['address']=address;checks.append('changed ERP address invalidates stored coordinates')
daily['date']='2026-10-25';path.write_text(json.dumps(daily));value=client.get('/workspace/home').json();assert value['attendance']['people'] is None and not value['attendance']['current'] and value['attendance']['last_people']==2;assert client.get('/workspace/functional-readiness').json()['today_people'] is None;checks.append('yesterday never appears as today or zero people')
for role,ui in [('SITE','SITE'),('WORKER','WORKER'),('SITE_FUNCTIONAL_EVAL','SITE')]:
    actor.role=role;actor.ui_type=ui
    for endpoint in ['home','functional-readiness','site-weather/QA1']:assert client.get('/workspace/'+endpoint).status_code==403
checks.append('field and worker accounts denied home, readiness and site weather')
assert list(db.execute(text('SELECT * FROM functional_eval_periods')))==before
print(json.dumps({'passed':True,'checks':checks}))
