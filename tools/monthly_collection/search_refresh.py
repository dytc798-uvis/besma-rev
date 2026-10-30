"""Receipt-backed refresh through the canonical NAS scanner and existing publisher.

No NAS content, index rows, credentials, schedules or server grants are changed here.
The scanner remains the only writer of its canonical SQLite/status/heartbeat.
"""
from pathlib import Path
import contextlib,datetime as dt,hashlib,json,ntpath,os,sqlite3,subprocess,sys,time,uuid

BASE=Path('D:/JSI/safety-workbench')
STATE=BASE/'data/monthly-collection'
NAS=Path(r'Z:\4. 안전보건관리실\★월간 자료 취합')
INDEX=Path('D:/nas-fts/state/filename_index.sqlite3')
INDEX_STATUS=Path('D:/nas-fts/state/indexer_status.json')
SCANNER=BASE/'tools/nas_indexer/nas_indexer.py'
SELF=BASE/'tools/monthly_collection/search_refresh.py'
SYNC=Path.home()/'AppData/Local/JSI/SafetyWorkbench/besma-chat/nas-index-sync.json'
PYTHON=Path.home()/'AppData/Local/Programs/Python/Python312/python.exe'
ROOT=r'Z:\4. 안전보건관리실'
BOOKS={str(NAS/'월간자료 취합현황.xlsx'),str(NAS/'4. 근로자 의견 청취/근로자 의견청취 대장_2026.xlsx')}
now=lambda:dt.datetime.now().astimezone().isoformat()
def filesystem_path(path):
 # Same documented long-path IO form as the canonical scanner. Plain paths
 # remain the only database/job keys; extended prefixes are used for IO only.
 value=os.fspath(path)
 if os.name=='nt'and len(value)>=240 and not value.startswith('\\\\?\\'):
  return '\\\\?\\UNC\\'+value[2:]if value.startswith('\\\\')else'\\\\?\\'+os.path.abspath(value)
 return value
load=lambda p:json.loads(Path(filesystem_path(p)).read_text('utf-8-sig'))
stat_file=lambda p:Path(filesystem_path(p)).stat()
exists=lambda p:Path(filesystem_path(p)).exists()
key=lambda p:ntpath.normcase(ntpath.normpath(str(p)))
def atomic(p,v):
 p=Path(p);Path(filesystem_path(p.parent)).mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.'+uuid.uuid4().hex+'.tmp');Path(filesystem_path(t)).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf-8');os.replace(filesystem_path(t),filesystem_path(p))
def sha(p):
 with Path(filesystem_path(p)).open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def ro(p):
 c=sqlite3.connect(Path(p).as_uri()+'?mode=ro',uri=True,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');return c
@contextlib.contextmanager
def enqueue_lock(folder):
 import msvcrt
 folder.mkdir(parents=True,exist_ok=True)
 with(folder/'enqueue.lock').open('a+b')as f:
  f.write(b'0');f.flush();f.seek(0)
  # Only short queue writes/final handoff use this lock, never a scan or network call.
  for attempt in range(100):
   try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1);break
   except OSError:
    if attempt==99:raise
    time.sleep(.1)
  try:yield
  finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
def allowed(path):
 p=key(path);root=key(NAS)
 try:
  if ntpath.commonpath([p,root])!=root or p==root:return False
 except ValueError:return False
 relative=ntpath.relpath(p,root)
 if any(x in {'.git','node_modules','__pycache__','.venv','venv'}for x in relative.split('\\')):return False
 q=Path(path)
 while key(q)!=root:
  io=Path(filesystem_path(q))
  if io.exists()and getattr(io.lstat(),'st_file_attributes',0)&0x400:return False
  q=q.parent
 return True
def plan(rows,indexed,stat_file,hash_file):
 """Pure decision boundary; exact receipt contents and current filesystem only."""
 pending=[];conflicts=[]
 for item in rows:
  try:st=stat_file(item['path'])
  except OSError:conflicts.append({'id':item['id'],'reason':'NAS_UNAVAILABLE'});continue
  old=indexed.get(key(item['path']))
  if old and not old['is_deleted']and old['file_size']==st.st_size and str(old['modified_at'])==str(st.st_mtime_ns):continue
  if st.st_size!=item['size']or hash_file(item['path'])!=item['sha256']:
   conflicts.append({'id':item['id'],'reason':'NAS_USER_CHANGE_PRESERVED'});continue
  pending.append({**item,'modified_at':str(st.st_mtime_ns)})
 return pending,conflicts
def targets(workbooks):
 with contextlib.closing(ro(STATE/'ledger.sqlite3'))as c:
  rows=[{'id':x['id'],'path':x['nas_path'],'size':x['size'],'sha256':x['sha256']}for x in c.execute('SELECT f.id,f.nas_path,d.size,d.sha256 FROM files f JOIN deliveries d ON d.file_id=f.id')]
 for book in workbooks:
  p=book.get('target','')
  if key(p)not in {key(x)for x in BOOKS}:raise ValueError('WORKBOOK_TARGET_NOT_APPROVED')
  rows.append({'id':'book-'+hashlib.sha256(key(p).encode()).hexdigest(),'path':p,'sha256':book['sha256'],'size':stat_file(p).st_size})
 if len(rows)>50000:raise ValueError('TOO_MANY_RECEIPTS')
 for item in rows:
  if not allowed(item['path'])or type(item['size'])is not int or item['size']<1 or len(item['sha256'])!=64:raise ValueError('RECEIPT_TARGET_NOT_APPROVED')
 return rows
def indexed():
 with contextlib.closing(ro(INDEX))as c:return {key(x['file_path']):dict(x)for x in c.execute('SELECT file_path,file_size,modified_at,is_deleted FROM files WHERE root_path=?',(ROOT,))}
def launch():
 # A fixed executable/script pair, no shell and no request text in arguments.
 if Path(__file__).resolve()!=SELF.resolve():raise ValueError('PRODUCTION_SCRIPT_REQUIRED')
 p=subprocess.Popen([str(PYTHON),'-I','-B','-X','utf8',str(SELF),'--run'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 return p.pid
def request(workbooks,root=STATE,nas=NAS):
 if Path(root).resolve()!=STATE.resolve()or Path(nas).resolve()!=NAS.resolve():return {'state':'TEST_ONLY'}
 try:
  sys.path.insert(0,str(BASE/'tools/nas_indexer'));import approved_nas_mount
  approved_nas_mount.validate_approved_nas_mount()
  rows=targets(workbooks);pending,conflicts=plan(rows,indexed(),stat_file,sha)
  folder=STATE/'search-refresh'
  if not pending:
   with enqueue_lock(folder):
    waiting=[p for p in (folder/'jobs').glob('*.json')if not exists(folder/'receipts'/p.name)or load(folder/'receipts'/p.name).get('phase')not in {'SEARCH_VERIFIED','SOURCE_CHANGED_REVIEW_REQUIRED'}]
    pid=launch()if waiting else None
   return {'state':'SEARCH_PENDING'if waiting else'ALREADY_INDEXED'if not conflicts else'REVIEW_REQUIRED','checked':len(rows),'conflicts':len(conflicts),'pid':pid}
  payload={'schema':1,'targets':sorted(pending,key=lambda x:x['id'])};digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  job=folder/'jobs'/(digest+'.json')
  with enqueue_lock(folder):
   if not exists(job):atomic(job,{**payload,'id':digest,'created_at':now()})
   pid=launch()
  result={'state':'QUEUED','id':digest,'targets':len(pending),'conflicts':len(conflicts),'pid':pid,'at':now()};atomic(folder/'latest-request.json',result);return result
 except Exception as error:
  result={'state':'RETRY_PENDING','error':type(error).__name__,'at':now(),'received_files_preserved':True};atomic(STATE/'search-refresh/latest-request.json',result);return result
def matching(rows):
 found=indexed()
 return all((entry:=found.get(key(x['path'])))and not entry['is_deleted']and entry['file_size']==x['size']and str(entry['modified_at'])==x['modified_at']for x in rows)
def scan_result(value,started):
 if value.get('operation')!='index'or value.get('state')not in {'completed','completed_with_errors'}:return 0
 if dt.datetime.fromisoformat(value['started_at'])<started-dt.timedelta(seconds=2):return 0
 roots=[x for x in value.get('root_results',[])if x.get('root')==ROOT]
 if len(roots)!=1 or roots[0].get('status')!='completed'or roots[0].get('errors')!=0:return 0
 return roots[0]['scan_id']
def wait_for_existing_scanner(status):
 # Discover a real canonical scanner process, then poll its kernel process handle.
 # A stale PID/status/lock file alone is never treated as a live wait.
 command="@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*D:\\JSI\\safety-workbench\\tools\\nas_indexer\\nas_indexer.py*' } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
 p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',command],capture_output=True,text=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if p.returncode:raise RuntimeError('SCANNER_PROCESS_QUERY_FAILED')
 ids=json.loads(p.stdout)if p.stdout.strip()else[]
 if isinstance(ids,int):ids=[ids]
 if not ids:return False
 import ctypes
 from ctypes import wintypes
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];k.OpenProcess.restype=wintypes.HANDLE;k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];k.CloseHandle.argtypes=[wintypes.HANDLE]
 handles=[]
 try:
  for pid in ids:
   handle=k.OpenProcess(0x00100000,False,pid)
   if handle:handles.append(handle)
  if not handles:return False
  status('WAITING_FOR_LIVE_SCANNER',scanner_pids=ids)
  deadline=time.monotonic()+7200
  while time.monotonic()<deadline:
   outcomes=[k.WaitForSingleObject(h,0)for h in handles]
   if any(x not in {0,258}for x in outcomes):raise RuntimeError('SCANNER_HANDLE_QUERY_FAILED')
   if all(x==0 for x in outcomes):return True
   time.sleep(5)
  raise TimeoutError('SCANNER_STILL_RUNNING')
 finally:
  for h in handles:k.CloseHandle(h)
def run_job(job):
 folder=STATE/'search-refresh';receipt=folder/'receipts'/(job['id']+'.json');start=dt.datetime.now().astimezone()
 def status(phase,**kw):atomic(receipt,{'id':job['id'],'at':now(),'phase':phase,'received_files_preserved':True,**kw})
 targets=job['targets']
 # Revalidate the queued names and content before starting the fixed scanner.
 if not targets or len(targets)>50000 or any(not allowed(x['path'])or stat_file(x['path']).st_size!=x['size']or str(stat_file(x['path']).st_mtime_ns)!=x['modified_at']or sha(x['path'])!=x['sha256']for x in targets):
  status('SOURCE_CHANGED_REVIEW_REQUIRED');return
 if matching(targets):
  value=load(INDEX_STATUS);scan=scan_result(value,start)
  # An earlier successful job may already have covered this queued generation.
  if not scan:scan=next((x['scan_id']for x in value.get('root_results',[])if x.get('root')==ROOT and x.get('status')=='completed'and x.get('errors')==0),0)
 else:scan=0
 if not scan:
  code=1
  for attempt in range(3):
   with Path(filesystem_path(folder/('indexer-'+job['id']+'.log'))).open('a',encoding='utf-8')as log:
    process=subprocess.Popen([str(PYTHON),'-B','-X','utf8',str(SCANNER),'--group','safety'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    status('INDEXING',scanner_pid=process.pid)
    code=process.wait()
   if code==0:break
   if not wait_for_existing_scanner(status):break
  if code!=0:status('INDEX_RETRY_PENDING',scanner_exit_code=code);return
  scan=scan_result(load(INDEX_STATUS),start)
  if not scan or not matching(targets):status('INDEX_VERIFICATION_PENDING');return
 status('INDEXED_SERVER_PENDING',scan_id=scan,targets=len(targets))
 deadline=time.monotonic()+600
 while time.monotonic()<deadline:
  try:
   remote=load(SYNC)
   if remote.get('phase')=='VERIFIED'and remote.get('scan_id',0)>=scan and remote.get('server_session_id')and remote.get('entry_count',0)>0:
    status('SEARCH_VERIFIED',scan_id=scan,server_scan_id=remote['scan_id'],entry_count=remote['entry_count'],server_sha256=remote['sha256'],targets=len(targets));return
  except (OSError,ValueError,KeyError):pass
  time.sleep(5)
 status('INDEXED_SERVER_PENDING',scan_id=scan,targets=len(targets),retry_needed=True)
def main():
 if sys.argv[1:]!=['--run']or Path(__file__).resolve()!=SELF.resolve():raise ValueError('FIXED_WORKER_REQUIRED')
 sys.path.insert(0,str(BASE/'tools/nas_indexer'));import approved_nas_mount
 approved_nas_mount.validate_approved_nas_mount()
 folder=STATE/'search-refresh';folder.mkdir(parents=True,exist_ok=True)
 import msvcrt
 with (folder/'worker.lock').open('a+b')as f:
  f.write(b'0');f.flush();f.seek(0)
  try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
  except OSError:return
  owned=True;seen=set()
  try:
   while True:
    with enqueue_lock(folder):
     jobs=[p for p in sorted((folder/'jobs').glob('*.json'))if p.name not in seen]
     if not jobs:
      # Release processing while enqueue remains locked: a new writer will
      # either be seen above or launch a worker after the lease is released.
      f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);owned=False;return
    for p in jobs:
     seen.add(p.name);job=load(p)
     expected=hashlib.sha256(json.dumps({'schema':job['schema'],'targets':job['targets']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
     if job['schema']!=1 or job['id']!=p.stem or expected!=job['id']:raise ValueError('INVALID_REFRESH_JOB')
     receipt=folder/'receipts'/(expected+'.json')
     if exists(receipt)and load(receipt).get('phase')=='SEARCH_VERIFIED':continue
     try:run_job(job)
     except Exception as error:atomic(receipt,{'id':job['id'],'at':now(),'phase':'RETRY_PENDING','error':type(error).__name__,'received_files_preserved':True})
  finally:
   if owned:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
if __name__=='__main__':
 try:main()
 except Exception as error:atomic(STATE/'search-refresh/worker-error.json',{'at':now(),'error':type(error).__name__,'state':'RETRY_PENDING'})
