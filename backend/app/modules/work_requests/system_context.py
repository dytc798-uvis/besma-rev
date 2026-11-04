"""Read existing operational fields before treating a question as a file search.

The registry describes data sources and fields, not individual user questions.
Only the existing authorized requester can obtain a bounded projection.
"""
from datetime import datetime,timezone
from pathlib import Path
import json,re,sqlite3

SITE_FIELDS={
 'site_manager':('현장소장',('현장소장','소장','현장책임자')),
 'project_manager':('담당자',('담당자','담당','공무')),
 'phone_number':('현장정보 연락처',('전화번호','연락처','전화','내선','휴대폰','핸드폰','연락')),
 'address':('현장주소',('주소','위치','어디에')),
 'start_date':('착공일',('착공일','착공','시작일')),
 'end_date':('준공예정일',('준공예정일','준공일','준공','종료일')),
 'status':('등록상태',('진행상태','등록상태','상태')),
 'client_name':('발주처',('발주처','발주자','고객사')),
 'contractor_name':('고객사',('원청','시공사','도급사')),
 'contract_type':('계약구분',('계약구분','관급','민간','계약종류')),
}
DATABASE=Path('/srv/besma/database/besma.db')
def compact(value):return re.sub(r'[^가-힣a-z0-9]','',str(value).casefold())

def requested_fields(text):
 value=compact(text)
 return [key for key,(_,aliases)in SITE_FIELDS.items()if any(compact(alias)in value for alias in aliases)]

def entity_score(question,name,code):
 q=compact(question)
 for word in sorted([x for _,aliases in SITE_FIELDS.values()for x in aliases]+['현장','알려주세요','알려줘','뭐야','무엇','어디','입니까','인가요'],key=len,reverse=True):q=q.replace(compact(word),'')
 name=compact(re.sub(r'^\[[^\]]*\]\s*','',name))
 if str(code)and str(code)in q:return 1000
 for size in range(min(18,len(q)),2,-1):
  if any(q[i:i+size]in name for i in range(len(q)-size+1)):return size
 return 0

def context_for(item,*,database=DATABASE,authorized=False):
 if not authorized or item.get('kind')!='QUESTION'or item.get('source')or item.get('input_attachments'):return None
 body=item.get('body','')
 if not isinstance(body,str)or not 0<len(body)<=6000:return None
 prior,separator,current=body.rpartition('\n\n현재 요청:\n')
 if not separator:current=body
 # Accident details keep their separate existing permission/workflow.
 if re.search(r'사고|산업재해|재해조사|부상|요양|산재',current):return None
 fields=requested_fields(current)
 if not fields:return None
 if re.search(r'계약서|보고서|PDF|파일|문서|도면|평가표|원문|기재',current,re.I):return None
 question=current
 if separator and re.search(r'그\s*현장|해당\s*현장|거기|그곳',current):
  turns=re.findall(r'(?:^|\n)사용자: (.*?)\n답변: ',prior,re.S)
  if turns:question=turns[-1]+' '+current
 with sqlite3.connect(Path(database).absolute().as_uri()+'?mode=ro',uri=True,timeout=3)as db:
  db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
  columns=['site_code','site_name','updated_at',*SITE_FIELDS]
  rows=[dict(row)for row in db.execute('SELECT '+','.join(columns)+' FROM sites')]
 scored=[(entity_score(question,row['site_name'],row['site_code']),row)for row in rows]
 scored=[(score,row)for score,row in scored if score>0]
 if not scored:return None
 best=max(x[0]for x in scored);selected=[row for score,row in scored if score==best]
 if len(selected)>5:return None
 result=[]
 for row in selected:
  values={SITE_FIELDS[key][0]:str(row[key]).strip()[:500]if row[key]is not None else None for key in fields}
  result.append(dict(site_code=str(row['site_code']),site_name=str(row['site_name'])[:300],updated_at=str(row['updated_at'])if row['updated_at']else None,fields=values))
 value=dict(schema=1,source='BESMA_SITE_REGISTER',title='BESMA 현장정보',retrieved_at=datetime.now(timezone.utc).isoformat(),entity_resolution='single'if len(result)==1 else'ambiguous',items=result)
 if len(json.dumps(value,ensure_ascii=False).encode())>24000:return None
 return value
