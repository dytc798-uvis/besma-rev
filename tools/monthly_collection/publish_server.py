"""Publish only validated intake metadata through the already approved SSH identity."""
import calendar,datetime as dt,hashlib,json,os,re,subprocess,sys,uuid
from pathlib import Path
ROOT=Path(r'D:\JSI\safety-workbench\data\monthly-collection')
KEY=Path(r'E:\SecureKeys\ssh\besma-ncp-ed25519')
HOST='besma-admin@101.79.24.88'
KEYPRINT='SHA256:Iihen1N6ttLDlzN96IzsaOYGf2tAl8l7kvAc7C8S/2Y'
HOSTPRINT='SHA256:UdTiy0n77FCIzWM3HESLqY7plu8UATBBpzjWe+UK09g'
OPTIONS=['-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','HostKeyAlgorithms=ssh-ed25519','-i',str(KEY)]
def call(args,**kwargs):
 r=subprocess.run(args,text=True,capture_output=True,encoding='utf8',timeout=90,**kwargs)
 if r.returncode:raise RuntimeError('TRANSPORT_FAILED')
 return r.stdout
def verify():
 assert KEYPRINT in call(['ssh-keygen','-lf',str(KEY)+'.pub']),'KEY_FINGERPRINT_CHANGED'
 host=call(['ssh-keygen','-F','101.79.24.88']);assert HOSTPRINT in call(['ssh-keygen','-lf','-'],input=host),'HOST_FINGERPRINT_CHANGED'
def reviewed_snapshot(value,registry):
 if not isinstance(registry,dict)or set(registry)!={'schema','notes'}or registry['schema']!=1 or not isinstance(registry['notes'],list)or len(registry['notes'])>1000:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
 index={r['id']:r for r in value['items']};seen=set();notes=[]
 for note in registry['notes']:
  if not isinstance(note,dict)or not isinstance(note.get('id'),str)or not re.fullmatch('[0-9a-f]{64}',note['id'])or not isinstance(note.get('sha256'),str)or not re.fullmatch('[0-9a-f]{64}',note['sha256']):raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  kind=note.get('kind')
  if not isinstance(kind,str):raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  pair=(note['id'],kind)
  if pair in seen:raise ValueError('REVIEWED_NOTES_DUPLICATE')
  seen.add(pair)
  if kind=='PERIOD':
   if set(note)!={'id','sha256','kind','document_month'}or not isinstance(note['document_month'],str)or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',note['document_month']):raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  elif kind=='PAGES':
   if set(note)!={'id','sha256','kind','present','expected'}or type(note['present'])is not int or type(note['expected'])is not int or not 1<=note['present']<note['expected']<=1000:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  elif kind=='LABEL_MONTH':
   if set(note)!={'id','sha256','kind','label_month'}or type(note['label_month'])is not int or not 1<=note['label_month']<=12:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  elif kind=='INVALID_DATE':
   if set(note)!={'id','sha256','kind','document_month','day'}or not isinstance(note['document_month'],str)or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',note['document_month'])or type(note['day'])is not int or not 0<=note['day']<=31:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
   year,month=map(int,note['document_month'].split('-'))
   if note['day']!=0 and note['day']<=calendar.monthrange(year,month)[1]:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  elif kind=='OPINION_NONE_DECLARED':
   if set(note)!={'id','sha256','kind','date_scope'}or not isinstance(note['date_scope'],str)or note['date_scope']not in ('DAY','PERIOD_ONLY','MISSING'):raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  elif kind=='OPINION_STATE_DIFFERENCE':
   if set(note)!={'id','sha256','kind'}:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  elif kind=='ASSESSMENT_DOCUMENT':
   if set(note)!={'id','sha256','kind','assessment_kind','document_date','site_code'}or note['assessment_kind']not in ('INITIAL','REGULAR','OCCASIONAL','CONTINUOUS')or not isinstance(note['document_date'],str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',note['document_date'])or not isinstance(note['site_code'],str)or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',note['site_code']):raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
   try:day=dt.date.fromisoformat(note['document_date'])
   except ValueError:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')from None
   if day>dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date():raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  else:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  current=index.get(note['id'])
  if current is not None and current['sha256']==note['sha256']:
   if kind in ('OPINION_STATE_DIFFERENCE','OPINION_NONE_DECLARED')and current.get('category')!='opinions':raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
   if kind=='ASSESSMENT_DOCUMENT'and(current.get('category')!='risk'or current.get('state')!='SAVED'or current.get('site_code')!=note['site_code']):raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
   notes.append(note)
 result={k:v for k,v in value.items()if k!='reviewed_source_notes'}
 if notes:result['reviewed_source_notes']=sorted(notes,key=lambda x:(x['id'],x['kind']))
 return result

def referenced_snapshot(value,registry,catalog):
 if not isinstance(registry,dict)or set(registry)!={'schema','references'}or type(registry['schema'])is not int or registry['schema']!=1 or not isinstance(registry['references'],list)or len(registry['references'])>1000:raise ValueError('REVIEWED_REFERENCES_CHECK_REQUIRED')
 registered={row['code']:row['site']for row in catalog['sites']};seen=set();references=[]
 for ref in registry['references']:
  if not isinstance(ref,dict)or set(ref)!={'id','sha256','contracts'}or not isinstance(ref['id'],str)or not re.fullmatch('[0-9a-f]{64}',ref['id'])or not isinstance(ref['sha256'],str)or not re.fullmatch('[0-9a-f]{64}',ref['sha256'])or ref['id']in seen:raise ValueError('REVIEWED_REFERENCES_CHECK_REQUIRED')
  seen.add(ref['id']);contracts=ref['contracts']
  if not isinstance(contracts,list)or not 2<=len(contracts)<=8 or any(not isinstance(c,dict)or set(c)!={'code','name'}or not isinstance(c['code'],str)or not re.fullmatch('[A-Za-z0-9_-]{1,40}',c['code'])or c['code']not in registered or c['name']!=registered[c['code']]for c in contracts):raise ValueError('REVIEWED_REFERENCE_CONTRACT_CHECK_REQUIRED')
  codes=[c['code']for c in contracts]
  if codes!=sorted(set(codes)):raise ValueError('REVIEWED_REFERENCE_CONTRACT_CHECK_REQUIRED')
  references.append(ref)
 result={k:v for k,v in value.items()if k!='reviewed_source_references'}
 if references:result['reviewed_source_references']=sorted(references,key=lambda r:r['id'])
 return result

def retained_assessment_facts(value,registry):
 # Validate the complete cache before discarding superseded source versions.
 reviewed_snapshot({'items':[]},registry)
 if any(n['kind']!='ASSESSMENT_DOCUMENT'for n in registry['notes']):raise ValueError('ASSESSMENT_CACHE_CHECK_REQUIRED')
 items={r['id']:r for r in value['items']}
 notes=[n for n in registry['notes']if (item:=items.get(n['id']))is not None and
        item.get('category')=='risk'and item.get('state')=='SAVED'and
        item.get('sha256')==n['sha256']and item.get('site_code')==n['site_code']]
 return notes

def save_assessment_facts(path,notes,before):
 raw=json.dumps({'schema':1,'notes':sorted(notes,key=lambda n:n['id'])},ensure_ascii=False,indent=2).encode('utf8')
 if raw==before:return
 temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
 try:
  temporary.write_bytes(raw)
  if path.is_symlink()or (path.read_bytes()if path.exists()else None)!=before:raise ValueError('ASSESSMENT_CACHE_CHANGED')
  os.replace(temporary,path)
 finally:
  if temporary.exists():temporary.unlink()

def prepared_snapshot(root):
 p=root/'dashboard.json';raw=p.read_bytes();value=json.loads(raw);notes=root/'reviewed-source-notes.json';references=root/'reviewed-source-references.json'
 canonical=root.resolve()==ROOT.resolve();fact_path=root/'assessment-document-facts.json';fact_before=None;retained=[];manual_keys=set()
 if canonical:
  if fact_path.exists():
   if fact_path.is_symlink()or fact_path.stat().st_size>1024*1024:raise ValueError('ASSESSMENT_CACHE_CHECK_REQUIRED')
   fact_before=fact_path.read_bytes();registry=json.loads(fact_before)
  else:
   # Bootstrap only once from the already validated publication, not future manual edits.
   registry={'schema':1,'notes':[n for n in value.get('reviewed_source_notes',[])if isinstance(n,dict)and n.get('kind')=='ASSESSMENT_DOCUMENT']}
  retained=retained_assessment_facts(value,registry)
 if notes.exists():
  if notes.is_symlink()or notes.stat().st_size>1024*1024:raise ValueError('REVIEWED_NOTES_CHECK_REQUIRED')
  manual=reviewed_snapshot(value,json.loads(notes.read_bytes()))
  manual_notes=manual.get('reviewed_source_notes',[]);manual_keys={(n['id'],n['kind'])for n in manual_notes}
  # Current manual corrections take precedence; they never become automatic cache entries.
  value=reviewed_snapshot(value,{'schema':1,'notes':[n for n in retained if(n['id'],n['kind'])not in manual_keys]+manual_notes})
 elif canonical:value=reviewed_snapshot(value,{'schema':1,'notes':retained})
 if canonical:
  from risk_document_facts import augment
  value,_fact_status=augment(value)
  # Apply the same typed metadata checks to extraction and manual review.
  if value.get('reviewed_source_notes'):value=reviewed_snapshot(value,{'schema':1,'notes':value['reviewed_source_notes']})
 value={k:v for k,v in value.items()if k!='reviewed_source_references'}
 if references.exists():
  catalog=root/'site-catalog.json'
  if references.is_symlink()or references.stat().st_size>1024*1024 or catalog.is_symlink()or catalog.stat().st_size>2*1024*1024:raise ValueError('REVIEWED_REFERENCES_CHECK_REQUIRED')
  value=referenced_snapshot(value,json.loads(references.read_bytes()),json.loads(catalog.read_bytes()))
 prepared=json.dumps(value,ensure_ascii=False,indent=2).encode('utf8')
 cached={n['id']:n for n in retained if(n['id'],n['kind'])not in manual_keys} if fact_before is None else {n['id']:n for n in retained}
 if canonical:
  cached.update({n['id']:n for n in value.get('reviewed_source_notes',[])if n['kind']=='ASSESSMENT_DOCUMENT'and(n['id'],n['kind'])not in manual_keys})
 if prepared==raw:
  if canonical:save_assessment_facts(fact_path,list(cached.values()),fact_before)
  return raw
 temporary=p.with_name(p.name+'.'+uuid.uuid4().hex+'.reviewed')
 try:
  temporary.write_bytes(prepared)
  if p.read_bytes()!=raw:raise ValueError('SNAPSHOT_CHANGED_BEFORE_REVIEW_NOTES')
  os.replace(temporary,p)
  if canonical:save_assessment_facts(fact_path,list(cached.values()),fact_before)
 finally:
  if temporary.exists():temporary.unlink()
 return prepared

def publish():
 verify();p=ROOT/'dashboard.json';raw=prepared_snapshot(ROOT);value=json.loads(raw)
 assert value['schema']==1 and len(raw)<=20*1024*1024 and len(value['items'])<=50000,'SNAPSHOT_LIMIT'
 allowed={'id','category','month','team','site','site_code','sha256','size','first_seen','last_seen','state','filename','storage_filename'}
 assert all(set(r)<=allowed and re.fullmatch('[0-9a-f]{64}',r['id']) and re.fullmatch('[0-9a-f]{64}',r['sha256']) and not re.search(r'[\\/]',r['filename']) and ('storage_filename'not in r or (isinstance(r['storage_filename'],str)and r['storage_filename']==Path(r['filename']).stem+'_'+r['sha256'][:12]+Path(r['filename']).suffix)) for r in value['items']),'UNEXPECTED_SNAPSHOT_DATA'
 digest=hashlib.sha256(raw).hexdigest();name='/tmp/monthly-collection-'+digest+'.json'
 call(['scp',*OPTIONS,str(p),HOST+':'+name])
 script=r'''import hashlib,json,os,shutil
from pathlib import Path
from datetime import datetime
source=Path(SOURCE)
raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==DIGEST
value=json.loads(raw);root=Path('/srv/besma/monthly-collection');root.mkdir(exist_ok=True)
target=root/'current.json'
if target.exists():
 previous=json.loads(target.read_bytes());assert previous.get('generated_at') is None or datetime.fromisoformat(value['generated_at'])>=datetime.fromisoformat(previous['generated_at']),'OLD_GENERATION'
archive=root/('snapshot-'+DIGEST+'.json')
if not archive.exists():archive.write_bytes(raw);archive.chmod(0o640)
temp=root/('current-'+DIGEST+'.tmp');temp.write_bytes(raw);temp.chmod(0o640);os.replace(temp,target)
print(json.dumps({'state':'PUBLISHED','sha256':DIGEST,'files':len(value['items'])}))
'''.replace('SOURCE',repr(name)).replace('DIGEST',repr(digest))
 # Fixed script, fixed application directory. No shell-built file names from submitted documents.
 result=json.loads(call(['ssh',*OPTIONS,HOST,'sudo -n -u besma python3 -'],input=script))
 # Opinion point defaults are anonymous, independently verified metadata.
 try:
  from opinion_scoring import publish as publish_opinion_points
  result['opinion_points']=publish_opinion_points(ROOT,lambda script:json.loads(call(['ssh',*OPTIONS,HOST,'sudo -n -u besma python3 -'],input=script)))
 except Exception as error:
  result['opinion_points']={'published':False,'error':type(error).__name__}
  (ROOT/'opinion-score-receipt.json').write_text(json.dumps(result['opinion_points']),encoding='utf8')
 (ROOT/'server-receipt.json').write_text(json.dumps(result),encoding='utf8');return result
if __name__=='__main__':
 try:print(json.dumps(publish(),ensure_ascii=False))
 except Exception as e:print(json.dumps({'state':'NOT_PUBLISHED','error':type(e).__name__}));sys.exit(1)
