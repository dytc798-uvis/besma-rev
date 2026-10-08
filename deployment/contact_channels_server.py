import sys,os,json,sqlite3,hashlib,shutil,subprocess,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).parent;LIVE=Path('/srv/besma/backend');DB=Path('/srv/besma/database/besma.db');OUT=Path('/srv/besma/ops_snapshots/government-contact-channels-20261008');MODE=sys.argv[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def backup(src,dest):
    with sqlite3.connect(src.as_uri()+'?mode=ro',uri=True) as a,sqlite3.connect(dest) as b:a.backup(b)
    dest.chmod(0o640)
def protected():
    with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as c:
        result={}
        for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='government_contact_test_messages'").fetchall():
            cols=[row[1] for row in c.execute('PRAGMA table_info('+name+')') if not(name=='government_contact_messages' and row[1]=='document_code')]
            rows=c.execute('SELECT '+','.join('"'+col+'"' for col in cols)+' FROM "'+name+'" ORDER BY 1').fetchall()
            result[name]={'count':len(rows),'sha256':hashlib.sha256(repr(rows).encode()).hexdigest()}
        return result
def migrate(path):
    with sqlite3.connect(path) as c:
        if 'document_code' not in {r[1] for r in c.execute('PRAGMA table_info(government_contact_messages)')}:c.execute('ALTER TABLE government_contact_messages ADD COLUMN document_code VARCHAR(64)')
    from app.core.database import engine
    from app.modules.users.models import User
    from app.modules.government_contact.models import GovernmentContactTestMessage
    GovernmentContactTestMessage.__table__.create(engine,checkfirst=True)
def init(source,test=False):
    if test:
        work=R/'regression';work.mkdir(exist_ok=True);backup(DB,work/'test.sqlite3')
        os.environ.update(SQLITE_PATH=str(work/'test.sqlite3'),STORAGE_ROOT=str(work/'storage'),DOCUMENT_EXPLORER_BASE_DIR=str(work/'forms'))
    else:os.environ['SQLITE_PATH']=str(DB)
    sys.path.insert(0,str(source));os.chdir(source)
def client():
    from app.core.database import SessionLocal
    from app.core.auth import get_current_user,get_current_user_with_bypass
    from app.modules.users.models import User
    from app.modules.government_contact.routes import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    db=SessionLocal();actor={'value':db.query(User).filter(User.role=='HQ_SAFE').first()};app=FastAPI();app.include_router(router);app.dependency_overrides[get_current_user]=lambda:actor['value'];app.dependency_overrides[get_current_user_with_bypass]=lambda:actor['value'];return TestClient(app),db,actor
if MODE=='test':
    init(R/'backend',True)
    from app.config.settings import settings
    assert Path(settings.sqlite_path)==R/'regression/test.sqlite3';migrate(settings.sqlite_path)
    api,db,actor=client()
    from app.modules.users.models import User
    hq=actor['value'];site=db.query(User).filter(User.role=='SITE',User.site_id==74).first();other=db.query(User).filter(User.role=='HQ_OTHER').first();test1=db.query(User).filter(User.login_id=='test01').one();test2=db.query(User).filter(User.login_id=='test02').one();assert all((hq,site,other))
    sites=api.get('/government-contact/sites').json()['items'];assert len(sites)==6
    subjects=api.get('/government-contact/subjects?site_id=74').json()['items'];assert subjects[0]['code'] is None and any(s['code']=='GOV_SAFETY_COST_MONTHLY' for s in subjects)
    first=api.post('/government-contact/messages',json={'site_id':74,'body':'일반 문의 검증'});assert first.status_code==201
    second=api.post('/government-contact/messages',json={'site_id':74,'body':'관리비 문의 검증','document_code':'GOV_SAFETY_COST_MONTHLY'});assert second.status_code==201
    assert api.post('/government-contact/messages',json={'site_id':74,'body':'invalid','document_code':'SECRET_INTERNAL'}).status_code==422
    actor['value']=site
    assert len(api.get('/government-contact/messages?general_only=true').json()['items'])==1
    assert len(api.get('/government-contact/messages?document_code=GOV_SAFETY_COST_MONTHLY').json()['items'])==1
    assert api.post('/government-contact/read',params={'through_id':second.json()['id'],'general_only':True}).json()['read_count']==1
    assert api.get('/government-contact/unread').json()['count']==1
    assert api.post('/government-contact/messages',json={'body':'문서 없이 답변'}).status_code==201
    assert api.post('/government-contact/messages',json={'site_id':sites[-1]['site_id'],'body':'cross site'}).status_code==403
    assert api.get('/government-contact/messages?site_id=-1').status_code==403
    actor['value']=test1;assert api.get('/government-contact/access').json()['test_mode']
    assert api.get('/government-contact/messages?site_id=74').status_code in (403,404)
    tests=api.get('/government-contact/test-sites').json()['items'];assert len(tests)==3
    for room in tests:assert api.post('/government-contact/messages',json={'site_id':room['site_id'],'body':'test 현장 문의'}).status_code==201
    actor['value']=test2;assert len(api.get('/government-contact/messages?site_id=-2&general_only=true').json()['items'])==1
    actor['value']=hq;assert len(api.get('/government-contact/messages?site_id=-1').json()['items'])==1
    assert api.post('/government-contact/messages',json={'site_id':-1,'body':'test 본사 답변','document_code':'GOV_RISK_MONTHLY'}).status_code==201
    actor['value']=test1;assert api.get('/government-contact/unread').json()['count']==1
    assert len(api.get('/government-contact/messages?site_id=-1&document_code=GOV_RISK_MONTHLY').json()['items'])==1
    assert api.post('/government-contact/read',params={'site_id':-1,'through_id':9999,'document_code':'GOV_RISK_MONTHLY'}).json()['read_count']==1
    actor['value']=other;assert not api.get('/government-contact/access').json()['allowed'];assert api.get('/government-contact/access').json()['legacy_contact_hidden'];assert api.get('/government-contact/test-sites').status_code==403
    pilot=db.query(User).filter(User.role=='SITE',User.site_id.in_([2,8])).first()
    if pilot:actor['value']=pilot;assert api.get('/government-contact/access').json()['legacy_contact_hidden'];assert not api.get('/government-contact/access').json()['allowed']
    actor['value']=hq;assert len(api.get('/government-contact/messages?site_id=74').json()['items'])==3
    result={'passed':True,'government_sites':6,'general_without_document':True,'document_categories':True,'bidirectional':True,'scoped_read_receipts':True,'site_isolation':True,'invalid_document_denied':True,'test_rooms':3,'existing_test_accounts':2,'test_real_separation':True,'readonly_role_unchanged':True,'c18_hidden':True}
    for name,value in [('result.json',result),('sites.json',{'items':sites}),('subjects.json',{'items':subjects}),('test-accounts.json',{'items':tests})]:(R/'regression'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result));db.close()
elif MODE=='migrate':
    init(R/'backend');from app.config.settings import settings
    assert Path(settings.sqlite_path)==DB;migrate(DB)
elif MODE=='deploy':
    assert os.geteuid()==0 and (R/'regression/result.json').exists();plan=json.loads((R/'manifest.json').read_text())
    for item in plan['files']:assert sha(LIVE/item['path'])==item['before_sha256'];assert sha(R/'backend'/item['path'])==item['sha256']
    assert not (OUT/'deployment.json').exists();OUT.mkdir(mode=0o750,exist_ok=True)
    import pwd,grp
    uid=pwd.getpwnam('besma').pw_uid;gid=grp.getgrnam('besma').gr_gid;os.chown(OUT,uid,gid)
    before=protected();backup(DB,OUT/'database-before.sqlite3')
    for item in plan['files']:
        target=OUT/'before'/item['path'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(LIVE/item['path'],target)
    subprocess.run(['sudo','-n','-u','besma','/srv/besma/backend/.venv/bin/python','-B',str(R/'server.py'),'migrate'],check=True)
    try:
        for item in plan['files']:
            dest=LIVE/item['path'];tmp=dest.with_name(dest.name+'.contact-release');shutil.copy2(R/'backend'/item['path'],tmp);os.chown(tmp,0,gid);tmp.chmod(0o640);os.replace(tmp,dest)
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True)
        for n in range(15):
            try:health=json.loads(urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3).read());break
            except Exception:
                if n==14:raise
                time.sleep(1)
        assert before==protected()
        receipt={**plan,'deployed_at':datetime.now(timezone.utc).isoformat(),'health':health,'protected_data_unchanged':True}
        for name,value in [('deployment.json',receipt),('protected-before.json',before)]:(OUT/name).write_text(json.dumps(value,indent=2),encoding='utf8');os.chown(OUT/name,uid,gid);(OUT/name).chmod(0o640)
        shutil.copy2(R/'regression/result.json',OUT/'regression.json');print(json.dumps({'health':health,'protected_data_unchanged':True,'files':len(plan['files'])}))
    except Exception:
        for item in plan['files']:shutil.copy2(OUT/'before'/item['path'],LIVE/item['path'])
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True);raise
elif MODE=='verify':
    init(LIVE);api,db,actor=client();from app.modules.users.models import User
    assert len(api.get('/government-contact/sites').json()['items'])==6
    assert len(api.get('/government-contact/test-sites').json()['items'])==3
    assert api.get('/government-contact/subjects?site_id=74').status_code==200
    for login in ('test01','test02'):actor['value']=db.query(User).filter(User.login_id==login).one();assert api.get('/government-contact/access').json()['test_mode'];assert api.get('/government-contact/messages?site_id=74').status_code in (403,404)
    actor['value']=db.query(User).filter(User.login_id=='test03').one();assert actor['value'].role=='HQ_OTHER' and not api.get('/government-contact/access').json()['allowed']
    assert protected()==json.loads((OUT/'protected-before.json').read_text())
    receipt=json.loads((OUT/'deployment.json').read_text());assert all(sha(LIVE/i['path'])==i['sha256'] for i in receipt['files'])
    result={'government_sites':6,'test_rooms':3,'accounts_unchanged':True,'protected_data_unchanged':True,'permissions_verified':True,'commit':receipt['commit'],'no_production_test_messages_created':True}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result));db.close()
else:raise ValueError(MODE)
