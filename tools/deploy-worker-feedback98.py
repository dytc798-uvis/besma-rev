"""Narrow reviewed operating update. No credentials or individual source fields are logged."""
from pathlib import Path
import ast,datetime,grp,hashlib,json,os,pwd,sqlite3,subprocess,sys,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent;APP=Path('/srv/besma/backend/app');DB=Path('/srv/besma/database/besma.db')
EXPECTED_MAIN='01073f1d58a8e9c64a4e52a3b076ceaf1e79bfe924e2e3c894c3acc9780f3c6d';EXPECTED_ROUTES='8994829a99fdaa164914236651f3e2bd12af780d95689e6482e1901fb902f3b9'
sha=lambda b:hashlib.sha256(b).hexdigest()
def ro():return sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
def rows_digest(db,table):
    table='"'+table.replace('"','""')+'"';return {str(r[0]):sha(repr(r).encode())for r in db.execute('SELECT * FROM '+table+' ORDER BY rowid')}
def health():
    for n in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3)as r:
                if json.loads(r.read())=={'status':'ok'}:return
        except OSError:pass
        time.sleep(.5)
    raise RuntimeError('HEALTH_FAILED')
def write(path,body,gid,mode=0o640):
    tmp=path.with_name(path.name+'.voice98-new');tmp.write_bytes(body);os.chown(tmp,0,gid);tmp.chmod(mode);os.replace(tmp,path)
def main():
    assert os.geteuid()==0;os.umask(0o027);gid=grp.getgrnam('besma').gr_gid;uid=pwd.getpwnam('besma').pw_uid
    manifest=json.loads((ROOT/'backend-manifest.json').read_text());before_main=(APP/'main.py').read_bytes();routes=APP/'modules/worker_feedback/routes.py';before_routes=routes.read_bytes()
    assert sha(before_main)==EXPECTED_MAIN and sha(before_routes)==EXPECTED_ROUTES,'Operating code changed; inspect before retry'
    for name,digest in manifest.items():assert sha((ROOT/name).read_bytes())==digest;compile((ROOT/name).read_bytes(),name,'exec')
    targets={'worker_feedback_read.py':APP/'modules/worker_feedback/desktop_read.py','worker_feedback_refresh.py':APP/'modules/worker_feedback/refresh.py'}
    assert all(not p.exists()for p in targets.values()),'New module already installed; inspect result'
    for name in ['besma-worker-feedback.service','besma-worker-feedback.timer']:assert not Path('/etc/systemd/system',name).exists(),'Timer already exists'
    receipt=Path('/srv/besma/backups')/('voice98-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));receipt.mkdir(mode=0o750);os.chown(receipt,0,gid)
    (receipt/'main.py').write_bytes(before_main);(receipt/'routes.py').write_bytes(before_routes)
    with ro()as db:
        before={t:rows_digest(db,t)for t in ['sites','users','worker_feedback_opinions']}
        with sqlite3.connect(receipt/'database-before.sqlite3')as backup:db.backup(backup);assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok'
        hq=db.execute("SELECT id FROM users WHERE name=? AND is_active=1 AND must_change_password=0 AND site_id IS NULL AND role IN ('HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN')",('정상익',)).fetchall();assert len(hq)==1,'HQ owner identity requires review'
        assert db.execute("SELECT COUNT(*) FROM sites WHERE site_code='HQ_LAB'").fetchone()[0]==0
    os.chmod(receipt/'database-before.sqlite3',0o600)
    text=before_main.decode();import_line='from app.modules.worker_feedback.routes import router as worker_feedback_router';include='    app.include_router(worker_feedback_router)'
    assert text.count(import_line)==text.count(include)==1
    text=text.replace(import_line,import_line+'\nfrom app.modules.worker_feedback.desktop_read import router as worker_feedback_read_router\nfrom app.modules.worker_feedback.refresh import router as worker_feedback_refresh_router').replace(include,include+'\n    app.include_router(worker_feedback_read_router)\n    app.include_router(worker_feedback_refresh_router)');compile(text,'main.py','exec')
    # Keep the established endpoints and feed. Reads stop initiating hidden writes;
    # both the explicit sync and the timer reuse the append-only importer.
    source=before_routes.decode();tree=ast.parse(source);sync=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_sync_from_google');lines=source.splitlines(keepends=True)
    lines[sync.lineno-1:sync.end_lineno]=['def _sync_from_google(db: DbDep, limit: int = 1000) -> dict[str, Any]:\n','    from .refresh import run_refresh\n','    value = run_refresh(db)\n', '    return {"fetched": value["fetched"], "created": value["created"], "updated": 0, "held": value["held"], "error": None}\n']
    patched=''.join(lines);anchor='        sync_result = _sync_from_google(db, limit=1000)';assert patched.count(anchor)==1;patched=patched.replace(anchor,'        from .refresh import status_value\n        sync_result = {"source_sync_performed": False, **status_value()}');compile(patched,'routes.py','exec')
    try:
        for name,path in targets.items():write(path,(ROOT/name).read_bytes(),gid)
        write(APP/'main.py',text.encode(),gid);write(routes,patched.encode(),gid)
        # Create only the requested synthetic site. HQ account remains unassigned.
        with sqlite3.connect(DB)as db:
            db.execute('PRAGMA busy_timeout=15000');db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT INTO sites(site_code,site_name,contract_type,status,notes,created_by_user_id,updated_by_user_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",('HQ_LAB','본사 실험실','내부시험','LAB','본사 기능 시험용. 실제 공사·출역·관급 문서취합 대상 제외.',hq[0][0],hq[0][0]));db.commit()
        os.chdir(APP.parent);sys.path.insert(0,str(APP.parent))
        from app.modules.worker_feedback.routes import _fetch_script_rows,_opinion_from_raw
        from app.core.database import SessionLocal
        raw=_fetch_script_rows(1000)
        with SessionLocal()as db:
            candidates=[_opinion_from_raw(db,r)for r in raw]
            test=[p for p in candidates if p['worker_name']=='정상익'and p['submitted_at_raw']=='2026-10-28T01:48:22.000Z'];assert len(test)==1,'Requested test response not uniquely found'
        state=DB.parent/'worker-feedback-refresh';state.mkdir(mode=0o700,exist_ok=True);os.chown(state,uid,gid)
        binding={'worker_name':'정상익','phone_sha256':sha(test[0]['phone_normalized'].encode()),'approved_user_id':hq[0][0],'site_code':'HQ_LAB','approved_at':datetime.datetime.now(datetime.timezone.utc).isoformat()};file=state/'lab-identity.json';assert not file.exists();file.write_text(json.dumps(binding,ensure_ascii=False),encoding='utf-8');os.chown(file,uid,gid);file.chmod(0o600)
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health()
        from app.config.security import create_access_token
        def call(path,userid=None,method='GET'):
            headers={}
            if userid is not None:headers['Authorization']='Bearer '+create_access_token(userid,datetime.timedelta(minutes=2))
            request=urllib.request.Request('http://127.0.0.1:8001'+path,headers=headers,method=method)
            try:
                with urllib.request.urlopen(request,timeout=30)as r:return r.status,json.loads(r.read())
            except urllib.error.HTTPError as e:return e.code,{}
        checks=[]
        for path in ['/worker-feedback/desktop-responses','/worker-feedback/refresh-status']:
            assert call(path)[0]==401;checks.append('anonymous denied '+path)
        status,outcome=call('/worker-feedback/refresh',hq[0][0],'POST');assert status==200 and outcome['created']==1 and outcome['existing_rows_updated']==0
        checks.append('New test response imported once without rewriting existing records')
        assert call('/worker-feedback/refresh',hq[0][0],'POST')[1]['created']==0;checks.append('Repeated import idempotent')
        status,data=call('/worker-feedback/desktop-responses',hq[0][0]);assert status==200 and data['total_count']==4;assert not data['source_sync_performed'];checks.append('HQ stored read includes all four opinions')
        status,lab=call('/worker-feedback/desktop-responses?site_code=HQ_LAB',hq[0][0]);assert status==200 and lab['total_count']==1 and lab['items'][0]['worker_name']=='정상익';checks.append('Requested test belongs only to HQ lab')
        with ro()as db:
            active=db.execute("SELECT id,role,site_id FROM users WHERE is_active=1 AND must_change_password=0 AND role IN ('SITE','WORKER','HQ_OTHER') ORDER BY id").fetchall()
        seen=set()
        for userid,role,site_id in active:
            if role in seen:continue
            seen.add(role);status,value=call('/worker-feedback/desktop-responses',userid)
            if role=='SITE':
                assert status==200;assert call('/worker-feedback/desktop-responses?site_code=HQ_LAB',userid)[0]==403;assert call('/worker-feedback/refresh',userid,'POST')[0]==403
                with ro()as db:own=db.execute('SELECT site_code FROM sites WHERE id=?',(site_id,)).fetchone()[0]
                assert all(x['matched_site_code']==own for x in value['items']);checks.append('Actual SITE JWT only own data and cannot import or read lab')
            else:assert status==403;checks.append(role+' denied')
        assert 'SITE'in seen
        unit='''[Unit]
Description=BESMA Google worker opinions receipt
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=besma
Group=besma
WorkingDirectory=/srv/besma/backend
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/srv/besma/backend/.venv/bin/python -m app.modules.worker_feedback.refresh
TimeoutStartSec=50
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/srv/besma/database
'''
        timer='''[Unit]
Description=Receive new Google worker opinions each minute
[Timer]
OnCalendar=*-*-* *:*:00
RandomizedDelaySec=3
AccuracySec=1s
Persistent=true
Unit=besma-worker-feedback.service
[Install]
WantedBy=timers.target
'''
        for name,body in [('besma-worker-feedback.service',unit),('besma-worker-feedback.timer',timer)]:write(Path('/etc/systemd/system')/name,body.encode(),0,0o644)
        subprocess.run(['systemd-analyze','verify','/etc/systemd/system/besma-worker-feedback.service','/etc/systemd/system/besma-worker-feedback.timer'],check=True,capture_output=True)
        subprocess.run(['systemctl','daemon-reload'],check=True);subprocess.run(['systemctl','enable','--now','besma-worker-feedback.timer'],check=True,capture_output=True)
        subprocess.run(['systemctl','start','besma-worker-feedback.service'],check=True)
        assert subprocess.check_output(['systemctl','show','besma-worker-feedback.service','--property=Result','--value'],text=True).strip()=='success';checks.append('Installed one-minute timer and service successfully executed as besma')
        with ro()as db:
            after={t:rows_digest(db,t)for t in before};assert all(after[t].get(key)==value for t,rows in before.items()for key,value in rows.items());assert after['users']==before['users'];assert len(after['sites'])==len(before['sites'])+1;assert len(after['worker_feedback_opinions'])==4
        checks.append('All prior sites users opinions unchanged byte-for-value')
        result={'passed':True,'receipt':str(receipt),'health':'ok','service_user':'besma','checks':checks,'stored_opinions':4,'new_opinions':1,'new_lab_sites':1,'old_opinions_preserved':3,'HQ_account_changed':False,'auto_interval_seconds':60,'backend_files':{str(p.relative_to(APP)):sha(p.read_bytes())for p in [APP/'main.py',routes,*targets.values()]}}
        (receipt/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
    except Exception:
        subprocess.run(['systemctl','disable','--now','besma-worker-feedback.timer'],capture_output=True)
        write(APP/'main.py',before_main,gid);write(routes,before_routes,gid);subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health()
        (receipt/'rollback.txt').write_text('Previous entry/router restored. Timer disabled. Additive site/opinion records and their backups preserved. No database restore or history deletion.')
        raise
if __name__=='__main__':main()
