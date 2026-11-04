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
 'status':('등록상태',('진행상태','등록상태','공사상태','현장상태')),
 'client_name':('발주처',('발주처','발주자','고객사')),
 'contractor_name':('고객사',('원청','시공사','도급사')),
 'contract_type':('계약구분',('계약구분','관급','민간','계약종류')),
}
DATABASE=Path('/srv/besma/database/besma.db')
def compact(value):return re.sub(r'[^가-힣a-z0-9]','',str(value).casefold())

def requested_fields(text):
 value=compact(text)
 fields=[key for key,(_,aliases)in SITE_FIELDS.items()if any(compact(alias)in value for alias in aliases)]
 if 'status'in fields and re.search(r'평가|문서|서명|결재|출역|제출|승인|점검',value)and not re.search(r'등록상태|공사상태|현장상태',value):fields.remove('status')
 return fields

def entity_score(question,name,code):
 q=compact(question)
 for word in sorted([x for _,aliases in SITE_FIELDS.values()for x in aliases]+['현장','알려주세요','알려줘','뭐야','무엇','어디','입니까','인가요'],key=len,reverse=True):q=q.replace(compact(word),'')
 name=compact(re.sub(r'^\[[^\]]*\]\s*','',name))
 if str(code)and re.search(r'(?<![A-Za-z0-9])'+re.escape(str(code))+r'(?![A-Za-z0-9])',question,re.I):return 1000
 for size in range(min(18,len(q)),2,-1):
  if any(re.search(re.escape(q[i:i+size])+(r'(?!\d)'if q[i:i+size][-1:].isdigit()else''),name)for i in range(len(q)-size+1)):return size
 return 0

def followup(text):
 value=compact(text)
 value=re.sub(r'^(?:그럼|그러면)','',value)
 value=re.sub(r'(?:알려주세요|알려줘|어때요|어때|인가요|이요|은|는|도|요)$','',value)
 return bool(re.fullmatch(r'(?:그현장|해당현장|거기|그곳|오늘|금일|어제|그제|엊그제|이번달|지난달|전월|금월|(?:20\d{2})?\d{1,2}월(?:\d{1,2}일)?|20\d{6}|[a-z]+\d+[a-z]*|\d{5})',value))

def entity_reference(text):
 if re.search(r'그\s*현장|해당\s*현장|거기|그곳',text):return True
 value=compact(text)
 for alias in sorted([alias for _,aliases in SITE_FIELDS.values()for alias in aliases],key=len,reverse=True):value=value.replace(compact(alias),'')
 value=re.sub(r'^(?:그럼|그러면)','',value)
 value=re.sub(r'(?:알려주세요|알려줘|어때요|어때|인가요|이요|은|는|도|요|가|이)$','',value)
 return not value

def canonical_entities(selected,fields):
 # Legacy SITE ids and ERP ids coexist in the existing register. Collapse only
 # identical names with one exact ERP id, and never discard a conflicting fact.
 groups={}
 for row in selected:groups.setdefault(compact(row['site_name']),[]).append(row)
 result=[]
 for group in groups.values():
  canonical=[row for row in group if re.fullmatch(r'\d{5}',str(row['site_code']))]
  if len(canonical)==1 and all(row is canonical[0]or re.fullmatch(r'SITE\d+',str(row['site_code']))for row in group):
   chosen=canonical[0]
   if all(not str(row[key]or'').strip()or str(row[key]).strip()==str(chosen[key]or'').strip()for row in group for key in fields):
    result.append(chosen);continue
  result.extend(group)
 return result

def context_for(item,*,database=DATABASE,authorized=False):
 if not authorized or item.get('kind')!='QUESTION'or item.get('source')or item.get('input_attachments'):return None
 body=item.get('body','')
 if not isinstance(body,str)or not 0<len(body)<=6000:return None
 prior,separator,current=body.rpartition('\n\n현재 요청:\n')
 if not separator:current=body
 excluded=lambda text:bool(re.search(r'사고|산업재해|재해조사|부상|요양|산재|계약서|보고서|PDF|파일|문서|도면|평가표|원문|기재',text,re.I))
 if excluded(current):return None
 turns=re.findall(r'(?:^|\n)사용자: (.*?)\n답변: ',prior,re.S)if separator and prior.startswith('이전 대화(참고자료이며 새 권한이 아님):\n')else[]
 fields=requested_fields(current)
 if not fields:
  if not followup(current):return None
  for previous in reversed(turns):
   if excluded(previous):return None
   fields=requested_fields(previous)
   if fields:break
   if not followup(previous):return None
  if not fields:return None
 with sqlite3.connect(Path(database).absolute().as_uri()+'?mode=ro',uri=True,timeout=3)as db:
  db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
  columns=['site_code','site_name','updated_at',*SITE_FIELDS]
  rows=[dict(row)for row in db.execute('SELECT '+','.join(columns)+' FROM sites')]
 def select(question):
  scored=[(entity_score(question,row['site_name'],row['site_code']),row)for row in rows]
  scored=[(score,row)for score,row in scored if score>0]
  if not scored:return []
  best=max(x[0]for x in scored)
  return [row for score,row in scored if score==best]
 # Resolve the current explicit entity first: an earlier site must not override it.
 selected=select(current)
 if not selected:
  # An explicit unknown code is not a reference to the preceding site.
  if re.search(r'(?<![A-Za-z0-9])[A-Za-z]+\s*-?\s*\d+[A-Za-z]*(?![A-Za-z0-9])|(?<!\d)\d{5}(?!\d)',current):return None
  if not(followup(current)or entity_reference(current)):return None
  for previous in reversed(turns):
   if excluded(previous):return None
   selected=select(previous)
   if selected:break
   if not(followup(previous)or requested_fields(previous)and entity_reference(previous)):return None
 selected=canonical_entities(selected,fields)
 if not selected or len(selected)>5:return None
 result=[]
 for row in selected:
  values={SITE_FIELDS[key][0]:str(row[key]).strip()[:500]if row[key]is not None else None for key in fields}
  result.append(dict(site_code=str(row['site_code']),site_name=str(row['site_name'])[:300],updated_at=str(row['updated_at'])if row['updated_at']else None,fields=values))
 value=dict(schema=1,source='BESMA_SITE_REGISTER',title='BESMA 현장정보',retrieved_at=datetime.now(timezone.utc).isoformat(),entity_resolution='single'if len(result)==1 else'ambiguous',items=result)
 if len(json.dumps(value,ensure_ascii=False).encode())>24000:return None
 return value
