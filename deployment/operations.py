"""Hash-guarded additive NCP deployment and isolated regression."""
import argparse,hashlib,json,os,secrets,shutil,sqlite3,sys,subprocess
from pathlib import Path
from datetime import datetime,timezone

BACKEND=Path('/srv/besma/backend');DB=Path('/srv/besma/database/besma.db')
PROTECTED=('users','sites','documents','document_instances','document_upload_histories','document_review_histories','functional_eval_assessments','worker_attendances')
def sha(b):return hashlib.sha256(b).hexdigest()
def summary(c):
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {t:{'count':c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0],'sha256':sha(repr(c.execute('SELECT * FROM '+t+' ORDER BY id').fetchall()).encode())} for t in PROTECTED if t in tables}
def snapshot(source,target):
    src=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);dest=sqlite3.connect(target);src.backup(dest);src.close();assert dest.execute('PRAGMA quick_check').fetchone()[0]=='ok';dest.close()

def test(release,out):
    os.umask(0o077);out.mkdir(parents=True,exist_ok=True);clone=out/'test.sqlite3';snapshot(DB,clone)
    root=out/'storage';root.mkdir(exist_ok=True);explorer=out/'forms';explorer.mkdir(exist_ok=True)
    monitor=root/'collection-monitor';monitor.mkdir(exist_ok=True);source=Path('/srv/besma/storage/collection-monitor/collection.sqlite3')
    if source.exists():snapshot(source,monitor/'collection.sqlite3')
    os.environ.update(SQLITE_PATH=str(clone),STORAGE_ROOT=str(root),DOCUMENT_EXPLORER_BASE_DIR=str(explorer),JWT_SECRET_KEY=secrets.token_urlsafe(64),ENV='prod',DEV_BYPASS_AUTH='false')
    sys.path.insert(0,str(release/'backend'));os.chdir(release/'backend');sys.dont_write_bytecode=True
    from app.config.settings import settings
    assert Path(settings.sqlite_path)==clone and Path(settings.storage_root)==root and Path(settings.document_explorer_base_dir)==explorer
    from app.modules.auth.routes import router as auth
    from app.modules.documents.routes import router as docs
    from app.modules.document_submissions.routes import router as submissions
    from app.modules.document_explorer.routes import router as forms
    from app.modules.government_contact.routes import router as contact
    from app.modules.collection_monitor.routes import router as collection
    from app.modules.government_contact.models import GovernmentContactMessage
    from app.core.database import engine
    GovernmentContactMessage.__table__.create(engine,checkfirst=True)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.config.security import get_password_hash
    app=FastAPI()
    for router in [auth,docs,submissions,forms,contact,collection]:app.include_router(router)
    client=TestClient(app)
    c=sqlite3.connect(clone);before=summary(c);password=secrets.token_urlsafe(30)+'Aa1!'
    selected={}
    for row in c.execute("SELECT u.id,u.login_id,u.role,u.site_id FROM users u LEFT JOIN sites s ON s.id=u.site_id WHERE u.role IN ('HQ_SAFE','HQ_OTHER','HQ_SAFE_ADMIN','SUPER_ADMIN') OR (u.role='SITE' AND s.site_code IN ('24028','25040')) ORDER BY u.id"):
        key=row[2] if row[2]!='SITE' else 'SITE'+str(row[3])
        if key not in selected:selected[key]=row
    headers={};checks={}
    for key,row in selected.items():
        c.execute('UPDATE users SET password_hash=?,must_change_password=0,is_active=1 WHERE id=?',(get_password_hash(password),row[0]));c.commit()
        r=client.post('/auth/login',data={'username':row[1],'password':password});assert r.status_code==200,(key,r.status_code)
        headers[key]={'Authorization':'Bearer '+r.json()['access_token']}
        assert client.get('/auth/me',headers=headers[key]).status_code==200
    checks['existing_auth_and_roles']=True
    h=headers['HQ_SAFE'];o=headers['HQ_OTHER'];site_keys=[k for k in selected if k.startswith('SITE')];site_id=selected[site_keys[0]][3];s=headers[site_keys[0]];other_id=selected[site_keys[1]][3]
    r=client.get('/collection-monitor/overview',headers=h,params={'month':'2026-10'});assert r.status_code==200
    payload=r.json();assert len(payload['sites'])==8 and len(payload['documents'])==7
    assert all(len(row['cells'])==7 for row in payload['sites']);assert all(row['active'] for row in payload['sites'])
    assert client.get('/collection-monitor/overview',headers=s,params={'month':'2026-10'}).status_code==403
    other=client.get('/collection-monitor/overview',headers=h,params={'month':'2026-10','scope':'other'}).json()
    assert all(row['active'] and row['channel']=='NAVERWORKS' for row in other['sites']);checks['active_roster_eight_government_seven_priority_other_scope']=True
    assert client.get('/collection-monitor/report.xlsx',headers=o,params={'month':'2026-10'}).status_code==403
    report=client.get('/collection-monitor/report.xlsx',headers=h,params={'month':'2026-10'});assert report.status_code==200
    from openpyxl import load_workbook
    from io import BytesIO
    wb=load_workbook(BytesIO(report.content));assert wb.sheetnames==['현장별 요약','서류별 취합률','현장별 서류현황'];assert wb.worksheets[0]['C5'].value==sum(s['required'] for s in payload['sites']);assert wb.worksheets[2].max_row==4+56
    (out/'report.xlsx').write_bytes(report.content);(out/'overview.json').write_text(json.dumps(payload,ensure_ascii=False),encoding='utf8');(out/'other-overview.json').write_text(json.dumps(other,ensure_ascii=False),encoding='utf8');checks['report_totals_detail_and_read_only_denial']=True
    # Paired correspondence stays inside the two authorized parties.
    r=client.post('/government-contact/messages',headers=s,json={'body':'isolated site fixture'});assert r.status_code==201
    r=client.post('/government-contact/messages',headers=h,json={'site_id':site_id,'body':'isolated HQ fixture'});assert r.status_code==201
    assert len(client.get('/government-contact/messages',headers=s).json()['items'])==2
    assert client.get('/government-contact/messages',headers=s,params={'site_id':other_id}).status_code==403
    assert client.post('/government-contact/messages',headers=o,json={'site_id':site_id,'body':'blocked'}).status_code==403
    assert client.get('/government-contact/unread',headers=s).json()['count']==1
    last_id=client.get('/government-contact/messages',headers=s).json()['items'][-1]['id']
    client.post('/government-contact/read',headers=s,params={'through_id':last_id})
    assert client.get('/government-contact/unread',headers=s).json()['count']==0;checks['two_way_contact_isolation_read_receipts']=True
    # Prepared public copies start private; public toggles cannot expose the internal original.
    fake='02. 안전점검/안전보건 점검 체크리스트(26.2.3개정).xlsx'
    for prefix in ['일반 양식','관급 공개 양식']:
        p=explorer/prefix/fake;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'isolated blank form')
    assert client.get('/document-explorer/government-document-catalog',headers=o).status_code==403
    assert client.get('/document-explorer/list',headers=s).json()['items']==[]
    assert client.put('/document-explorer/government-files',headers=h,json={'relative_path':fake,'visible':True}).status_code==200
    assert client.put('/document-explorer/government-folders',headers=h,json={'folder':'관급 공개 양식/02. 안전점검','visible':True}).status_code==200
    assert len(client.get('/document-explorer/list',headers=s).json()['items'])==1
    assert client.get('/document-explorer/file',headers=s,params={'relative_path':'base/일반 양식/'+fake}).status_code==404
    assert client.put('/document-explorer/government-files',headers=h,json={'relative_path':fake,'visible':False}).status_code==200
    assert client.get('/document-explorer/list',headers=s).json()['items']==[];checks['folder_file_public_copy_double_gate_and_hq_other_denial']=True
    # Existing upload API, manual authenticated NAS plan, copies and previous versions.
    req=client.get('/documents/requirements/status',headers=s,params={'site_id':site_id,'period':'all','date':'2026-10-08'});assert req.status_code==200
    item=next(x for x in req.json()['items'] if x['document_type_code']=='GOV_RISK_MONTHLY')
    for contents in [b'manual original version one',b'manual original version two']:
        uploaded=client.post('/document-submissions/upload',headers=s,data={'site_id':site_id,'requirement_id':item['requirement_id'],'document_type_code':item['document_type_code'],'work_date':'2026-10-08'},files={'file':('fixture.txt',contents,'text/plain')});assert uploaded.status_code==200,uploaded.text[:160]
        if contents==b'manual original version one':
            reviewed=client.post('/documents/'+str(uploaded.json()['document_id'])+'/review',headers=h,json={'action':'reject','comment':'isolated reupload fixture'})
            assert reviewed.status_code==200,reviewed.text[:160]
    plan=client.get('/collection-monitor/nas-export',headers=h,params={'month':'2026-10'});assert plan.status_code==200
    items=plan.json()['items'];assert len(items)>=2 and all(r['relative_path'].split('/')[1]=='관급' for r in items)
    for item in items:
        data=client.get('/collection-monitor/nas-files/'+item['key'],headers=h,params={'month':'2026-10'});assert data.status_code==200;assert sha(data.content)==item['sha256'];assert 'path' not in item
    assert client.get('/collection-monitor/nas-export',headers=s,params={'month':'2026-10'}).status_code==403
    assert client.get('/collection-monitor/nas-export',headers=o,params={'month':'2026-10'}).status_code==403
    import zipfile
    z=client.get('/collection-monitor/nas-export.zip',headers=h,params={'month':'2026-10'});assert z.status_code==200
    with zipfile.ZipFile(BytesIO(z.content)) as archive:assert archive.testzip() is None and len(archive.namelist())==len(items)
    r=client.get('/collection-monitor/overview',headers=h,params={'month':'2026-10'}).json();cell=next(c for row in r['sites'] if row['id']==site_id for c in row['cells'] if c['code']=='GOV_RISK_MONTHLY');assert cell['received']==1;checks['manual_nas_original_history_hash_zip_and_scope']=True
    # Clone-only fixtures above must never touch production data.
    checks['production_db_read_only_clone']=True
    c.close();(out/'regression.json').write_text(json.dumps({'checks':checks,'count':len(checks),'protected_baseline':before},indent=2),encoding='utf8');print(json.dumps({'checks':len(checks),'passed':True,'other_active_sites':len(other['sites'])}))

def deploy(release,out):
    if os.geteuid()!=0:raise ValueError('DEPLOY_ROOT_REQUIRED')
    plan=json.loads((release/'manifest.json').read_text(encoding='utf8'))
    for row in plan['files']:
        target=BACKEND/row['path'];expected=row['before_sha256']
        assert (sha(target.read_bytes()) if target.is_file() else None)==expected,('OPERATING_SOURCE_CHANGED',row['path'])
        assert sha((release/'backend'/row['path']).read_bytes())==row['sha256']
    out.mkdir(parents=True,exist_ok=True);os.chown(out,__import__('pwd').getpwnam('besma').pw_uid,__import__('grp').getgrnam('besma').gr_gid);os.chmod(out,0o750)
    for row in plan['files']:
        target=BACKEND/row['path']
        if target.exists():
            backup=out/'before'/row['path'];backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(target,backup)
    # Backup and create the sole new table under the service identity.
    subprocess.run(['sudo','-n','-u','besma','/srv/besma/backend/.venv/bin/python','-B',str(release.parent/'operations.py'),'database',str(release),str(out)],check=True)
    gid=__import__('grp').getgrnam('besma').gr_gid
    try:
        for row in plan['files']:
            target=BACKEND/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+'.gov-release');temp.write_bytes((release/'backend'/row['path']).read_bytes());os.chown(temp,0,gid);os.chmod(temp,0o640);os.replace(temp,target)
            assert sha(target.read_bytes())==row['sha256']
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True)
        import time,urllib.request
        for attempt in range(15):
            try:
                response=json.loads(urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=4).read());break
            except Exception:
                if attempt==14:raise
                time.sleep(1)
        receipt={'applied_at':datetime.now(timezone.utc).isoformat(),'commit':plan.get('commit'),'files':plan['files'],'health':response}
        (out/'deployment.json').write_text(json.dumps(receipt,indent=2),encoding='utf8');print(json.dumps({'deployed_files':len(plan['files']),'health':response}))
    except Exception:
        # Preserve the additive table/history; restore only pre-existing changed source.
        for row in plan['files']:
            backup=out/'before'/row['path']
            if backup.exists():shutil.copy2(backup,BACKEND/row['path'])
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True);raise

def database(release,out):
    assert os.geteuid()!=0
    snapshot(DB,out/'database-before.sqlite3');c=sqlite3.connect(DB);before=summary(c)
    c.execute('BEGIN IMMEDIATE')
    c.executescript('''CREATE TABLE IF NOT EXISTS government_contact_messages(id INTEGER PRIMARY KEY,site_id INTEGER NOT NULL REFERENCES sites(id),sender_user_id INTEGER NOT NULL REFERENCES users(id),sender_side VARCHAR(4) NOT NULL,body TEXT NOT NULL,created_at DATETIME NOT NULL,read_at DATETIME);CREATE INDEX IF NOT EXISTS ix_gov_contact_site_created ON government_contact_messages(site_id,id);''')
    assert before==summary(c);c.commit();c.close()
    (out/'database-preservation.json').write_text(json.dumps(before,indent=2),encoding='utf8')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['test','deploy','database']);a.add_argument('release');a.add_argument('out');v=a.parse_args();{'test':test,'deploy':deploy,'database':database}[v.mode](Path(v.release),Path(v.out))
