"""A running request may discover NAS metadata using its requester's permissions.

Selection reuses the existing OWN/SHARED/WAITING_REVIEW flow. It never publishes
content, reads private PC data, or converts the worker identity into a user grant.
"""
import hashlib,json,re
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from .store import Conflict
from .nas_sources import accident_source

class LookupLease(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
 lease:str=Field(pattern=r'^[0-9a-f]{64}$')
class LookupQuery(LookupLease):
 q:str=Field(min_length=1,max_length=100)
class LookupSelection(LookupLease):
 selection_id:str=Field(pattern=r'^[0-9a-f]{64}$')
 action:Literal['QUESTION','FIND','EDIT','CREATE']='QUESTION'
 output_format:Literal['TXT','PDF']='TXT'
 artifact_title:str|None=Field(default=None,min_length=1,max_length=80)

def install(router,worker,store,config,eligible,nas,result,call):
 def gate():
  cfg=config()
  if not cfg.source_lookup_enabled or not cfg.nas_files_enabled or nas is None:raise HTTPException(404,'자료 조회 연결을 준비하고 있습니다.')
 def requester(db,rid,lease):
  with db.connection()as connection:
   row=db._lease(connection,rid,lease)
   members={(x['id'],x['login_id']):bool(x['owner'])for x in eligible()}
   pair=row['user_id'],row['login_id']
   if pair not in members:raise Conflict('REQUESTER_ACCESS_REVOKED')
   from .input_images import for_request
   from .image_comparison import require_lookup
   require_lookup(config(),connection,row)
   if row['kind']!='QUESTION'or row['source_json']:raise Conflict('SOURCE_LOOKUP_NOT_APPLICABLE')
   actor={'id':pair[0],'login_id':pair[1],'owner':members[pair]}
  if not nas.member_valid(actor):raise Conflict('REQUESTER_SOURCE_ACCESS_REVOKED')
  return actor
 def search(db,actor,q,register):
  user=nas.load_user(actor);state=nas.search_state(user,q)
  if not isinstance(state.get('items'),list)or type(state.get('complete'))is not bool:raise ValueError('EXACT_METADATA_STATE_REQUIRED')
  items=[]
  for source in state['items'][:20]:
   if source.get('scope')!='TEAM_SAFETY_NAS'or source.get('logical_root_id')!='team-safety-nas-z4'or accident_source(source.get('relative_path','')):continue
   item={k:source[k]for k in ['file_name','relative_path','extension','size','modified_at']}
   if register:item.update(selection_id=db.register_selection(actor,source),source_sha256=db.source_digest(source))
   items.append(item)
  return {'source':'NAS','items':items,'complete':state['complete'],'unavailable_count':state.get('unavailable_count',0)}
 def state_of(db,rid):
  with db.connection()as connection:
   row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
   if row is None:raise KeyError('REQUEST_NOT_FOUND')
   return row_state(db,connection,row)
 def row_state(db,connection,row):
  value={'id':row['id'],'kind':row['kind'],'status':row['status'],'review_phase':row['review_phase'],'source_sha256':db.source_digest(json.loads(row['source_json']))if row['source_json']else None}
  from .source_generation import requested
  generation=requested(connection,row)
  if generation:value['source_generation_format']=generation
  if generation:value['artifact_title']=row['title']
  return value

 @router.post('/worker/{rid}/lookup-catalog')
 def lookup_catalog(rid:str,body:LookupLease,user=Depends(worker),db=Depends(store)):
  gate();actor=call(requester,db,rid,body.lease);items=[]
  from .image_comparison import inputs
  with db.connection()as connection:
   row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone();photo_context=bool(config().image_source_comparison_enabled and inputs(connection,row))
  categories=[('위험성평가',['위험성평가 데이터베이스']),('절차·지침',['절차서']),('고객사 평가기준',['평가기준','안전등급']),('서식',['양식']),('안전관리계획',['안전관리계획'])]
  if photo_context:categories[3]=('안전관계자 명부',['105 안전관리자 현황','105 선해임'])
  for category,queries in categories:
   pools=[];uncertain=False
   for q in queries:
    value=call(search,db,actor,q,False);uncertain|=not value['complete']
    rows=value['items']
    if category=='고객사 평가기준':
     rows=[r for r in rows if not any(v in re.sub(r'\s+','',r['file_name'])for v in ['품의','기안','청구서','견적서','정산서','영수증'])]
    pools.append(rows)
   examples=[];seen=set()
   for i in range(20):
    for pool in pools:
     if i>=len(pool):continue
     item=pool[i];key=item['relative_path']
     if key not in seen:seen.add(key);examples.append(item)
    if len(examples)>=3:break
   examples=examples[:3]
   if examples:
    hints=[]
    for item in examples:
     relative=item['relative_path'].replace('\\','/');parts=relative.split('/')
     if relative.startswith('/')or re.match(r'^[A-Za-z]:',relative)or any(p in {'.','..',''}for p in parts)or any(ord(c)<32 for c in relative):continue
     hints.append({'file_name':item['file_name'],'folder_hint':'/'.join(parts[:-1][-3:])[-240:],'root_label':'안전보건실 NAS'})
    items.append({'source':'NAS','category':category,'file_names':list(dict.fromkeys(x['file_name']for x in examples)),'file_hints':hints,'index_uncertain':uncertain})
  # Re-check the lease and account after external metadata queries, before returning.
  call(requester,db,rid,body.lease)
  return result({'items':items,'allowed_sources':['NAS'],'allowed_actions':['QUESTION','FIND','EDIT']+(['CREATE']if config().source_generation_enabled else[]),'generation_formats':['TXT','PDF']if config().source_generation_enabled else[],'edit_formats':['.txt','.docx']+(['.xlsx']if config().workbook_edit_enabled else[])})

 @router.post('/worker/{rid}/lookup-search')
 def lookup_search(rid:str,body:LookupQuery,user=Depends(worker),db=Depends(store)):
  gate();actor=call(requester,db,rid,body.lease);value=call(search,db,actor,body.q,True);call(requester,db,rid,body.lease);return result(value)

 def attach(db,rid,lease,selection_id,action,output_format,artifact_title):
  # Idempotent replay uses a receipt event bound to the original lease and selector.
  # The hash is never a new credential and no lease is placed in a URL.
  values=[rid,lease,selection_id]
  if action!='QUESTION':values.append(action)
  if action=='CREATE':values.extend([output_format,artifact_title])
  marker='LOOKUP_SOURCE_SELECTED:'+hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()
  with db.connection()as connection:
   old=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
   replay=old is not None and connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone()
  if replay:return state_of(db,rid)
  actor=requester(db,rid,lease)
  with db.connection()as connection:
   from .image_comparison import require_lookup
   image_row=db._lease(connection,rid,lease);require_lookup(config(),connection,image_row,action)
  source=db.selection(actor,selection_id);source=nas.validate(actor,source)
  if source.get('scope')!='TEAM_SAFETY_NAS'or source.get('logical_root_id')!='team-safety-nas-z4'or accident_source(source.get('relative_path','')):raise Conflict('SOURCE_NOT_ALLOWED')
  if action=='EDIT'and source.get('extension')=='.xlsx'and not config().workbook_edit_enabled:raise Conflict('WORKBOOK_EDIT_DISABLED')
  if action=='EDIT'and source.get('extension')not in{'.txt','.docx','.xlsx'}:raise ValueError('EDIT_COPY_FORMAT_REQUIRED')
  with db.connection()as connection,connection:
   connection.execute('BEGIN IMMEDIATE')
   # A concurrent retry may have completed after the first receipt check.
   if connection.execute('SELECT 1 FROM events WHERE request_id=? AND status=?',(rid,marker)).fetchone():
    row=connection.execute('SELECT * FROM requests WHERE id=?',(rid,)).fetchone()
    return row_state(db,connection,row)
   row=db._lease(connection,rid,lease)
   current={(x['id'],x['login_id']):bool(x['owner'])for x in eligible()};pair=row['user_id'],row['login_id']
   if pair not in current or row['kind']!='QUESTION'or row['source_json']:raise Conflict('REQUEST_CHANGED')
   from .image_comparison import require_lookup
   comparison_photos=require_lookup(config(),connection,row,action)
   if not nas.valid({'id':pair[0],'login_id':pair[1]},source):raise Conflict('SOURCE_CHANGED')
   if action=='EDIT'and source.get('extension')=='.xlsx'and not config().workbook_edit_enabled:raise Conflict('WORKBOOK_EDIT_DISABLED')
   title=row['title']
   if action=='CREATE'and artifact_title is not None:
    import unicodedata
    title=unicodedata.normalize('NFC',artifact_title).strip()
    if not title or any(ord(c)<32 for c in title):raise ValueError('DOCUMENT_TITLE_REQUIRED')
   kind='EDIT'if action=='EDIT'else'FILE'if action in {'CREATE','FIND'}else'QUESTION'
   phase='OWN'if current[pair]else'SHARED'if action in {'QUESTION','FIND'}and source.get('shared_file_id')and source.get('approved_content_sha256')else'WAITING_REVIEW'
   target='AWAITING_REVIEW'if phase=='WAITING_REVIEW'else'QUEUED'
   connection.execute('UPDATE requests SET kind=?,title=?,source_json=?,selection_id=?,status=?,review_phase=?,review_version=review_version+1,scope_exempt=?,updated_at=?,lease_hash=NULL,lease_until=NULL WHERE id=?',(kind,title,json.dumps(source,ensure_ascii=False,sort_keys=True),selection_id,target,phase,int(current[pair]),db.clock(),rid))
   if comparison_photos:db._event(connection,rid,'IMAGE_COMPARISON_BOUND')
   db._event(connection,rid,marker);db._event(connection,rid,'LOOKUP_ACTION_'+action+(':'+output_format if action=='CREATE'else''));db._event(connection,rid,target)
  return state_of(db,rid)

 @router.post('/worker/{rid}/lookup-select')
 def lookup_select(rid:str,body:LookupSelection,user=Depends(worker),db=Depends(store)):
  gate()
  if body.action=='CREATE'and not config().source_generation_enabled:raise HTTPException(404,'원문 기반 새 파일 작성을 준비하고 있습니다.')
  if body.action!='CREATE'and(body.output_format!='TXT'or body.artifact_title is not None):raise HTTPException(422,'새 파일의 제목과 형식을 확인해 주세요.')
  return result(call(attach,db,rid,body.lease,body.selection_id,body.action,body.output_format,body.artifact_title))

 @router.get('/worker/{rid}/lookup-state')
 def lookup_state(rid:str,user=Depends(worker),db=Depends(store)):
  gate();return result(call(state_of,db,rid))
