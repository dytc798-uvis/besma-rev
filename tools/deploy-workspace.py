"""Scoped additive release; preserve operational records and restore code on failure."""
import hashlib,json,os,pwd,grp,shutil,sqlite3,subprocess,sys,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).parent;APP=Path('/srv/besma/backend/app');DB=Path('/srv/besma/database/besma.db');DATA=Path('/srv/besma/storage/headquarters-workspace')
EXPECTED='6bb1f48a4a4164922b52f1b8c1fe27402b75f298549025459ab26323cf6bc2cb'
sha=lambda b:hashlib.sha256(b).hexdigest()
def inventory(c):
 out={}
 for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
  table='"'+name.replace('"','""')+'"'
  rows=c.execute('SELECT * FROM '+table).fetchall()
  out[name]={'count':len(rows),'sha256':sha(repr(rows).encode())}
 return out
def write(p,body,gid):
 p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.workspace-new');temp.write_bytes(body);os.chown(temp,0,gid);os.chmod(temp,0o640);os.replace(temp,p)
def main():
 assert os.geteuid()==0
 os.umask(0o027);gid=grp.getgrnam('besma').gr_gid
 before=(APP/'main.py').read_bytes();assert sha(before)==EXPECTED,'Operating main changed; stop'
 assert not (APP/'modules/workspace.py').exists() and not DATA.exists(),'New release already exists; inspect rather than overwrite'
 candidate=(R/'backend/main.py').read_bytes()
 stripped=candidate.decode().replace('    from app.modules.workspace import router as workspace_router\n    app.include_router(workspace_router)\n','')
 assert stripped.splitlines()==before.decode().splitlines(),'Unexpected main changes'
 for file in [R/'backend/main.py',R/'backend/workspace.py']:compile(file.read_bytes(),str(file),'exec')
 data=json.loads((R/'private/workspace-data.json').read_text());assert len(data['risks'])==342 and len(data['cases'])==43 and len(data['duties'])==70
 receipt=Path('/srv/besma/backups/workspace-20261026-'+datetime.now().strftime('%H%M%S'));receipt.mkdir(mode=0o750,parents=True);os.chown(receipt,0,gid)
 (receipt/'main-before.py').write_bytes(before)
 src=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);backup=sqlite3.connect(receipt/'database-before.sqlite3');src.backup(backup);src.close();assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok';backup.close()
 old_gid=os.getegid();os.setegid(gid);os.seteuid(pwd.getpwnam('besma').pw_uid)
 try:
  c=sqlite3.connect(DB);c.execute('PRAGMA busy_timeout=10000');c.execute('BEGIN IMMEDIATE');old=inventory(c)
  c.execute('CREATE TABLE workspace_site_preferences(user_id INTEGER NOT NULL REFERENCES users(id),site_code TEXT NOT NULL,is_favorite INTEGER NOT NULL,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,site_code))')
  new=inventory(c);assert all(new[t]==v for t,v in old.items());c.commit();c.close()
 finally:os.seteuid(0);os.setegid(old_gid)
 (receipt/'preservation.json').write_text(json.dumps({'before':old,'after_additive_table':new,'old_tables_unchanged':True},indent=2))
 DATA.mkdir(mode=0o750);os.chown(DATA,0,gid)
 for file in (R/'private').rglob('*'):
  if file.is_file():write(DATA/file.relative_to(R/'private'),file.read_bytes(),gid)
 for directory in [DATA,*[p for p in DATA.rglob('*') if p.is_dir()]]:os.chown(directory,0,gid);os.chmod(directory,0o750)
 try:
  write(APP/'modules/workspace.py',(R/'backend/workspace.py').read_bytes(),gid)
  write(APP/'main.py',candidate,gid)
  subprocess.run(['systemctl','restart','besma-backend.service'],check=True)
  for attempt in range(20):
   try:
    health=json.loads(urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3).read());assert health=={'status':'ok'};break
   except Exception:
    if attempt==19:raise
    time.sleep(1)
  try:urllib.request.urlopen('http://127.0.0.1:8001/workspace/bootstrap',timeout=5);raise AssertionError('Unauthenticated access allowed')
  except urllib.error.HTTPError as e:assert e.code==401
  source=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);after=inventory(source);source.close()
  changed=[t for t,v in old.items() if after[t]!=v]
  assert not any(t.startswith('functional_eval_') for t in changed),('Unexpected evaluation change',changed)
  result={'applied_at':datetime.now(timezone.utc).isoformat(),'commit':(R/'commit.txt').read_text().strip(),'health':health,'unauthenticated_status':401,'preserved_tables':len(old),'changed_after_restart':changed,'data_sha256':sha((DATA/'workspace-data.json').read_bytes()),'main_sha256':sha(candidate),'workspace_sha256':sha((APP/'modules/workspace.py').read_bytes()),'preview_files':len(list((DATA/'policy-previews').glob('*.jpg'))),'receipt':str(receipt)}
  (receipt/'deployment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 except Exception:
  write(APP/'main.py',before,gid);subprocess.run(['systemctl','restart','besma-backend.service'],check=True)
  # The new, unused module/data/table remain for inspection; no live DB restore.
  (receipt/'rollback.txt').write_text('Restored original main.py and restarted. Existing data untouched. Additive candidate retained.');raise
if __name__=='__main__':main()
