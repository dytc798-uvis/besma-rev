from pathlib import Path
import json,sqlite3,tempfile,unittest,datetime as dt
from review import analyse,review
NOW=dt.datetime(2026,10,30,5,30,tzinfo=dt.timezone(dt.timedelta(hours=9))).timestamp()
def row(n,body,reply,status='NEEDS_INFO',actor='a',**kw):return dict(id=f'{n:032x}',actor_key=actor,body=body,reply=reply,status=status,kind='QUESTION',created_at=NOW-600,updated_at=NOW-60,file_count=0,**kw)
def snapshot(*rows):return {'schema':1,'read_at':NOW,'complete':True,'total':len(rows),'rows':list(rows)}
def semantic(d,s):return {'reviewed_requests':len(d['rows']),'issues':[],'receipts':[]}
class RecoveryTests(unittest.TestCase):
 def test_later_success_replaces_candidate_without_editing_original(self):
  a=row(1,'이 PC에서 점검표.xlsx 파일 찾아줘','파일을 보내 주세요.')
  b=row(2,a['body'],'확인한 원본입니다.',status='COMPLETED');b['created_at']+=1;b['file_count']=1
  with tempfile.TemporaryDirectory(dir='D:/JSI/work')as tmp:
   state=Path(tmp)/'state';comm=Path(tmp)/'comm';review(state,comm,lambda:snapshot(a),lambda:NOW,semantic)
   c=sqlite3.connect(state/'review.sqlite3')
   try:c.execute("UPDATE findings SET state='VERIFIED_CANDIDATE'");c.commit()
   finally:c.close()
   result=review(state,comm,lambda:snapshot(a,b),lambda:NOW+86400,semantic)
   self.assertEqual(result['improvement_states'].get('LATER_RETRY_SUCCEEDED'),1)
   self.assertEqual(a['reply'],'파일을 보내 주세요.')
 def test_same_followup_in_other_conversation_does_not_resolve(self):
  a=row(1,'방금 찾은 파일의 이름을 알려줘.','파일을 보내 주세요.',conversation_id='a',parent_request_id='old')
  b=row(2,a['body'],'파일은 점검표.pdf입니다.',status='COMPLETED',conversation_id='b',parent_request_id='another');b['created_at']+=1
  result=analyse(snapshot(a,b),NOW);self.assertTrue(all(x['state']=='OPEN'for x in result['findings']))
 def test_direct_same_conversation_retry_can_resolve(self):
  a=row(1,'방금 찾은 파일의 이름을 알려줘.','파일을 보내 주세요.',conversation_id='a',parent_request_id='old')
  b=row(2,a['body'],'파일은 점검표.pdf입니다.',status='COMPLETED',conversation_id='a',parent_request_id=a['id']);b['created_at']+=1
  self.assertTrue(all(x['state']=='LATER_RETRY_SUCCEEDED'for x in analyse(snapshot(a,b),NOW)['findings']))
 def test_missing_context_or_pending_data_does_not_auto_close(self):
  a=row(1,'지금은 어때?','원본을 보내 주세요.')
  b=row(2,a['body'],'오늘 자료는 미수신입니다.',status='NEEDS_INFO');b['created_at']+=1
  self.assertTrue(all(x['state']=='OPEN'for x in analyse(snapshot(a,b),NOW)['findings']))
if __name__=='__main__':unittest.main(verbosity=2)
