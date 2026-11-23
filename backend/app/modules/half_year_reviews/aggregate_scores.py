"""Read-only composite scores from saved evaluations and verified monthly receipts."""
from decimal import Decimal,ROUND_HALF_UP
from contextlib import closing
from pathlib import Path
import json,sqlite3,re
from .catalog import CATALOG,context_key
from .supervisor_group import project_data,subject

def rounded(value,places=2):return float(Decimal(str(value)).quantize(Decimal('1').scaleb(-places),rounding=ROUND_HALF_UP))
def points(q,value):
 if value is None:return None
 if type(value)in {int,float}:return value
 return q['max_score']*{'EXCELLENT':1,'NORMAL':.5,'POOR':0}[value]

def saved(data,kind):
 if kind=='supervisor':key=kind+':'+subject(data)['id'];items=[data.get('assessments',{}).get(key,{})]
 else:items=[v for k,v in data.get('assessments',{}).items()if k.startswith(kind+':')]
 available=[v for v in items if v.get('draft') or v.get('completed')]
 if not available:return None,False
 record=max(available,key=lambda r:(r.get('draft')or r.get('completed'))['at'])
 latest=record.get('draft')or record['completed']
 return latest,bool(record.get('completed') and record.get('draft',{}).get('data')==record['completed']['data'])

def confirmation_status(data):
 confirmation=data.get('score_confirmation')or{};snapshots=confirmation.get('snapshot_ids')or{}
 if confirmation.get('status')not in {'CONFIRMED','PARTIAL'}or {k.split(':')[0]for k in snapshots}!={'report','law','manager','supervisor'}:return None
 source=confirmation.get('file',{})
 if not any(f.get('id')==source.get('id')and f.get('sha256')==source.get('sha256')and f.get('extension')=='.pdf'for f in data.get('files',[])):return None
 for key,sid in snapshots.items():
  record=data.get('assessments',{}).get(key,{})
  if record.get('completed',{}).get('id')!=sid or record.get('draft',{}).get('data')!=record.get('completed',{}).get('data'):return None
 return confirmation['status']

ADJUSTMENT_COLUMNS = (
 ('prior_year_grade','직전년도 평가등급','가점',1,3),
 ('near_miss_sharing','아차사고사례 공유','가점',2,10),
 ('contractor_award','도급사 안전포상','가점',3,10),
 ('upload_delay','업로드 지연','감점',1,2),
 ('late_reporting','지연보고','감점',3,10),
 ('accident_concealment','사고은폐','감점',30,30),
)

def adjustments(record=None):
 record=record or {};values=record.get('values',{})
 if set(values)-{r[0] for r in ADJUSTMENT_COLUMNS}:raise ValueError('ADJUSTMENT_CATEGORY_INVALID')
 items=[]
 for key,label,kind,minimum,maximum in ADJUSTMENT_COLUMNS:
  value=values.get(key)
  if value is not None and (type(value)not in {int,float} or not __import__('math').isfinite(value) or value<0):raise ValueError('ADJUSTMENT_VALUE_INVALID')
  items.append({'key':key,'label':label,'kind':kind,'value':value,'minimum':minimum,'maximum':maximum})
 bonus=rounded(sum(r['value'] or 0 for r in items if r['kind']=='가점'));deduction=rounded(sum(r['value'] or 0 for r in items if r['kind']=='감점'))
 return {'items':items,'bonus':bonus,'deduction':deduction,'net':rounded(bonus-deduction)}

def row_scores(data,monthly):
 data=project_data(data);scores={};states=[];headquarters_pending=False;has_grades=False
 for kind in ['report','manager','supervisor','law']:
  snap,unchanged=saved(data,kind);states.append(bool(snap and unchanged))
  if not snap:scores[kind]=None;continue
  answers=snap.get('data',{}).get('answers',{});schema=CATALOG['forms'][kind]['criteria']
  if kind=='law':
   values=[answers.get(q['id'],{}).get('value')for q in schema]
   yes=values.count('PASS');no=values.count('FAIL');na=values.count('NA');pending=len(values)-yes-no-na
   scores['law_counts']={'pass':yes,'fail':no,'na':na,'pending':pending}
   scores[kind]=rounded(yes/(len(values)-na)*20)if yes+no and len(values)>na else None
   has_grades=has_grades or bool(yes+no)
  else:
   values={q['id']:points(q,answers.get(q['id'],{}).get('value'))for q in schema}
   known=[v for v in values.values()if v is not None];has_grades=has_grades or bool(known)
   if kind=='manager':
    field=[v for k,v in values.items()if k!='m10' and v is not None]
    scores['manager_field']=sum(field)if field else None;scores['headquarters']=values.get('m10');headquarters_pending=values.get('m10')is None
   scores[kind]=rounded(sum(known)*({'report':.4,'manager':.2,'supervisor':.1}[kind]),0 if kind=='report'else 2)if known else None
 scores['monthly']=rounded(monthly['received']/monthly['required']*10,0)if monthly and monthly['required']else None
 adjusted=adjustments();all_written=all(states)
 components=[scores.get(k)for k in ['report','monthly','manager','supervisor','law']]
 scores['total']=rounded(sum(v for v in components if v is not None))if has_grades else None
 field=[scores.get(k)for k in ['report','monthly','supervisor','law']]+[scores.get('manager_field')*.2 if scores.get('manager_field')is not None else None]
 scores['field_total']=rounded(sum(v for v in field if v is not None))if has_grades else None
 reported=bool(data.get('paper_completion')or data.get('reported_completion'))
 state='평가 완료'if all_written else'법규 판정 확인'if data.get('paper_review_pending')else'완료·점수 미등록'if reported else'평가 중'if has_grades else'평가 전'
 confirmed=confirmation_status(data)if all_written else None
 if confirmed=='CONFIRMED':state='점수 확정'
 elif confirmed=='PARTIAL':state='법령점검표 서명 보완'
 from .signature_completion import completed as signatures_completed
 signed=signatures_completed(data)
 return {'signature_completed':signed,'signature_state':('서명 완료'if signed else'서명전')if has_grades else None,'provisional':bool(has_grades and (not all_written or not signed)),'scores':scores,'adjustments':adjusted,'state':state,'score_confirmed':confirmed=='CONFIRMED','written':all_written,'headquarters_pending':headquarters_pending,'monthly':{'received':monthly['received'],'required':monthly['required']}if monthly else None}

def rank(items,key,out):
 scores=[r['scores'][key]for r in items if r['scores'][key]is not None]
 for r in items:r[out]=1+sum(v>r['scores'][key]for v in scores)if r['scores'][key]is not None else None

def summary(store,rows,period,monthly_source):
 path=store.root/'reviews.sqlite3';states={}

 if path.exists():
  with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=10))as db:
   keys={context_key(r,period)for r in rows}
   for key,raw in db.execute('select id,data from contexts'):
    if key in keys:states[key]=json.loads(raw)
 items=[]
 for row in rows:
  key=context_key(row,period);monthly=monthly_source.get('sites',{}).get(key);items.append({'public_id':row.public_id,'site':row.title.removeprefix('[점검] ').strip(),**row_scores(states.get(key,{}),monthly)})
 rank(items,'total','rank');rank(items,'field_total','field_rank');items.sort(key=lambda r:(r['rank']is None,r['rank']or 0,r['site']))
 return {'period':period,'monthly_as_of':monthly_source.get('as_of'),'monthly_period':monthly_source.get('period_label'),'items':items,'counts':{'sites':len(items),'graded':sum(r['written']for r in items),'headquarters_pending':sum(r['headquarters_pending']for r in items),'total_scored':sum(r['scores']['total']is not None for r in items),'provisional':sum(r['provisional']for r in items)}}
