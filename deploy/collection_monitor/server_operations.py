"""Hash guarded isolated regression / additive production deployment."""
import argparse,hashlib,json,os,secrets,shutil,sqlite3,sys,tempfile,grp,subprocess
from datetime import datetime,timezone
from pathlib import Path

BACKEND=Path('/srv/besma/backend');DB=Path('/srv/besma/database/besma.db')
TARGETS=('app/main.py','app/modules/documents/routes.py','app/modules/document_submissions/routes.py')
PROTECTED=('documents','document_instances','document_upload_histories','document_review_histories','users','functional_eval_assessments','worker_attendances')
EXTRAS=[('GOV_NONCONFORMITY_LEDGER','관급 부적합사항관리대장','WEEKLY'),('GOV_WORKER_OPINION_LEDGER','관급 근로자 의견청취대장','MONTHLY')]
GOV={'24028','25037','25040','25059','25063','26004','26024','26052'}

def sha(data):return hashlib.sha256(data).hexdigest()
def patch_sources():
    changed={}
    for rel in TARGETS:
        b=(BACKEND/rel).read_bytes();text=b.decode('utf8');nl='\r\n' if '\r\n' in text else '\n';s=text.replace('\r\n','\n')
        if rel=='app/main.py':
            if 'collection_monitor.routes' not in s:
                s=s.replace('from app.modules.artifact_vault.routes import router as artifact_vault_router','from app.modules.artifact_vault.routes import router as artifact_vault_router\nfrom app.modules.collection_monitor.routes import router as collection_monitor_router')
                s=s.replace('    app.include_router(artifact_vault_router)','    app.include_router(artifact_vault_router)\n    app.include_router(collection_monitor_router)')
        elif rel.endswith('documents/routes.py'):
            marker='    summary = _compute_summary(items)'
            replacement='''    # Collection channel policy: selected government sites submit in BESMA.
    from app.modules.collection_monitor.core import GOV_CODES
    if current_user.role == Role.SITE:
        items = [item for item in items if item.get("document_type_code", "").startswith("GOV_")] if site.site_code in GOV_CODES else []
    summary = _compute_summary(items)'''
            if '# Collection channel policy:' not in s:
                begin=s.index('def get_requirement_status(');end=s.index('@router.get("/hq-dashboard"',begin)
                block=s[begin:end]
                if block.count(marker)!=1:raise ValueError('STATUS_PATCH_ANCHOR')
                s=s[:begin]+block.replace(marker,replacement)+s[end:]
        else:
            marker='    append_list = list(append_files) if append_files else []'
            replacement='''    # Collection channel policy; legacy documents and their histories remain readable.
    from app.modules.collection_monitor.core import GOV_CODES
    if current_user.role == Role.SITE:
        collection_site = db.query(Site).filter(Site.id == current_user.site_id).first()
        if not collection_site or collection_site.site_code not in GOV_CODES:
            raise HTTPException(status_code=403, detail="NAVERWORKS_COLLECTION_CHANNEL")

    append_list = list(append_files) if append_files else []'''
            if '# Collection channel policy;' not in s:
                if s.count(marker)!=1:raise ValueError('UPLOAD_PATCH_ANCHOR')
                s=s.replace(marker,replacement)
        compile(s,rel,'exec');changed[rel]={'before':b,'after':s.replace('\n',nl).encode('utf8')}
    return changed

def provision(conn):
    stamp=datetime.now(timezone.utc).isoformat();created=[]
    template=conn.execute("SELECT default_cycle_id FROM document_type_masters WHERE code='GOV_RISK_MONTHLY'").fetchone()
    if not template:raise ValueError('GOV_BASELINE_MISSING')
    for index,(code,title,freq) in enumerate(EXTRAS):
        master=conn.execute('SELECT id FROM document_type_masters WHERE code=?',(code,)).fetchone()
        if master:mid=master[0]
        else:
            cur=conn.execute("INSERT INTO document_type_masters(code,name,description,sort_order,is_active,default_cycle_id,generation_rule,is_required_default,created_at,updated_at) VALUES(?,?,?, ?,1,?,'ADHOC_MANUAL',0,?,?)",(code,title,'월간 자료 취합 NAS 연계',221+index,template[0],stamp,stamp));mid=cur.lastrowid
        for site in conn.execute('SELECT id,site_code FROM sites'):
            if site[1] not in GOV:continue
            if conn.execute('SELECT id FROM document_requirements WHERE site_id=? AND code=?',(site[0],code)).fetchone():continue
            cur=conn.execute('INSERT INTO document_requirements(site_id,document_type_id,is_enabled,code,title,frequency,is_required,display_order,due_rule_text,note,created_at,updated_at) VALUES(?,?,1,?,?,?,1,?,?,?,?,?)',(site[0],mid,code,title,freq,221+index,'주간' if freq=='WEEKLY' else '월간','NAS 취합폴더 연계',stamp,stamp));created.append(cur.lastrowid)
    return created

def counts(conn):
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {t:conn.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in PROTECTED if t in tables}

def regression(module_dir,out):
    os.umask(0o077);checks={}
    root=Path(tempfile.mkdtemp(prefix='clone-',dir=out));clone=root/'test.db'
    src=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);dest=sqlite3.connect(clone);src.backup(dest);src.close()
    original=counts(dest);new=provision(dest);dest.commit();assert counts(dest)==original;checks['existing_histories_preserved']=True
    os.environ.update(SQLITE_PATH=str(clone),STORAGE_ROOT=str(root/'storage'),DOCUMENT_EXPLORER_BASE_DIR=str(root/'explorer'),JWT_SECRET_KEY=secrets.token_urlsafe(64),ENV='prod',DEV_BYPASS_AUTH='false',PYTHONDONTWRITEBYTECODE='1')
    os.chdir(BACKEND);sys.path.insert(0,str(BACKEND));sys.dont_write_bytecode=True
    import app.modules
    app.modules.__path__.insert(0,str(module_dir))
    from app.config.settings import settings
    assert Path(settings.sqlite_path)==clone and Path(settings.storage_root)==root/'storage'
    from app.config.security import get_password_hash
    # Fixture-only passwords are never printed or saved.
    password=secrets.token_urlsafe(24)+'Aa1!'
    users=dest.execute("SELECT id,login_id,role,site_id FROM users WHERE (role='SITE' AND site_id IN (SELECT id FROM sites WHERE site_code='24028')) OR role IN ('HQ_SAFE','HQ_OTHER','HQ_SAFE_ADMIN','SUPER_ADMIN') ORDER BY id").fetchall()
    selected={}
    for r in users:
        if r[2] not in selected:selected[r[2]]=r
    for role,r in selected.items():dest.execute('UPDATE users SET password_hash=?,must_change_password=0,is_active=1 WHERE id=?',(get_password_hash(password),r[0]))
    dest.commit();dest.close()
    import importlib
    patched=patch_sources()
    for rel,module_name in [('app/modules/documents/routes.py','app.modules.documents.routes'),('app/modules/document_submissions/routes.py','app.modules.document_submissions.routes')]:
        module=importlib.import_module(module_name);exec(compile(patched[rel]['after'],rel,'exec'),module.__dict__)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.modules.auth.routes import router as auth
    from app.modules.collection_monitor.routes import router as monitor
    from app.modules.documents.routes import router as documents
    from app.modules.document_submissions.routes import router as submissions
    api=FastAPI();[api.include_router(r) for r in (auth,documents,submissions,monitor)];client=TestClient(api)
    headers={}
    for role,r in selected.items():
        resp=client.post('/auth/login',data={'username':r[1],'password':password});assert resp.status_code==200,(role,resp.status_code)
        headers[role]={'Authorization':'Bearer '+resp.json()['access_token']}
        assert client.get('/auth/me',headers=headers[role]).status_code==200
        assert client.get('/collection-monitor/context',headers=headers[role]).status_code==200
    checks['site_hq_safe_hq_other_login_and_auth_me']=True
    fixture=sqlite3.connect(clone);gov_user=selected['SITE']
    fixture.execute('UPDATE users SET must_change_password=1 WHERE id=?',(gov_user[0],));fixture.commit()
    gated=client.get('/collection-monitor/context',headers=headers['SITE']);assert gated.status_code==403
    fixture.execute('UPDATE users SET must_change_password=0 WHERE id=?',(gov_user[0],));fixture.commit();fixture.close()
    checks['initial_password_change_gate_preserved']=True
    fixture=sqlite3.connect(clone)
    from app.modules.collection_monitor.core import GOV_CODES
    gov_logins=fixture.execute("SELECT u.id,u.login_id,u.site_id FROM users u JOIN sites s ON s.id=u.site_id WHERE u.role='SITE' AND s.site_code IN ("+','.join('?' for _ in GOV_CODES)+") ORDER BY u.id",sorted(GOV_CODES)).fetchall()
    seen=set()
    for uid,login_id,sid in gov_logins:
        if sid in seen:continue
        fixture.execute('UPDATE users SET password_hash=?,must_change_password=0,is_active=1 WHERE id=?',(get_password_hash(password),uid));fixture.commit()
        r=client.post('/auth/login',data={'username':login_id,'password':password});assert r.status_code==200
        hh={'Authorization':'Bearer '+r.json()['access_token']}
        assert client.get('/auth/me',headers=hh).status_code==200
        assert client.get('/collection-monitor/context',headers=hh).json()['channel']=='BESMA'
        assert len(client.get('/documents/requirements/status',headers=hh,params={'site_id':sid,'period':'all','date':'2026-10-08'}).json()['items'])==23
        seen.add(sid)
    assert len(seen)==8;fixture.close();checks['all_eight_government_logins_and_23_requirements']=True
    h=headers['HQ_SAFE'];s=headers['SITE'];o=headers['HQ_OTHER'];site_id=selected['SITE'][3]
    req=client.get('/documents/requirements/status',headers=s,params={'site_id':site_id,'period':'all','date':'2026-10-08'});assert req.status_code==200
    assert len(req.json()['items'])==23 and all(r['document_type_code'].startswith('GOV_') for r in req.json()['items']);checks['gov_23_requirements_only']=True
    assert client.get('/documents/requirements/status',headers=s,params={'site_id':8,'period':'all','date':'2026-10-08'}).status_code==403;checks['site_isolation']=True
    for code in ['GOV_RISK_MONTHLY','GOV_NONCONFORMITY_LEDGER']:
        r=next(x for x in req.json()['items'] if x['document_type_code']==code)
        resp=client.post('/document-submissions/upload',headers=s,data={'site_id':site_id,'document_type_code':code,'requirement_id':r['requirement_id'],'work_date':'2026-10-08'},files={'file':('fixture.txt',b'isolated collection fixture','text/plain')});assert resp.status_code==200,(code,resp.status_code,resp.text[:200])
    checks['gov_upload_existing_endpoint']=True
    from app.modules.collection_monitor import worker_io
    exported=worker_io.export('2026-10')
    import zipfile
    with zipfile.ZipFile(exported['bundle']) as archive:
        manifest_out=json.loads(archive.read('manifest.json'));assert len(manifest_out['items'])==2
        for r in manifest_out['items']:assert sha(archive.read(r['key']))==r['sha256'] and '/관급/' in r['relative_path']
        assert any('2주차' in r['relative_path'] for r in manifest_out['items'])
    checks['government_originals_versioned_nas_export_hash_and_week']=True
    ov=client.get('/collection-monitor/overview',headers=h,params={'month':'2026-10'});assert ov.status_code==200
    row=next(r for r in ov.json()['sites'] if r['id']==site_id)
    assert next(c for c in row['cells'] if c['code']=='GOV_RISK_MONTHLY')['received']==1
    assert next(c for c in row['cells'] if c['code']=='GOV_NONCONFORMITY_LEDGER')['received']==1
    assert client.get('/collection-monitor/overview',headers=s,params={'month':'2026-10'}).status_code==403
    assert client.get('/collection-monitor/overview',headers=o,params={'month':'2026-10'}).status_code==200
    assert client.get('/collection-monitor/unmapped',headers=o,params={'month':'2026-10'}).status_code==403
    checks['monitor_rates_roles_and_month_scope']=True
    assert client.post('/document-submissions/upload',headers=o,data={'site_id':site_id,'document_type_code':'GOV_RISK_MONTHLY'}).status_code==403;checks['hq_other_write_blocked']=True
    fixture=sqlite3.connect(clone);c18=fixture.execute("SELECT id,login_id FROM users WHERE role='SITE' AND site_id=8 ORDER BY id LIMIT 1").fetchone()
    fixture.execute('UPDATE users SET password_hash=?,must_change_password=0,is_active=1 WHERE id=?',(get_password_hash(password),c18[0]));fixture.commit();fixture.close()
    login=client.post('/auth/login',data={'username':c18[1],'password':password});assert login.status_code==200
    ch={'Authorization':'Bearer '+login.json()['access_token']}
    resp=client.get('/documents/requirements/status',headers=ch,params={'site_id':8,'period':'all','date':'2026-10-08'});assert resp.status_code==200 and not resp.json()['items']
    assert client.post('/document-submissions/upload',headers=ch,data={'site_id':8,'document_type_code':'DAILY_TBM'}).status_code==403
    checks['c18_login_legacy_readable_collection_hidden_and_write_blocked']=True
    from app.modules.collection_monitor.core import ingest,state,overview
    blobroot=root/'blobs';blobroot.mkdir();blob=b'NAS fixture';digest=sha(blob);(blobroot/digest).write_bytes(blob)
    copy={'relative_path':'3. 위험성평가/26.10월/1팀/fixture.txt','filename':'fixture.txt','sha256':digest,'size':len(blob),'category':'risk','period':'2026-10','site_id':None,'team':'1팀'}
    manifest={'month':'2026-10','files':[copy],'complete_categories':['risk'],'error_count':0};monitorroot=root/'storage'/'collection-monitor'
    ingest(clone,monitorroot,manifest,blobroot);ingest(clone,monitorroot,manifest,blobroot)
    with state(monitorroot) as c:assert c.execute('SELECT COUNT(*) FROM copies').fetchone()[0]==1
    items=client.get('/collection-monitor/unmapped',headers=h,params={'month':'2026-10'}).json()['items'];assert len(items)==1
    assert client.post('/collection-monitor/copies/'+items[0]['id']+'/classify',headers=o,json={'site_id':8,'period':'2026-10'}).status_code==403
    assert client.post('/collection-monitor/copies/'+items[0]['id']+'/classify',headers=h,json={'site_id':8,'period':'2026-10'}).status_code==200
    assert client.get('/collection-monitor/copies/'+items[0]['id']+'/content',headers=h).content==blob
    checks['immutable_copies_repeat_classification_audit_and_download']=True
    corrupted={**copy,'sha256':'0'*64}
    try:ingest(clone,monitorroot,{**manifest,'files':[corrupted]},blobroot);raise AssertionError('bad hash accepted')
    except ValueError:pass
    checks['hash_mismatch_rejected']=True
    result={'checks':checks,'passed':len(checks),'clone':str(root),'new_requirements':len(new)}
    (out/'regression.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))

def deploy(module_dir,out):
    patched=patch_sources();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');snap=Path('/srv/besma/ops_snapshots')/('collection-monitor-'+stamp);snap.mkdir(mode=0o700)
    import pwd
    account=pwd.getpwnam('besma');os.chown(snap,account.pw_uid,account.pw_gid)
    subprocess.run(['sudo','-n','-u','besma',str(BACKEND/'.venv/bin/python'),'-B',__file__,'provision',str(module_dir),str(snap)],check=True,capture_output=True)
    provisioned=json.loads((snap/'provision.json').read_text());before=provisioned['protected_counts'];created=provisioned['new_requirements']
    files=[]
    for rel,item in patched.items():
        p=BACKEND/rel;assert p.read_bytes()==item['before'];b=snap/rel;b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(item['before'])
        tmp=p.with_suffix('.collection-new');tmp.write_bytes(item['after']);shutil.copystat(p,tmp);os.chown(tmp,p.stat().st_uid,p.stat().st_gid);os.replace(tmp,p)
        files.append({'path':rel,'before':sha(item['before']),'after':sha(p.read_bytes())})
    destination=BACKEND/'app/modules/collection_monitor';destination.mkdir(mode=0o750,exist_ok=True)
    for p in (module_dir/'collection_monitor').glob('*.py'):
        existing=destination/p.name
        if existing.exists():
            b=snap/'app/modules/collection_monitor'/p.name;b.parent.mkdir(parents=True,exist_ok=True);b.write_bytes(existing.read_bytes())
        (destination/p.name).write_bytes(p.read_bytes());os.chmod(destination/p.name,0o640);os.chown(destination/p.name,0,grp.getgrnam('besma').gr_gid)
        files.append({'path':str((destination/p.name).relative_to(BACKEND)),'after':sha(p.read_bytes())})
    os.chown(destination,0,grp.getgrnam('besma').gr_gid)
    result={'snapshot':str(snap),'files':files,'new_requirements':created,'protected_counts':before}
    (out/'deployment.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))

def provision_only(module_dir,out):
    if os.geteuid()==0:raise ValueError('DB_WRITER_MUST_BE_BESMA')
    db=sqlite3.connect(DB);reader=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);backup=sqlite3.connect(out/'before.sqlite3');reader.backup(backup);assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok';backup.close();reader.close()
    before=counts(db);old_rows={t:sha(repr(db.execute('SELECT * FROM '+t+' ORDER BY id').fetchall()).encode()) for t in ('users','document_requirements','document_type_masters')}
    old_max={t:db.execute('SELECT COALESCE(MAX(id),0) FROM '+t).fetchone()[0] for t in old_rows}
    db.execute('BEGIN IMMEDIATE');created=provision(db);assert counts(db)==before
    for t,digest in old_rows.items():assert sha(repr(db.execute('SELECT * FROM '+t+' WHERE id<=? ORDER BY id',(old_max[t],)).fetchall()).encode())==digest
    db.commit();db.close()
    (out/'provision.json').write_text(json.dumps({'protected_counts':before,'new_requirements':created},indent=2),encoding='utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['test','deploy','provision']);p.add_argument('module_dir');p.add_argument('out');a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    {'test':regression,'deploy':deploy,'provision':provision_only}[a.mode](Path(a.module_dir),out)
