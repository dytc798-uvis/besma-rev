from pathlib import Path
from types import SimpleNamespace
import datetime as dt,hashlib,importlib.util,json,sys,tempfile,unittest,shutil,contextlib
from unittest.mock import patch,MagicMock
R=Path(__file__).resolve().parent
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
s=module('candidate_search_refresh',R/'search_refresh.py')
sys.modules['search_refresh']=s
@contextlib.contextmanager
def fixture():
 root=Path(tempfile.mkdtemp(dir=R))
 try:yield str(root)
 finally:
  assert root.resolve().is_relative_to(R.resolve())and root.resolve()!=R.resolve()
  shutil.rmtree('\\\\?\\'+str(root.resolve()))
class RefreshTests(unittest.TestCase):
 def row(self):return {'id':'f'*64,'path':r'Z:\4. 안전보건관리실\★월간 자료 취합\[1팀]\자료.pdf','size':4,'sha256':hashlib.sha256(b'data').hexdigest()}
 def st(self,size=4,at=20):return lambda _:SimpleNamespace(st_size=size,st_mtime_ns=at)
 def test_existing_unchanged_does_not_hash_or_queue(self):
  row=self.row();idx={s.key(row['path']):{'is_deleted':0,'file_size':4,'modified_at':'20'}}
  self.assertEqual(s.plan([row],idx,self.st(),lambda _:self.fail('unnecessary body read')),([],[]))
 def test_new_file_with_brackets_queues_exact_receipt(self):
  row=self.row();todo,review=s.plan([row],{},self.st(),lambda _:row['sha256'])
  self.assertEqual(todo,[{**row,'modified_at':'20'}]);self.assertEqual(review,[])
 def test_same_size_new_timestamp_rechecks_hash(self):
  row=self.row();idx={s.key(row['path']):{'is_deleted':0,'file_size':4,'modified_at':'19'}}
  self.assertEqual(len(s.plan([row],idx,self.st(),lambda _:row['sha256'])[0]),1)
 def test_user_changed_content_is_preserved(self):
  row=self.row();todo,review=s.plan([row],{},self.st(),lambda _:'0'*64)
  self.assertEqual(todo,[]);self.assertEqual(review[0]['reason'],'NAS_USER_CHANGE_PRESERVED')
 def test_missing_NAS_is_review_not_zero_success(self):
  def missing(_):raise FileNotFoundError()
  todo,review=s.plan([self.row()],{},missing,lambda _:self.fail('must not read'))
  self.assertFalse(todo);self.assertEqual(review[0]['reason'],'NAS_UNAVAILABLE')
 def test_deleted_index_entry_requires_new_scan(self):
  row=self.row();idx={s.key(row['path']):{'is_deleted':1,'file_size':4,'modified_at':'20'}}
  self.assertEqual(len(s.plan([row],idx,self.st(),lambda _:row['sha256'])[0]),1)
 def test_wrong_size_never_uses_receipt_to_overwrite(self):
  todo,review=s.plan([self.row()],{},self.st(5),lambda _:self.fail('size already differs'))
  self.assertFalse(todo);self.assertTrue(review)
 def test_test_root_does_not_launch(self):
  with fixture()as tmp,patch.object(s,'launch',side_effect=AssertionError('launch')):
   self.assertEqual(s.request([],Path(tmp),Path(tmp)),{'state':'TEST_ONLY'})
 def test_path_boundaries(self):
  self.assertFalse(s.allowed(r'Z:\4. 안전보건관리실\★월간 자료 취합2\bad.pdf'))
  self.assertFalse(s.allowed(r'Z:\4. 안전보건관리실\★월간 자료 취합\..\bad.pdf'))
  self.assertFalse(s.allowed(r'C:\bad.pdf'))
  self.assertFalse(s.allowed(r'Z:\4. 안전보건관리실\★월간 자료 취합\node_modules\bad.pdf'))
 def test_scan_completion_requires_exact_root_no_errors_and_fresh_generation(self):
  at=dt.datetime.now().astimezone();root={'root':s.ROOT,'status':'completed','errors':0,'scan_id':64}
  base={'operation':'index','state':'completed','started_at':at.isoformat(),'root_results':[root]}
  self.assertEqual(s.scan_result(base,at),64)
  for candidate in [{**base,'state':'running'},{**base,'operation':'repair'},{**base,'started_at':(at-dt.timedelta(days=1)).isoformat()},{**base,'root_results':[{**root,'errors':1}]},{**base,'root_results':[{**root,'root':r'Z:\1. 원가관리팀 - 현장 계약 및 원가'}]},{**base,'root_results':[root,root]}]:self.assertEqual(s.scan_result(candidate,at),0)
 def test_fingerprint_changes_only_with_exact_content_metadata(self):
  row={**self.row(),'modified_at':'20'}
  digest=lambda x:hashlib.sha256(json.dumps({'schema':1,'targets':x},sort_keys=True,separators=(',',':')).encode()).hexdigest()
  self.assertEqual(digest([row]),digest([dict(reversed(list(row.items())))]))
  self.assertNotEqual(digest([row]),digest([{**row,'modified_at':'21'}]))
 def test_publish_keeps_receipt_and_reports_search_state(self):
  m=module('candidate_collection',R/'collection.py')
  with fixture()as tmp:
   root=Path(tmp);book={'target':'fixture','sha256':'0'*64};c=MagicMock()
   with patch.object(m,'db',return_value=c),patch.object(m,'prepare_evaluation',return_value=book),patch.object(m,'prepare_opinions',return_value=book),patch.object(m,'snapshot',return_value={'review_count':1}),patch.object(m,'optimization_summary',return_value={'files':0}),patch.object(m,'optimization_enabled',return_value=False):
    result=m.publish(root,root/'nas')
    self.assertEqual(result['state'],'PUBLISHED');self.assertEqual(result['search_refresh']['state'],'TEST_ONLY');self.assertTrue((root/'status.json').exists())
 def test_search_failure_does_not_revoke_received_files(self):
  m=module('candidate_collection',R/'collection.py')
  with fixture()as tmp:
   root=Path(tmp);c=MagicMock()
   with patch.object(m,'db',return_value=c),patch.object(m,'prepare_evaluation',return_value={}),patch.object(m,'prepare_opinions',return_value={}),patch.object(m,'snapshot',return_value={'review_count':1}),patch.object(m,'optimization_summary',return_value={'files':0}),patch.object(m,'optimization_enabled',return_value=False),patch.object(s,'request',side_effect=OSError('offline')):
    result=m.publish(root,root/'nas')
    self.assertEqual(result['state'],'PUBLISHED');self.assertEqual(result['search_refresh']['state'],'RETRY_PENDING');self.assertTrue(result['search_refresh']['received_files_preserved'])
 def test_worker_uses_fixed_safety_scanner_then_existing_server_receipt(self):
  with fixture()as tmp:
   root=Path(tmp);(root/'search-refresh').mkdir();p=root/'source.pdf';p.write_bytes(b'data');st=p.stat()
   row={**self.row(),'path':str(p),'modified_at':str(st.st_mtime_ns)};job={'id':'a'*64,'targets':[row]}
   at=dt.datetime.now().astimezone();index=root/'index.json';sync=root/'sync.json'
   s.atomic(index,{'operation':'index','state':'completed','started_at':at.isoformat(),'root_results':[{'root':s.ROOT,'status':'completed','errors':0,'scan_id':64}]})
   s.atomic(sync,{'phase':'VERIFIED','scan_id':64,'server_session_id':'fixture','entry_count':2,'sha256':'b'*64})
   child=MagicMock();child.pid=12;child.wait.return_value=0
   with patch.object(s,'STATE',root),patch.object(s,'INDEX_STATUS',index),patch.object(s,'SYNC',sync),patch.object(s,'allowed',return_value=True),patch.object(s,'matching',side_effect=[False,True]),patch.object(s.subprocess,'Popen',return_value=child)as spawn:
    s.run_job(job)
    self.assertEqual(spawn.call_args.args[0][-2:],['--group','safety']);self.assertNotIn('shell',spawn.call_args.kwargs)
   self.assertEqual(s.load(root/'search-refresh/receipts'/('a'*64+'.json'))['phase'],'SEARCH_VERIFIED')
 def test_worker_changed_original_never_launches_scanner(self):
  with fixture()as tmp:
   root=Path(tmp);p=root/'source.pdf';p.write_bytes(b'user change');row={**self.row(),'path':str(p),'modified_at':str(p.stat().st_mtime_ns)}
   with patch.object(s,'STATE',root),patch.object(s,'allowed',return_value=True),patch.object(s.subprocess,'Popen',side_effect=AssertionError('scanner')):
    s.run_job({'id':'a'*64,'targets':[row]})
   self.assertEqual(s.load(root/'search-refresh/receipts'/('a'*64+'.json'))['phase'],'SOURCE_CHANGED_REVIEW_REQUIRED')
 def test_actual_long_path_hash_stat_and_receipt_keep_plain_keys(self):
  with fixture()as tmp:
   top=Path(tmp)/('long-folder-'*8);p=top/('nested-folder-'*5)/'source.pdf'
   try:
    Path(s.filesystem_path(p.parent)).mkdir(parents=True)
    Path(s.filesystem_path(p)).write_bytes(b'data')
    self.assertGreater(len(str(p)),260)
    row={**self.row(),'path':str(p)};todo,review=s.plan([row],{},s.stat_file,s.sha)
    self.assertEqual(todo[0]['path'],str(p));self.assertFalse(todo[0]['path'].startswith('\\\\?\\'));self.assertFalse(review)
    receipt=p.parent/('a'*64+'.json');s.atomic(receipt,{'sha256':row['sha256']});self.assertEqual(s.load(receipt)['sha256'],row['sha256'])
   finally:
    # Python's temporary-directory cleanup also needs the extended prefix for
    # a long descendant. Verify the absolute fixture boundary before removal.
    assert top.resolve().is_relative_to(R.resolve())and top.resolve()!=R.resolve()
    if top.exists():shutil.rmtree('\\\\?\\'+str(top.resolve()))
if __name__=='__main__':unittest.main(verbosity=2)
