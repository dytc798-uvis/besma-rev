"""Hash-guarded five-file update; no business database writes or migrations."""
import sys, os, json, sqlite3, hashlib, shutil, grp, subprocess, time, urllib.request, urllib.error, datetime
from pathlib import Path
ROOT=Path(sys.argv[1]);APP=Path('/srv/besma/backend/app');DB=Path('/srv/besma/database/besma.db')
FILES={
 'core/government_workspace_access.py':'b8104ab6e35bbeef53e5b418155fa50a7a7076e509e14273600b23b30c4895f5',
 'modules/government_contact/routes.py':'4099603e0593f4ab94129fab14a1f5af6009790d0231fbbcdcfbe599cac12ae9',
 'modules/collection_monitor/routes.py':'b5fb9e881aa12093f01d13e02f0e504c73e3157bb7fcf62262e968ff1af288ef',
 'modules/functional_eval/grade_stats_cache.py':'ee83ae91b2332afdc1db5d82f7de26716ad26a5dcfe2c3733695237b4efedccf',
 'modules/workspace.py':'d61d151d114eb59b659ebc4805daaca0961ec0a3665c7c825edb0804f6fdaf2d',
}
sha=lambda b:hashlib.sha256(b).hexdigest()
def ro():return sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
def inventory(c):
    result={}
    for (table,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        quoted='"'+table.replace('"','""')+'"';rows=c.execute('SELECT * FROM '+quoted).fetchall()
        result[table]={'count':len(rows),'sha256':sha(repr(rows).encode())}
    return result
def health():
    for n in range(25):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3) as r:
                assert json.loads(r.read())=={'status':'ok'};return
        except Exception:
            if n==24:raise
            time.sleep(1)
def call(path,uid):
    from app.config.security import create_access_token
    token=create_access_token(uid,datetime.timedelta(minutes=2))
    req=urllib.request.Request('http://127.0.0.1:8001'+path,headers={'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=20) as r:return r.status,json.loads(r.read())
    except urllib.error.HTTPError as e:return e.code,{}
def main():
    assert os.geteuid()==0
    os.umask(0o027);gid=grp.getgrnam('besma').gr_gid
    before={name:(APP/name).read_bytes() for name in FILES}
    for name,expected in FILES.items():
        assert sha(before[name])==expected,'Runtime changed, stop: '+name
        compile((ROOT/'backend/app'/name).read_bytes(),name,'exec')
    receipt=Path('/srv/besma/backups/workspace-followup-20261026-'+datetime.datetime.now().strftime('%H%M%S'));receipt.mkdir(parents=True,mode=0o750);os.chown(receipt,0,gid)
    for name,body in before.items():
        dest=receipt/'code-before'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(body)
    with ro() as c:
        backup=sqlite3.connect(receipt/'database-before.sqlite3');c.backup(backup);assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok';backup.close()
        initial=inventory(c)
        cached=json.loads(c.execute('SELECT hq_grade_stats_json FROM functional_eval_periods WHERE id=1').fetchone()[0])
        users=c.execute("SELECT id,role,must_change_password FROM users WHERE is_active=1 AND (role LIKE 'HQ_%' OR role IN ('SUPER_ADMIN','ACCIDENT_ADMIN','FUNCTIONAL_EVAL_VIEWER')) ORDER BY id").fetchall()
    def write(name,body):
        dest=APP/name;temp=dest.with_name(dest.name+'.renewal-new');temp.write_bytes(body);os.chown(temp,0,gid);temp.chmod(0o640);os.replace(temp,dest)
    try:
        for name in FILES:write(name,(ROOT/'backend/app'/name).read_bytes())
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health()
        sys.path.insert(0,'/srv/besma/backend');checks=[];seen=set()
        for uid,role,must_change in users:
            if must_change or (role in seen and uid not in {8,96}):continue
            seen.add(role);owner=uid in {8,96}
            status,data=call('/government-contact/access',uid);assert status==200 and data.get('allowed') and data.get('can_manage_forms')==owner,(uid,role,'access',status)
            for path in ['/document-explorer/government-document-catalog','/document-explorer/government-folders','/collection-monitor/settings']:
                status,_=call(path,uid);assert status==(200 if owner else 403),(uid,role,path,status)
            status,data=call('/workspace/bootstrap',uid);assert status==200 and data['permissions']['manage_government_forms']==owner
            assert call('/government-contact/sites',uid)[0]==200
            checks.append({'role':role,'owner':owner,'catalog_status':200 if owner else 403,'communication':200})
        status,view=call('/functional-eval/hq/grade-stats',96);assert status==200
        assert view['overall']==cached['overall'] and view.get('by_team')==cached.get('by_team') and view.get('computed_at')==cached.get('computed_at')
        assert all(row['site_code'] not in {'00057','13192','21009'} for row in view['by_site'] if not any((row.get(k) or {}).get('graded_total') for k in ('functional','safety')))
        with ro() as c:after=inventory(c)
        changed=[name for name in initial if initial[name]!=after[name]]
        assert not any(name.startswith('functional_eval_') for name in changed),('Historical records changed',changed)
        result={'applied_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commit':(ROOT/'commit.txt').read_text().strip(),'receipt':str(receipt),'files':{name:sha((APP/name).read_bytes()) for name in FILES},'health':'ok','service_user':subprocess.check_output(['systemctl','show','besma-backend.service','--property=User','--value'],text=True).strip(),'role_checks':checks,'tables_checked':len(initial),'changed_tables':changed,'functional_history_unchanged':True,'archived_total_unchanged':True,'archived_rows_before':len(cached['by_site']),'archived_rows_displayed':len(view['by_site']),'database_migration':False}
        (receipt/'preservation.json').write_text(json.dumps({'before':initial,'after':after},indent=2));(receipt/'deployment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
    except Exception:
        for name,body in before.items():write(name,body)
        subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health()
        (receipt/'rollback.txt').write_text('Previous five code files restored. No live database restore, deletion or migration.');raise
if __name__=='__main__':main()
