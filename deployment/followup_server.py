import sys,os,json,hashlib,sqlite3,shutil,subprocess,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).parent; RELEASE=R/'release'; LIVE=Path('/srv/besma/backend'); DB=Path('/srv/besma/database/besma.db'); OUT=Path('/srv/besma/ops_snapshots/government-matrix-20261008')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def protected():
    with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as c:
        return {t:{'count':len(rows),'sha256':hashlib.sha256(repr(rows).encode()).hexdigest()} for t in ('users','sites','documents','document_instances','document_upload_histories','document_review_histories','functional_eval_assessments','worker_attendances','government_contact_messages') if (rows:=c.execute('SELECT * FROM '+t+' ORDER BY id').fetchall()) is not None}
mode=sys.argv[1]
if mode=='test':
    import operations
    contact_root=R/'regression/storage/collection-monitor';contact_root.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'site-contacts-20261008.json',contact_root/'site-contacts-20261008.json')
    operations.test(RELEASE,R/'regression')
    os.environ['SQLITE_PATH']=str(R/'regression/test.sqlite3')
    from app.modules.collection_monitor.core import scoped_overview,readonly
    from app.modules.document_explorer.government_access import is_government_site_record
    from types import SimpleNamespace
    p=scoped_overview(R/'regression/test.sqlite3',R/'regression/storage/collection-monitor','2026-10')
    assert len(p['sites'])==6
    assert all('김포고촌' not in s['site_name'] for s in p['sites'])
    assert all(len(s['cells'])==7 and all(c['periods'] for c in s['cells']) for s in p['sites'])
    other=scoped_overview(R/'regression/test.sqlite3',R/'regression/storage/collection-monitor','2026-10','other')
    moved=[s for s in other['sites'] if s['site_code'] in {'26004','26024'}]
    assert len(moved)==2 and all(s['team']=='5팀' and s['channel']=='NAVERWORKS' for s in moved)
    assert all(not is_government_site_record(SimpleNamespace(site_code=code,contract_type='관급',site_name='김포고촌')) for code in ('26004','26024'))
    # Rejected/submitted/approved states preserve their own period and instance link.
    with readonly(R/'regression/test.sqlite3') as c:
        for s in p['sites']:
            row=c.execute('SELECT site_manager,manager_name,project_manager,phone_number FROM sites WHERE id=?',(s['id'],)).fetchone()
            expected_contact=json.loads((R/'site-contacts-20261008.json').read_text(encoding='utf8'))['sites'][s['site_code']]
            assert s['contact_phone']==expected_contact['contact_phone'] and s['contact_name']==expected_contact['contact_name']
            for cell in s['cells']:
                assert len(cell['periods'])==cell['expected']
                for period in cell['periods']:
                    if period['instance_id']:
                        instance=c.execute('SELECT site_id,document_type_code FROM document_instances WHERE id=?',(period['instance_id'],)).fetchone()
                        assert instance['site_id']==s['id'] and instance['document_type_code']==cell['code']
    clone=sqlite3.connect(R/'regression/test.sqlite3');fixture=clone.execute("SELECT d.id,d.instance_id,d.site_id,d.current_status,i.workflow_status,i.document_type_code FROM documents d JOIN document_instances i ON i.id=d.instance_id WHERE d.file_path IS NOT NULL AND i.document_type_code='GOV_RISK_MONTHLY' ORDER BY d.id DESC LIMIT 1").fetchone();assert fixture
    for status,received in [('APPROVED',1),('REJECTED',0),('SUBMITTED',1)]:
        clone.execute('UPDATE documents SET current_status=? WHERE id=?',(status,fixture[0]));clone.execute('UPDATE document_instances SET workflow_status=? WHERE id=?',(status,fixture[1]));clone.commit()
        changed=scoped_overview(R/'regression/test.sqlite3',R/'regression/storage/collection-monitor','2026-10')
        cell=next(c for s in changed['sites'] if s['id']==fixture[2] for c in s['cells'] if c['code']==fixture[5])
        assert cell['periods'][0]['status']==status and cell['periods'][0]['instance_id']==fixture[1] and cell['received']==received
    clone.execute('UPDATE documents SET current_status=? WHERE id=?',(fixture[3],fixture[0]));clone.execute('UPDATE document_instances SET workflow_status=? WHERE id=?',(fixture[4],fixture[1]));clone.commit();clone.close()
    result={'government_sites':6,'priority_documents':7,'team5_sites_moved':2,'other_active_sites':len(other['sites']),'period_status_links':True,'approved_rejected_submitted_periods':True,'contact_fields_match_readonly_source':True,'isolated_existing_flow_regression':True}
    (R/'regression/followup-regression.json').write_text(json.dumps(result),encoding='utf8');print(json.dumps(result))
elif mode=='deploy':
    assert os.geteuid()==0
    plan=json.loads((R/'followup-manifest.json').read_text());assert (R/'regression/followup-regression.json').exists()
    for row in plan['files']:
        assert sha(LIVE/row['path'])==row['before_sha256'],('SOURCE_CHANGED',row['path'])
        assert sha(RELEASE/'backend'/row['path'])==row['sha256']
    import pwd,grp
    uid=pwd.getpwnam('besma').pw_uid;gid=grp.getgrnam('besma').gr_gid
    OUT.mkdir(mode=0o750);os.chown(OUT,uid,gid)
    before=protected();(OUT/'protected-before.json').write_text(json.dumps(before),encoding='utf8')
    src=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);dst=sqlite3.connect(OUT/'database-before.sqlite3');src.backup(dst);src.close();dst.close();os.chown(OUT/'database-before.sqlite3',uid,gid);os.chmod(OUT/'database-before.sqlite3',0o640)
    for row in plan['files']:
        backup=OUT/'before'/row['path'];backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(LIVE/row['path'],backup)
    contact_target=Path('/srv/besma/storage/collection-monitor/site-contacts-20261008.json')
    assert not contact_target.exists(), 'CONTACT_SOURCE_EXISTS'
    shutil.copy2(R/'site-contacts-20261008.json',contact_target);os.chown(contact_target,uid,gid);os.chmod(contact_target,0o640)
    try:
        for row in plan['files']:
            path=LIVE/row['path'];tmp=path.with_name(path.name+'.matrix-release');shutil.copy2(RELEASE/'backend'/row['path'],tmp);os.chown(tmp,0,gid);os.chmod(tmp,0o640);os.replace(tmp,path)
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True)
        for attempt in range(15):
            try:health=json.loads(urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=4).read());break
            except Exception:
                if attempt==14:raise
                time.sleep(1)
        assert before==protected()
        receipt={**plan,'deployed_at':datetime.now(timezone.utc).isoformat(),'health':health,'protected_data_unchanged':True}
        (OUT/'deployment.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
        shutil.copy2(R/'regression/followup-regression.json',OUT/'regression.json')
        for p in OUT.glob('*.json'):os.chown(p,uid,gid);os.chmod(p,0o640)
        print(json.dumps({'deployed_files':len(plan['files']),'health':health,'protected_data_unchanged':True}))
    except Exception:
        for row in plan['files']:shutil.copy2(OUT/'before'/row['path'],LIVE/row['path'])
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True);raise
elif mode=='verify':
    os.umask(0o027);sys.path.insert(0,str(LIVE));os.chdir(LIVE)
    from app.config.settings import settings
    from app.core.auth import get_current_user,get_current_user_with_bypass
    from app.core.database import SessionLocal
    from app.modules.users.models import User
    from app.main import create_app
    from fastapi.testclient import TestClient
    session=SessionLocal();current={'user':session.query(User).filter(User.role=='HQ_SAFE').first()};app=create_app();app.dependency_overrides[get_current_user]=lambda:current['user'];app.dependency_overrides[get_current_user_with_bypass]=lambda:current['user'];client=TestClient(app)
    p=client.get('/collection-monitor/overview',params={'month':'2026-10'});assert p.status_code==200;p=p.json();assert len(p['sites'])==6 and len(p['documents'])==7 and all('김포고촌' not in s['site_name'] for s in p['sites'])
    other=client.get('/collection-monitor/overview',params={'month':'2026-10','scope':'other'}).json();assert len([s for s in other['sites'] if s['site_code'] in ('26004','26024') and s['team']=='5팀'])==2
    contacts=client.get('/government-contact/sites').json()['items'];assert len(contacts)==6
    report=client.get('/collection-monitor/report.xlsx',params={'month':'2026-10'});assert report.status_code==200
    plan=client.get('/collection-monitor/nas-export',params={'month':'2026-10'});assert plan.status_code==200
    for s in p['sites']:assert all(len(c['periods'])==c['expected'] for c in s['cells'])
    current['user']=session.query(User).filter(User.role=='HQ_OTHER').first();assert client.get('/collection-monitor/report.xlsx',params={'month':'2026-10'}).status_code==403
    current['user']=session.query(User).filter(User.role=='SITE',User.site_id==74).first();assert client.get('/collection-monitor/overview',params={'month':'2026-10'}).status_code==403;assert client.get('/government-contact/access').json()['allowed'];assert client.get('/government-contact/messages',params={'site_id':69}).status_code==403
    assert protected()==json.loads((OUT/'protected-before.json').read_text())
    receipt=json.loads((OUT/'deployment.json').read_text());assert all(sha(LIVE/r['path'])==r['sha256'] for r in receipt['files'])
    result={'version':p['version'],'government_active_sites':6,'other_active_sites':len(other['sites']),'team5_sites_moved':2,'priority_documents':7,'period_status_links':True,'contact_names_registered':sum(bool(s['contact_name']) for s in p['sites']),'contact_phones_registered':sum(bool(s['contact_phone']) for s in p['sites']),'nas_export_files':len(plan.json()['items']),'protected_data_unchanged':True,'permissions_verified':True,'commit':receipt['commit'],'verification':'read-only internal application with existing users and explicit authentication dependency overrides; real password public login not performed'}
    for name,payload in [('verification.json',result),('overview.json',p),('other-overview.json',other)]: (OUT/name).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    session.close();print(json.dumps(result))
else:raise ValueError(mode)

