"""Scoped update: three modules, private org/photo assets and one additive history table."""
import ast,datetime,grp,hashlib,json,os,pwd,sqlite3,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(sys.argv[1]);APP=Path('/srv/besma/backend/app');DB=Path('/srv/besma/database/besma.db');DATA=Path('/srv/besma/storage/headquarters-workspace')
EXPECTED={'workspace.py':'51fce7799e2d79e6de6b5eb061927f917348aad123fa9b03ee31946ec5e79f75','workspace_home.py':'c1f844a84d2de76d73f6b5f661943479223099d7c13620a847c84192ffc8da6d','site_directory.py':'a3161322275194d67a99707ff68f8c7cdd7ace7c22f5f9afe21e6cfbb2523013'}
MAIN='01073f1d58a8e9c64a4e52a3b076ceaf1e79bfe924e2e3c894c3acc9780f3c6d';DATA_SHA='5b6a315c46042835f3e49ef176f674660ecfaedb39c6be6ee805442bccc72d02'
PRIVATE=['organization/company.png','organization/safety.png','organization/people.json','site-photos.json']
sha=lambda b:hashlib.sha256(b).hexdigest()
def ro():return sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True)
def inventory(c):
 out={}
 for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
  quoted='"'+name.replace('"','""')+'"';rows=c.execute('SELECT * FROM '+quoted+' ORDER BY rowid').fetchall() if not 'WITHOUT ROWID' in (c.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0] or '').upper() else c.execute('SELECT * FROM '+quoted).fetchall()
  out[name]={'count':len(rows),'sha256':sha(repr(rows).encode())}
 return out
def health():
 for n in range(25):
  try:
   with urllib.request.urlopen('http://127.0.0.1:8001/health',timeout=3) as r:assert json.loads(r.read())=={'status':'ok'};return
  except Exception:
   if n==24:raise
   time.sleep(1)
def write(dest,body,gid):
 dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_name(dest.name+'.homepage67-new');temp.write_bytes(body);os.chown(temp,0,gid);temp.chmod(0o640);os.replace(temp,dest)
def main():
 assert os.geteuid()==0;os.umask(0o027);gid=grp.getgrnam('besma').gr_gid
 manifest=json.loads((ROOT/'manifest.json').read_text());assert manifest['version']=='2026.10.26.7'
 for name,digest in manifest['files'].items():assert sha((ROOT/name).read_bytes())==digest,'Payload mismatch: '+name
 assert sha((APP/'main.py').read_bytes())==MAIN,'Runtime main changed'
 assert sha((DATA/'workspace-data.json').read_bytes())==DATA_SHA,'Workspace source changed; rebind organization before deployment'
 before={name:(APP/'modules'/name).read_bytes() for name in EXPECTED}
 for name,digest in EXPECTED.items():assert sha(before[name])==digest,'Runtime module changed: '+name;compile((ROOT/'backend'/name).read_bytes(),name,'exec')
 private_before={name:(DATA/name).read_bytes() if (DATA/name).is_file() else None for name in PRIVATE}
 assert all(value is None for value in private_before.values()),'New private assets already exist; inspect first'
 meta=json.loads((ROOT/'private/organization/people.json').read_text());assert meta['workspace_duties']['sha256']==DATA_SHA
 for chart in meta['charts']:assert sha((ROOT/'private/organization'/(chart['kind']+'.png')).read_bytes())==chart['png_sha256']
 tree=ast.parse((ROOT/'backend/site_directory.py').read_text());migration=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='migrate');ddls=[n.value for n in ast.walk(migration) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.lstrip().startswith('CREATE TABLE')];assert len(ddls)==3 and sum('CREATE TABLE IF NOT EXISTS site_directory_info_completions' in ddl for ddl in ddls)==1
 receipt=Path('/srv/besma/backups/homepage67-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));receipt.mkdir(parents=True,mode=0o750);os.chown(receipt,0,gid)
 for name,body in before.items():(receipt/name).write_bytes(body)
 with ro() as source:
  backup=sqlite3.connect(receipt/'database-before.sqlite3');source.backup(backup);assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok';backup.close()
 os.chown(receipt/'database-before.sqlite3',0,gid);os.chmod(receipt/'database-before.sqlite3',0o640)
 old_gid=os.getegid();os.setegid(gid);os.seteuid(pwd.getpwnam('besma').pw_uid)
 try:
  c=sqlite3.connect(DB);c.execute('PRAGMA busy_timeout=15000');c.execute('BEGIN IMMEDIATE');old=inventory(c)
  for ddl in ddls:c.execute(ddl)
  new=inventory(c);assert all(new[name]==value for name,value in old.items()),'Existing row changed during migration';assert new['site_directory_info_completions']['count']==0;c.commit();c.close()
 finally:os.seteuid(0);os.setegid(old_gid)
 (receipt/'preservation.json').write_text(json.dumps({'before':old,'after_additive_table':new,'old_tables_identical':True},indent=2))
 try:
  for name in PRIVATE:write(DATA/name,(ROOT/'private'/name).read_bytes(),gid)
  os.chown(DATA/'organization',0,gid);os.chmod(DATA/'organization',0o750)
  for name in EXPECTED:write(APP/'modules'/name,(ROOT/'backend'/name).read_bytes(),gid)
  subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health()
  service_user=subprocess.check_output(['systemctl','show','besma-backend.service','--property=User','--value'],text=True).strip();assert service_user=='besma','Service user changed'
  sys.path.insert(0,str(APP.parent));os.chdir(APP.parent)
  from app.config.security import create_access_token
  def call(path,uid=None):
   headers={}
   if uid is not None:headers['Authorization']='Bearer '+create_access_token(uid,datetime.timedelta(minutes=2))
   try:
    with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8001'+path,headers=headers),timeout=35) as response:
     raw=response.read();return response.status,json.loads(raw) if response.headers.get_content_type()=='application/json' else {'bytes':len(raw),'sha256':sha(raw),'headers':{k:response.headers.get(k) for k in ('Cache-Control','Vary','X-Content-Type-Options')}}
   except urllib.error.HTTPError as error:return error.code,{}
  checks=[]
  for path in ['/workspace/bootstrap','/workspace/organization-chart/company','/workspace/organization-chart/company/people','/workspace/contractors/1/pages/1']:
   status,_=call(path);assert status==401;(checks.append({'scope':'anonymous','path':path,'status':status}))
  with ro() as c:users=c.execute("SELECT id,role,ui_type FROM users WHERE is_active=1 AND must_change_password=0 ORDER BY id").fetchall()
  allowed={'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN','ACCIDENT_ADMIN','HQ_OTHER','FUNCTIONAL_EVAL_VIEWER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE'};seen=set()
  for uid,role,ui in users:
   key=(role,ui)
   if key in seen or role not in allowed|{'SITE','WORKER','SITE_FUNCTIONAL_EVAL'}:continue
   seen.add(key);expected=200 if role in allowed and ui in {'HQ_SAFE','HQ_OTHER'} else 403;status,data=call('/workspace/bootstrap',uid);assert status==expected,(role,ui,status);checks.append({'role':role,'ui_type':ui,'path':'bootstrap','status':status})
   if expected==200:
    assert data['version']=='2026.10.26.7' and len(data['menus'])==9
    for path in ['duties','sites','home','contractors','organization-chart/company/people','organization-chart/safety/people','organization-chart/company','organization-chart/safety','government-sites','functional-overview']:
     status,value=call('/workspace/'+path,uid);assert status==200,(role,path,status)
     if path.endswith('/people'):assert value['people'] and any(p['match_key'] for p in value['people'])
     if path in {'organization-chart/company','organization-chart/safety'}:assert value['headers']['Cache-Control']=='private, no-store' and value['headers']['Vary']=='Authorization'
     checks.append({'role':role,'ui_type':ui,'path':path,'status':status})
    status,policies=call('/workspace/contractors',uid);sample=next(item for item in policies['items'] if item.get('pages'));status,picture=call('/workspace/contractors/'+str(sample['id'])+'/pages/1',uid);assert status==200 and picture['bytes']>1000;checks.append({'role':role,'path':'contractor-preview','status':status})
    if role=='HQ_OTHER':assert call('/collection-monitor/report.xlsx?month=2026-10',uid)[0]==403
   else:
    assert call('/workspace/organization-chart/company',uid)[0]==403
  assert {'HQ_SAFE','HQ_OTHER','SITE'}<={role for role,ui in seen},'Required operating role not available for verification'
  assert sha((DATA/'workspace-data.json').read_bytes())==DATA_SHA and sha((APP/'main.py').read_bytes())==MAIN
  with ro() as c:after=inventory(c)
  changed=[name for name in old if after[name]!=old[name]]
  result={'version':manifest['version'],'commit':manifest['commit'],'applied_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'receipt':str(receipt),'health':'ok','service_user':service_user,'verified_role_scopes':sorted(seen),'existing_tables_preserved_during_migration':len(old),'new_history_rows':new['site_directory_info_completions']['count'],'changed_after_restart':changed,'workspace_source_unchanged':True,'main_unchanged':True,'files':{name:sha((APP/'modules'/name).read_bytes()) for name in EXPECTED},'private_assets':{name:sha((DATA/name).read_bytes()) for name in PRIVATE},'checks':checks}
  (receipt/'deployment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 except Exception:
  for name,body in before.items():write(APP/'modules'/name,body,gid)
  subprocess.run(['systemctl','restart','besma-backend.service'],check=True);health();(receipt/'rollback.txt').write_text('Previous three code files restored. Existing business records retained; additive history table and private assets retained for inspection. No database restore.');raise
if __name__=='__main__':main()
