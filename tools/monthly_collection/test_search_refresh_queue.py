from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,time,contextlib,shutil
R=Path(__file__).resolve().parent
@contextlib.contextmanager
def fixture():
 root=Path(tempfile.mkdtemp(dir=R))
 try:yield str(root)
 finally:
  assert root.resolve().is_relative_to(R.resolve())and root.resolve()!=R.resolve()
  shutil.rmtree('\\\\?\\'+str(root.resolve()))
def job(n):
 body={'schema':1,'targets':[{'fixture':n}]};body['id']=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest();body['created_at']='fixture';return body
with fixture()as tmp:
 root=Path(tmp);assert root.resolve().is_relative_to(R.resolve());folder=root/'search-refresh';(folder/'jobs').mkdir(parents=True)
 code=r'''
import importlib.util,json,sys,time,types
from pathlib import Path
spec=importlib.util.spec_from_file_location('fixture_module',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.STATE=Path(sys.argv[2]);m.SELF=Path(sys.argv[1]);sys.modules['approved_nas_mount']=types.SimpleNamespace(validate_approved_nas_mount=lambda:None)
def run(job):
 m.atomic(m.STATE/('started-'+str(job['targets'][0]['fixture'])+'.json'),{'pid':__import__('os').getpid()});time.sleep(.4)
 m.atomic(m.STATE/'search-refresh/receipts'/(job['id']+'.json'),{'phase':'SEARCH_VERIFIED','fixture':True})
m.run_job=run;sys.argv=[str(m.SELF),'--run'];m.main()
'''
 # The real queue file locks, process startup and final lease handoff are used.
 # Only scanner/network work is replaced with a fixture receipt.
 spec=__import__('importlib.util',fromlist=['spec_from_file_location']);sp=spec.spec_from_file_location('parent',R/'search_refresh.py');m=spec.module_from_spec(sp);sp.loader.exec_module(m)
 a=job(1);m.atomic(folder/'jobs'/(a['id']+'.json'),a)
 command=[sys.executable,'-B','-X','utf8','-c',code,str(R/'search_refresh.py'),str(root)]
 one=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 deadline=time.monotonic()+10
 while not(root/'started-1.json').exists():
  assert one.poll()is None,'First queue process ended unexpectedly'
  if time.monotonic()>deadline:raise RuntimeError('Fixture startup timeout')
  time.sleep(.02)
 b=job(2)
 with m.enqueue_lock(folder):
  m.atomic(folder/'jobs'/(b['id']+'.json'),b)
  two=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 for p in [one,two]:
  out,err=p.communicate(timeout=15);assert p.returncode==0,err
 assert all(m.load(folder/'receipts'/(x['id']+'.json'))['phase']=='SEARCH_VERIFIED'for x in [a,b])
 # A second invocation after normal exit must take the released lease and skip
 # completed jobs rather than execute them again.
 before={p.name:Path(m.filesystem_path(p)).read_bytes()for p in (folder/'receipts').glob('*.json')}
 three=subprocess.run(command,capture_output=True,text=True,timeout=15);assert three.returncode==0,three.stderr
 assert before=={p.name:Path(m.filesystem_path(p)).read_bytes()for p in (folder/'receipts').glob('*.json')}
 result={'passed':True,'two_pending_jobs_completed':True,'completed_receipts_unchanged_on_restart':True,'simultaneous_processes':[one.pid,two.pid],'all_processes_terminal':True,'scanner_or_network_invoked':False}
(R/'QUEUE_CHECK.json').write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result))
