"""Scoped home release, immutable daily files, read-only evaluation preparation."""
import datetime as dt,grp,hashlib,json,os,pwd,shutil,sqlite3,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
R=Path(sys.argv[1]);APP=Path('/srv/besma/backend/app');DB=Path('/srv/besma/database/besma.db');DATA=Path('/srv/besma/storage/headquarters-workspace');INBOX=Path('/home/besma-admin/.besma-workspace-attendance-inbox');TOOL=Path('/srv/besma/tools/receive_workspace_attendance.py')
EXPECTED='19ee7c79c057028e607ce5f358e2a00710433b28faa5e0de66bdd1a5f63342c6'
sha=lambda b:hashlib.sha256(b).hexdigest()
def inventory(c):
 out={}
 for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
  rows=c.execute('SELECT * FROM "'+name.replace('"','""')+'"').fetchall();out[name]={'count':len(rows),'sha256':sha(repr(rows).encode())}
 return out
def health():
 for attempt in range(25):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3) as r:assert json.load(r)=={'status':'ok'};return
  except Exception:
   if attempt==24:raise
   time.sleep(1)
def main():
 assert os.geteuid()==0;os.umask(0o027);gid=grp.getgrnam('besma').gr_gid;admin=pwd.getpwnam('besma-admin')
 old=(APP/'modules/workspace.py').read_bytes();assert sha(old)==EXPECTED,'Operating source changed'
 assert not (APP/'modules/workspace_home.py').exists() and not TOOL.exists(),'Home release already exists; review before updating'
 for name in ['backend/app/modules/workspace.py','backend/app/modules/workspace_home.py','tools/receive-workspace-attendance.py']:compile((R/name).read_bytes(),name,'exec')
 receipt=Path('/srv/besma/backups/home-dashboard-20261026-'+dt.datetime.now().strftime('%H%M%S'));receipt.mkdir(parents=True,mode=0o750);os.chown(receipt,0,gid);(receipt/'workspace-before.py').write_bytes(old)
 with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as c:
  backup=sqlite3.connect(receipt/'database-before.sqlite3');c.backup(backup);assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok';backup.close();before=inventory(c)
  roles=c.execute("SELECT role,MIN(id) FROM users WHERE is_active=1 AND must_change_password=0 GROUP BY role").fetchall()
 def write(path,body):
  path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_name(path.name+'.home-new');temp.write_bytes(body);os.chown(temp,0,gid);temp.chmod(0o640);os.replace(temp,path)
 try:
  write(APP/'modules/workspace_home.py',(R/'backend/app/modules/workspace_home.py').read_bytes());write(TOOL,(R/'tools/receive-workspace-attendance.py').read_bytes())
  write(DATA/'site-locations.json',(R/'private/site-locations.json').read_bytes())
  body=(R/'private/daily-attendance/latest.json').read_bytes();daily=json.loads(body);inbox=INBOX/('besma-daily-attendance-'+daily['date'].replace('-','')+'-'+sha(body)[:12]+'.json');inbox.write_bytes(body);os.chown(inbox,admin.pw_uid,admin.pw_gid);inbox.chmod(0o600)
  applied=json.loads(subprocess.check_output(['/srv/besma/backend/.venv/bin/python','-B',str(TOOL),str(inbox)],text=True));assert applied['people']==daily['people']
  write(APP/'modules/workspace.py',(R/'backend/app/modules/workspace.py').read_bytes());subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health()
  sys.path.insert(0,'/srv/besma/backend');from app.config.security import create_access_token
  def call(path,uid=None):
   headers={'Authorization':'Bearer '+create_access_token(uid,dt.timedelta(minutes=2))} if uid else {}
   try:
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8001'+path,headers=headers),timeout=35) as response:return response.status,json.load(response)
   except urllib.error.HTTPError as e:return e.code,{}
  assert call('/workspace/home')[0]==401
  hq={'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','HQ_OTHER','FUNCTIONAL_EVAL_VIEWER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE'};checks=[]
  for role,uid in roles:
   if role not in hq|{'SITE','SITE_FUNCTIONAL_EVAL','WORKER'}:continue
   status,value=call('/workspace/home',uid);assert status==(200 if role in hq else 403),(role,status)
   if role in hq:
    assert value['attendance']['people']==daily['people'] and 'rrn_hash' not in json.dumps(value)
    status,ready=call('/workspace/functional-readiness',uid);assert status==200 and ready['deadline']=='2026-11-20' and not ready['can_evaluate']
   checks.append({'role':role,'home':status})
  _,overview=call('/workspace/home',96);_,readiness=call('/workspace/functional-readiness',96)
  code=next(s['code'] for s in overview['sites'] if s['latitude'] is not None);weather_status,weather=call('/workspace/site-weather/'+code,96);assert weather_status==200
  with sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True) as c:after=inventory(c)
  changed=[t for t in before if before[t]!=after[t]];assert not any(t.startswith('functional_eval_') for t in changed),('Evaluation history changed',changed)
  result={'commit':(R/'commit.txt').read_text().strip(),'receipt':str(receipt),'applied_at':dt.datetime.now(dt.timezone.utc).isoformat(),'health':'ok','version':'2026.10.26.4','roles':checks,'attendance':overview['attendance'],'active_sites':len(overview['sites']),'located_sites':sum(s['latitude'] is not None for s in overview['sites']),'readiness':{k:v for k,v in readiness.items() if k not in {'sites','source_sha256','previous_periods'}},'weather_probe':{'status':weather_status,'available':weather.get('available'),'source':weather.get('source'),'observed_at':weather.get('observed_at')},'tables_checked':len(before),'changed_tables':changed,'database_migration':False,'files':{str(p):sha(p.read_bytes()) for p in [APP/'modules/workspace.py',APP/'modules/workspace_home.py',TOOL,DATA/'site-locations.json']}}
  (receipt/'deployment.json').write_text(json.dumps(result,indent=2));(receipt/'preservation.json').write_text(json.dumps({'before':before,'after':after},indent=2));print(json.dumps(result,ensure_ascii=True))
 except Exception:
  write(APP/'modules/workspace.py',old);subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health();(receipt/'rollback.txt').write_text('Previous workspace module restored; no database restore. New inactive private files preserved for review.');raise
if __name__=='__main__':main()
