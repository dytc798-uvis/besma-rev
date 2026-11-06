"""Only verified opinion identities from existing collection receipts; no personal text."""
from pathlib import Path
from datetime import date
import json
from .catalog import period_value

def calculate(snapshot,site,period,counts):
    period_value(period)
    if not site or not counts.get('generated_at'):
        return {'state':'CHECK_REQUIRED','count':None,'score':None,'sources':[]}
    codes={c['code']for c in site.get('contracts',[{'code':site.get('code')}])}
    low=period[:4]+('-01-01'if period.endswith('H1')else'-07-01')
    high=period[:4]+('-06-30'if period.endswith('H1')else'-12-31')
    current={r['id']:r for r in snapshot.get('items',[])};seen=set();sources=[];pending=0
    for source in counts.get('sources',[]):
        row=current.get(source.get('id'))
        if source.get('site_code')not in codes or not low[:7]<=source.get('month','')<=high[:7]:continue
        if not row or row.get('state')!='SAVED' or row.get('site_code')!=source['site_code'] or row.get('sha256')!=source.get('sha256'):
            pending+=1;continue
        valid=0
        for item in source.get('opinions',[]):
            try:day=date.fromisoformat(item['day']).isoformat()
            except (ValueError,TypeError,KeyError):pending+=1;continue
            if low<=day<=high and item['id']not in seen:seen.add(item['id']);valid+=1
        sources.append({'id':row['id'],'filename':row['filename'],'month':row['month'],'count':valid})
    pending+=sum(1 for r in current.values()if r.get('site_code')in codes and low[:7]<=r.get('month','')<=high[:7] and r.get('category')=='opinions' and r['id']not in {s['id']for s in sources})
    count=len(seen)
    return {'state':'PARTIAL'if pending and sources else'AVAILABLE'if sources else'CHECK_REQUIRED','count':count if sources else None,'score':min(5,count)if sources else None,'max_score':5,'pending_sources':pending,'sources':sources,'generated_at':counts['generated_at']}

def for_plan(db,row,period):
    from . import monthly_sources
    path=Path('/srv/besma/monthly-collection/opinion-counts.json')
    try:counts=json.loads(path.read_text('utf8'))
    except (OSError,ValueError):counts={}
    return calculate(monthly_sources.monthly.load(),monthly_sources.site_for_plan(db,row),period,counts)
