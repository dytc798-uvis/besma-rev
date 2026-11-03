import pytest
from app.modules.work_requests import grounding

@pytest.mark.parametrize('text,query,count',[
 ('나스 최신 파일 3개만 보여줘','',3),
 ('제일 최근 수정된 파일 2개 알려줘','',2),
 ('NAS 최종 수정 문서 3개 찾아줘','',3),
 ('최신 위험성평가 자료 2개 보여줘','위험성평가',2),
 ('나스에서 최신의 안전관리계획서 파일 10개 조회','안전관리계획서',10),
 ('최신 변경된 자료 1개 이름 알려줘','',1),
 ('제일 최근에 갱신한 위험성평가 자료 2개 알려줘','위험성평가',2),
])
def test_latest_uses_bounded_authorized_metadata(text,query,count):
 assert grounding.recent_request(text)==dict(query=query,limit=count)
 calls=[]
 answer=grounding.answer({'kind':'QUESTION','body':text},lambda *a:calls.append(a) or {'status':'COMPLETED','reply':'synthetic'})
 assert answer['status']=='COMPLETED'
 assert calls==[('recent',count,query)] if query else calls==[('recent',count)]

@pytest.mark.parametrize('text',[
 '최신 파일 0개 보여줘','최신 파일 11개 보여줘','최신 파일 3개 2개 보여줘',
 '최신 위험성평가 내용 요약해줘','최신 파일 삭제해줘','최신 파일 정상익에게 보내줘',
 '최신 출역 자료 2개 보여줘','최신 파일 2개 수정해줘','PC 최신 파일 3개 보여줘',
 '최신 사고보고서 파일 2개 알려줘','최신 승인 문서 3개가 법적으로 유효한지 알려줘',
])
def test_content_actions_and_invalid_limits_keep_existing_route(text):
 if '사고보고서' in text:
  # Parsing a filename query does not grant content access; NAS policy filters it.
  assert grounding.recent_request(text)==dict(limit=2,query='사고보고서')
 else:assert grounding.recent_request(text) is None
