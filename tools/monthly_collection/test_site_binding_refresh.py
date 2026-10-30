from pathlib import Path
import sys,importlib.util,tempfile,hashlib,json
from unittest.mock import patch
R=Path(__file__).resolve().parent;P=R;sys.path.insert(0,str(P));sys.path.insert(0,str(R/'source'))
spec=importlib.util.spec_from_file_location('candidate_collection',R/'collection.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
import search_refresh
checks=[]
for failed in [False,True]:
 with tempfile.TemporaryDirectory(dir=Path("D:/JSI/work"),prefix="monthly-refresh-test-")as tmp:
  assert Path(tmp).resolve().is_relative_to(Path('D:/JSI/work').resolve());root=Path(tmp)/'state';nas=Path(tmp)/'nas';root.mkdir();nas.mkdir();p=nas/'청라 피크원 푸르지오 자료.pdf';p.write_bytes(b'original');digest=hashlib.sha256(p.read_bytes()).hexdigest()
  c=m.db(root);c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',('one','theme','2026-10','1팀',p.name,digest,8,'first','last',str(p),'','','SITE_REVIEW'));m.review(c,'SITE','one','현장 일치 확인 필요');c.commit();c.close()
  book={'target':str(nas/'월간자료 취합현황.xlsx'),'sha256':'a'*64,'changed_cells':1};m.prepare_evaluation=lambda *args:book
  with patch.object(search_refresh,'request',side_effect=OSError('isolated')if failed else None,return_value={'state':'QUEUED','job_id':'test'})as request:
   out=m.reconcile_sites(root,nas,[{'code':'26050','site':'[1.대우건설] 청라피크원푸르지오 전기설비공사'}])
  assert out['bound_files']==1 and out['opinions_or_scores_updated']is False
  assert request.call_args.args==([book],root,nas)
  assert out['search_refresh']['state']==('RETRY_PENDING'if failed else 'QUEUED')
  c=m.db(root);assert c.execute('SELECT site_code FROM files').fetchone()[0]=='26050';c.close();assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
  receipts=list((root/'receipts').glob('site-bindings-*.json'));assert len(receipts)==1 and json.loads(receipts[0].read_text('utf-8'))['search_refresh']==out['search_refresh']
  checks.append('Index request failure leaves received data intact and a retry receipt'if failed else'Updated workbook is handed to existing canonical search-refresh request')
assert search_refresh.request([],R,Path('D:/unapproved'))['state']=='TEST_ONLY'
checks.append('Isolated state cannot enqueue a production scan')
print(json.dumps({'passed':True,'conditions':len(checks)}))
