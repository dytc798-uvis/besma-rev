from pathlib import Path
import importlib.util,json,unicodedata
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('binding',R/'site_binding.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
def ck(value,label):
 assert value,label
 checks.append(label)
sites=[{'code':'26050','site':'[1.대우건설] 청라피크원푸르지오 전기설비공사'},
 {'code':'25044','site':'[1.라온건설] 덕소2구역 주택재개발 정비사업'},
 {'code':'26027','site':'[1.진흥기업] 여수 학동 주상복합 신축공사 전기 및 소방공사'},
 {'code':'25055','site':'[1.진흥기업] 여수 학동 주상복합 신축공사 임시전력공사'},
 {'code':'25023','site':'[2.한양] 평택브레인시티8BL 공동주택 신축공사'}]
for text,code in [('청라 피크원 푸르지오 현장/테마점검.pdf','26050'),('[라온건설]덕소2구역 교육.pdf','25044'),('평택 브레인시티8BL 위험성평가.pdf','25023'),('여수 학동 주상복합 신축공사 임시전력공사 교육.pdf','25055'),('여수 학동 주상복합 신축공사 전기 및 소방공사 교육.pdf','26027'),('25044 자료.pdf','25044')]:
 ck(m.bind(text,sites).get('code')==code,'Exact normalized project '+text)
for text in ['진흥기업 여수학동주상복합 신축공사_테마.pdf','여수 학동 주상복합 자료.pdf']:
 ck(m.bind(text,sites)['state']=='AMBIGUOUS','Other contract remains ambiguous '+text)
for text in ['덕소2구역 교육.pdf','[대우건설]덕소2구역 교육.pdf','평택브레인시티18BL 교육.pdf','평택브레인시티9BL 교육.pdf','청라 푸르지오 교육.pdf']:
 ck(m.bind(text,sites)['state']=='UNMATCHED','No guessed short name or block '+text)
ck(m.bind('25044 청라피크원푸르지오 자료.pdf',sites)['state']=='AMBIGUOUS','Code and normalized name conflict')
ck(m.bind('25044 26050 자료.pdf',sites)['state']=='AMBIGUOUS','Multiple explicit codes')
ck(m.bind(unicodedata.normalize('NFD','청라 피크원 푸르지오 현장/교육.pdf'),sites).get('code')=='26050','Unicode normalization')
same=sites+[{'code':'SITE002','site':'[1.대우건설] 청라피크원푸르지오 전기설비공사'}]
ck(m.bind('청라피크원푸르지오 교육.pdf',same)['state']=='AMBIGUOUS','Legacy duplicate code is not collapsed')
units=[{'code':'26001','site':'[2.한양] 평택브레인시티8BL 공동주택 신축공사(1공구)'},{'code':'26002','site':'[2.한양] 평택브레인시티8BL 공동주택 신축공사(2공구)'}]
ck(m.bind('평택브레인시티8BL 교육.pdf',units)['state']=='AMBIGUOUS','Missing work-unit designation')

print(json.dumps({'passed':True,'conditions':len(checks)}))
