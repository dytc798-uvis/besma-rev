from pathlib import Path
from unittest.mock import MagicMock,patch
import importlib.util,json,sys,tempfile,unittest,types
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('intake_candidate',R/'collection.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
import search_refresh
class LinkTests(unittest.TestCase):
 def run_ingest(self,state='NAS_SAVED',publication_error=False,refresh_error=False):
  with tempfile.TemporaryDirectory(dir=R)as tmp:
   root=Path(tmp);nas=root/'nas';nas.mkdir();c=MagicMock();order=[]
   def receive(*args):order.append('receipt_committed');return {'state':state,'files':[{'id':'fixture'}]}
   def refresh(books,called_root,called_nas):
    order.append('refresh');self.assertEqual(books,[]);self.assertEqual(called_root,root);self.assertEqual(called_nas,nas)
    if refresh_error:raise OSError('fixture')
    return {'state':'QUEUED','id':'fixture'}
   def publish():
    order.append('metadata')
    if publication_error:raise OSError('fixture')
    return {'state':'PUBLISHED'}
   with patch.object(m,'NAS',nas),patch.object(m,'db',return_value=c),patch.object(m,'_ingest',side_effect=receive),patch.object(m,'snapshot',return_value={}),patch.object(search_refresh,'request',side_effect=refresh)as callback,patch.dict(sys.modules,{'publish_server':types.SimpleNamespace(publish=publish)}):
    result=m.ingest(root,root/'fixture.json',nas)
   return result,order,callback.call_count
 def test_receipted_files_queue_before_whole_workbook_publish(self):
  result,order,calls=self.run_ingest();self.assertEqual(result['search_refresh']['state'],'QUEUED');self.assertEqual(order,['receipt_committed','metadata','refresh']);self.assertEqual(calls,1)
 def test_monthly_metadata_failure_does_not_block_NAS_search(self):
  result,order,calls=self.run_ingest(publication_error=True);self.assertEqual(result['server']['state'],'NOT_PUBLISHED');self.assertEqual(result['search_refresh']['state'],'QUEUED');self.assertEqual(calls,1)
 def test_search_failure_keeps_received_state(self):
  result,_,_=self.run_ingest(refresh_error=True);self.assertEqual(result['state'],'NAS_SAVED');self.assertEqual(result['search_refresh']['state'],'RETRY_PENDING')
 def test_unverified_archive_does_not_queue(self):
  result,_,calls=self.run_ingest(state='ARCHIVE_REVIEW');self.assertEqual(calls,0);self.assertNotIn('search_refresh',result)
if __name__=='__main__':unittest.main(verbosity=2)
