from pathlib import Path
import importlib.util,json
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('grounding_candidate',R.parent/'backend/app/modules/work_requests/grounding.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
positive=['방금 찾은 파일의 이름을 알려줘.','방금 받은 파일 이름이 뭐야?','아까 그 자료의 이름은?','그 문서 명칭을 알려줘.','직전 파일명 확인','그 파일은 무슨 이름이야?']
negative=['방금 만든 파일에 적힌 자료 종류는 몇 가지야? 이름도 알려줘.','방금 받은 파일의 항목 이름을 알려줘.','그 문서 안에 나오는 파일명을 설명해줘.','그 자료에 기재된 업체 이름은?','이 파일의 내용과 이름을 알려줘.','방금 받은 파일을 요약해줘.','방금 파일의 이름을 바꾸고 내용을 수정해줘.','방금 만든 파일에 있는 자료명 목록은?','이 문서의 표에 적힌 이름은?']
checks=[]
def ck(name,value):
 assert value,name
 checks.append(name)
for s in positive:ck('explicit filename: '+s,g.file_name_question(s))
for s in negative:
 ck('content is not filename: '+s,not g.file_name_question(s))
 ck('content passes through: '+s,g.answer({'kind':'QUESTION','body':s},lambda *a:(_ for _ in()).throw(AssertionError('UNEXPECTED_NAS_METADATA')),lambda:(_ for _ in()).throw(AssertionError('UNEXPECTED_FILENAME_CALLBACK')))is None)
ck('metadata-only filename answer remains',g.answer({'kind':'QUESTION','body':positive[0]},lambda *a:None,lambda:['원본.txt'])['reply']=='방금 제공한 파일은 ‘원본.txt’입니다.')
ck('missing filename is not invented',g.answer({'kind':'QUESTION','body':positive[0]},lambda *a:None,lambda:[])['status']=='NEEDS_INFO')
ck('current request overrides historical filename question',not g.file_name_question(g.current_text(positive[0]+'\n\n현재 요청:\n'+negative[0])))
ck('other kinds retain legacy path',g.answer({'kind':'FILE','body':positive[0]},lambda *a:None,lambda:['原本'])is None)
ck('explicit source retains source path',g.answer({'kind':'QUESTION','body':positive[0],'source':{'file_name':'原本'}},lambda *a:None,lambda:['原本'])is None)
result={'passed':True,'conditions':len(checks),'checks':checks,'pure_routing_only':True,'production_requests':0};print(json.dumps({'passed':True,'conditions':len(checks)}))
