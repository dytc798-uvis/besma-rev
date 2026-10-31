"""Read-only NAVERWORKS intake metadata, separate from operational document records."""
from pathlib import Path
from datetime import datetime
import json,unicodedata
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
def overview(response:Response,month:str=Query(default='',pattern=r'^(|20\d{2}-(0[1-9]|1[0-2]))$'),category:str=Query(default='',max_length=24),team:str=Query(default='',max_length=10),q:str=Query(default='',max_length=100),offset:int=Query(default=0,ge=0,le=50000),binding:str=Query(default='',pattern=r'^(|linked|pending)$'),user=Depends(reader)):
 response.headers['Cache-Control']='no-store'
 value=load();quality=notes_by_id(value);rows=value['items']
 if category and category not in LABELS:raise HTTPException(422,'CATEGORY_NOT_REGISTERED')
 rows=[r for r in rows if (not month or r['month']==month) and (not category or r['category']==category) and (not team or r['team']==team) and (not q or search_key(q) in search_key(r['site']+' '+r['filename']))]
 binding_counts={'all':len(rows),'linked':sum(bool(r['site_code'])for r in rows),'pending':sum(not r['site_code']for r in rows)}
 if binding:rows=[r for r in rows if bool(r['site_code'])==(binding=='linked')]
 rows=sorted(rows,key=lambda x:(x['month'],x['first_seen'],x['id']),reverse=True)
 counts={key:sum(1 for r in rows if r['category']==key) for key in LABELS}
 # File count and site count are separate; no submission rate without a verified required-site list.
 return {'generated_at':value.get('generated_at'),'schedule':'매일 02:00 (한국시간)','state':value.get('collection_state','NAS_SAVED'),'review_count':value['review_count'],'count':len(rows),'site_count':len({r['site_code'] for r in rows if r['site_code']}),'binding_counts':binding_counts,'linked_file_count':sum(bool(r['site_code'])for r in rows),'pending_file_count':sum(not r['site_code']for r in rows),'categories':[{'key':key,'label':label,'count':counts[key]} for key,label in LABELS.items()],'months':sorted({r['month'] for r in value['items']},reverse=True),'quality_review_file_count':sum(r['id']in quality for r in rows),'items':[{**{k:r[k] for k in ('id','category','month','team','site','filename','first_seen','last_seen','state','size')},'quality_notes':quality.get(r['id'],[])} for r in rows[offset:offset+200]],'next_offset':offset+200 if offset+200<len(rows) else None}
