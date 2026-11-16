"""Read-only map projection. A planned end date never proves completion."""
import json,re,datetime as dt
from pathlib import Path

def load_rows(path):
    try:
        p=Path(path)
        if p.is_symlink() or p.stat().st_size>500000:return {}
        data=json.loads(p.read_text(encoding='utf8'))
        if data.get('schema')!=1 or not isinstance(data.get('rows'),list) or not re.fullmatch('[0-9a-f]{64}',data.get('source_sha256','')):return {}
        received=dt.datetime.fromisoformat(data['received_at'])
        now=dt.datetime.now(dt.timezone.utc)
        if received.tzinfo is None or received>now+dt.timedelta(minutes=5):return {}
        rows={}
        for row in data['rows']:
            if not re.fullmatch(r'\d{5}',row.get('code','')) or row['code'] in rows or not isinstance(row.get('site'),str):return {}
            rows[row['code']]={**row,'received_at':data['received_at']}
        return rows
    except (OSError,ValueError,KeyError,TypeError):return {}

def period_end(value):
    matches=re.findall(r'20\d{2}-\d{2}-\d{2}',str(value or ''))
    try:return dt.date.fromisoformat(matches[-1]).isoformat() if len(matches)==2 else None
    except ValueError:return None

def merge_directory(data,path):
    rows=load_rows(path);aliases=data.get('aliases',{});existing={s['code'] for s in data['sites']}
    # New metadata contains no inferred coordinates, contacts, approval or score.
    for code,row in rows.items():
        canonical=aliases.get(code,code)
        if canonical not in existing:
            data['sites'].append({'code':canonical,'name':row['site'],'erp':{'period':row.get('period','')},'contacts':[]})
            existing.add(canonical)
    return data

def lifecycle(site,db_row,master,today,in_existing_scope=False,has_attendance=False):
    day=dt.date.fromisoformat(today);status=str(db_row.get('status')or'').strip().upper()
    source_status=str((master or{}).get('status')or'').strip().upper()
    confirmed=status in {'COMPLETED','CLOSED'} or source_status in {'COMPLETED','CLOSED','준공완료','준공확정'}
    end=period_end((master or{}).get('period'))
    if end is None:
        raw=db_row.get('end_date')
        try:end=dt.date.fromisoformat(str(raw)).isoformat() if raw else None
        except ValueError:pass
    if end is None:
        candidates=[period_end('2000-01-01 ~ '+str(c.get('end','')))for c in site.get('contracts',[])]
        end=max((d for d in candidates if d),default=None)
    current_period=bool(master and end and end>=today)
    display=not confirmed and status not in {'INACTIVE','TEST','LAB'} and bool(in_existing_scope or status=='ACTIVE' or has_attendance or current_period)
    handover=display and end is not None and dt.date.fromisoformat(end)<=day+dt.timedelta(days=30)
    return {'display':display,'completion_confirmed':confirmed,'planned_end_date':end,'document_handover':bool(handover),'received_at':(master or{}).get('received_at')}
