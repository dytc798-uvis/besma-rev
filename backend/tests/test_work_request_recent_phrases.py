import pytest
from app.modules.work_requests import grounding

@pytest.mark.parametrize('question,query,count',[
 ('나스 최근 파일 3개만 보여줘','',3),
 ('최근에 바뀐 파일 3개 알려줘','',3),
 ('NAS 최근 저장한 문서 3개만 찾아줘','',3),
 ('최근 갱신한 위험성평가 자료 2개 알려줘','위험성평가',2),
 ('최근 변경한 삼성 평가기준 파일 2개만 알려줘','삼성 평가기준',2),
 ('나스에서 최근 저장된 자료 1개만','',1),
 ('최근수정파일3개만 보여줘','',3),
 ('최근 변경관리 절차 파일 3개만','변경관리 절차',3),
 ('최근 저장공간 자료 3개','저장공간',3),
 ('최근 갱신계획 파일 2개','갱신계획',2),
])
def test_metadata_words_are_not_mistaken_for_filename_filters(question,query,count):
 assert grounding.recent_request(question)=={'query':query,'limit':count}
 calls=[]
 reply=grounding.answer({'kind':'QUESTION','body':question},lambda *args:calls.append(args)or{'status':'COMPLETED','reply':'허용된 메타데이터'})
 assert reply['status']=='COMPLETED'and calls==[('recent',count,query)if query else('recent',count)]

@pytest.mark.parametrize('question',[
 '최근 바뀐 파일 내용을 알려줘','최근 저장한 파일 3개만 정상익에게 보내줘',
 '최근 변경한 파일을 삭제해줘','최근 수정한 파일을 바꿔줘',
 '최근 갱신한 파일 0개만','최근 바뀐 파일 11개만','최근 저장한 파일 999개',
 'PC에서 최근 바뀐 파일 3개만','C드라이브 최근 수정한 파일 3개만',
 '최근 바뀐 파일과 사진을 비교해줘','최근 저장한 파일 3개, 문서 2개',
 '최근 저장한 출역인원 자료 3개만',
])
def test_other_work_and_scope_do_not_become_a_global_nas_list(question):
 assert grounding.recent_request(question)is None
 assert grounding.answer({'kind':'QUESTION','body':question},lambda *args:pytest.fail('Wrong NAS metadata route'))is None

