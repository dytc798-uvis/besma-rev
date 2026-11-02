"""Read-only NAVERWORKS intake metadata, separate from operational document records."""
from pathlib import Path
from datetime import datetime
import json,re,unicodedata
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.core.auth import get_current_user
from .source_quality import notes_by_id

ROOT=Path('/srv/besma/monthly-collection')
router=APIRouter(prefix='/monthly-collection',tags=['monthly-collection'])
READ_ROLES={'HQ_SAFE','HQ_SAFE_ADMIN','SUPER_ADMIN'}
LABELS={'theme':'테마점검','legal-training':'법정교육','risk':'위험성평가','opinions':'근로자 의견청취','safety-cost':'산업안전보건관리비'}
def reader(user=Depends(get_current_user)):
 if str(getattr(user.role,'value',user.role)) not in READ_ROLES:raise HTTPException(403,'HQ_SAFETY_ONLY')
 return user
def search_key(value):
 return ''.join(unicodedata.normalize('NFC',value).casefold().split())

def storage_fields(row):
 if 'storage_filename'not in row:return {}
 name=row['storage_filename'];display=row.get('filename');digest=row.get('sha256')
 if not isinstance(name,str)or not 1<=len(name)<=600 or re.search(r'[\\/\x00-\x1f\x7f]',name)or not isinstance(display,str)or not isinstance(digest,str)or not re.fullmatch(r'[a-f0-9]{64}',digest):raise HTTPException(503,'취합자료 저장명을 확인해야 합니다.')
 expected=Path(display).stem+'_'+digest[:12]+Path(display).suffix
 if name!=expected:raise HTTPException(503,'취합자료 저장명을 확인해야 합니다.')
 return {'storage_filename':name}

def reviewed_references(snapshot):
 references=snapshot.get('reviewed_source_references',[])
 if not isinstance(references,list)or len(references)>1000:raise HTTPException(503,'공동 참고자료의 적용 범위를 확인해야 합니다.')
 seen=set()
 for reference in references:
  if not isinstance(reference,dict)or set(reference)!={'id','sha256','contracts'}or not isinstance(reference['id'],str)or not re.fullmatch('[a-f0-9]{64}',reference['id'])or not isinstance(reference['sha256'],str)or not re.fullmatch('[a-f0-9]{64}',reference['sha256'])or reference['id']in seen:raise HTTPException(503,'공동 참고자료의 수신 근거를 확인해야 합니다.')
  seen.add(reference['id']);contracts=reference['contracts']
  if not isinstance(contracts,list)or not 2<=len(contracts)<=8 or any(not isinstance(c,dict)or set(c)!={'code','name'}or not isinstance(c['code'],str)or not re.fullmatch('[A-Za-z0-9_-]{1,40}',c['code'])or not isinstance(c['name'],str)or not 1<=len(c['name'])<=500 or re.search(r'[\x00-\x1f\x7f]',c['name'])for c in contracts):raise HTTPException(503,'공동 참고자료의 계약 범위를 확인해야 합니다.')
  scope=[c['code']for c in contracts]
  if scope!=sorted(set(scope)):raise HTTPException(503,'공동 참고자료의 계약 범위를 확인해야 합니다.')
 return references

def reference_metadata(snapshot):
 index={r['id']:r for r in snapshot['items']};found={};pending=0
 for reference in reviewed_references(snapshot):
  row=index.get(reference['id'])
  if row is None:pending+=1;continue
  if row.get('sha256')!=reference['sha256']or row.get('site_code')or row.get('state')!='SITE_REVIEW':
   pending+=1;found[row['id']]={'reference_state':'CHECK_REQUIRED'};continue
  if row.get('category')not in LABELS or type(row.get('size'))is not int or row['size']<1 or not isinstance(row.get('filename'),str)or not 1<=len(row['filename'])<=260 or re.search(r'[\\/\x00-\x1f\x7f]',row['filename'])or not isinstance(row.get('month'),str)or not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])',row['month']):raise HTTPException(503,'공동 참고자료의 원본 정보를 확인해야 합니다.')
  found[row['id']]={'reference_only':True,'reference_state':'AVAILABLE','reference_contracts':reference['contracts']}
 return found,pending

def load():
 p=ROOT/'current.json'
 if not p.exists():return {'schema':1,'generated_at':None,'items':[],'review_count':0,'collection_state':'NOT_RECEIVED'}
 if p.is_symlink() or p.stat().st_size>20*1024*1024:raise HTTPException(503,'SNAPSHOT_CHECK_REQUIRED')
 try:
  value=json.loads(p.read_text(encoding='utf8'))
  if value['schema']!=1 or not isinstance(value['items'],list) or len(value['items'])>50000:raise ValueError()
  return value
 except (ValueError,KeyError,TypeError):raise HTTPException(503,'SNAPSHOT_CHECK_REQUIRED')
@router.get('/overview')
def overview(response:Response,month:str=Query(default='',pattern=r'^(|20\d{2}-(0[1-9]|1[0-2]))$'),category:str=Query(default='',max_length=24),team:str=Query(default='',max_length=10),q:str=Query(default='',max_length=100),offset:int=Query(default=0,ge=0,le=50000),binding:str=Query(default='',pattern=r'^(|linked|pending|shared)$'),quality:str=Query(default='',pattern=r'^(|review)$'),user=Depends(reader)):
 response.headers['Cache-Control']='no-store'
 value=load();quality_notes=notes_by_id(value);references,reference_pending=reference_metadata(value);rows=value['items']
 if category and category not in LABELS:raise HTTPException(422,'CATEGORY_NOT_REGISTERED')
 rows=[r for r in rows if (not month or r['month']==month) and (not category or r['category']==category) and (not team or r['team']==team) and (not q or search_key(q) in search_key(r['site']+' '+r['filename']+' '+' '.join(c['code']+' '+c['name']for c in references.get(r['id'],{}).get('reference_contracts',[]))))]
 binding_counts={'all':len(rows),'linked':sum(bool(r['site_code'])for r in rows),'pending':sum(not r['site_code']for r in rows),'shared':sum(references.get(r['id'],{}).get('reference_state')=='AVAILABLE'for r in rows)}
 if binding=='shared':rows=[r for r in rows if references.get(r['id'],{}).get('reference_state')=='AVAILABLE']
 elif binding:rows=[r for r in rows if bool(r['site_code'])==(binding=='linked')]
 quality_counts={'all':len(rows),'review':sum(r['id']in quality_notes for r in rows)}
 if quality=='review':rows=[r for r in rows if r['id']in quality_notes]
 rows=sorted(rows,key=lambda x:(x['month'],x['first_seen'],x['id']),reverse=True)
 counts={key:sum(1 for r in rows if r['category']==key) for key in LABELS}
 # File count and site count are separate; no submission rate without a verified required-site list.
 return {'reference_file_count':sum(references.get(r['id'],{}).get('reference_state')=='AVAILABLE'for r in rows)if rows or not reference_pending else None,'reference_pending_count':reference_pending,'generated_at':value.get('generated_at'),'schedule':'매일 02:00 (한국시간)','state':value.get('collection_state','NAS_SAVED'),'review_count':value['review_count'],'count':len(rows),'site_count':len({r['site_code'] for r in rows if r['site_code']}),'binding_counts':binding_counts,'linked_file_count':sum(bool(r['site_code'])for r in rows),'pending_file_count':sum(not r['site_code']for r in rows),'categories':[{'key':key,'label':label,'count':counts[key]} for key,label in LABELS.items()],'months':sorted({r['month'] for r in value['items']},reverse=True),'quality_counts':quality_counts,'quality_filter':quality,'quality_review_file_count':sum(r['id']in quality_notes for r in rows),'items':[{**{k:r[k] for k in ('id','category','month','team','site','filename','first_seen','last_seen','state','size')},**storage_fields(r),**references.get(r['id'],{}),'quality_notes':quality_notes.get(r['id'],[])} for r in rows[offset:offset+200]],'next_offset':offset+200 if offset+200<len(rows) else None}
