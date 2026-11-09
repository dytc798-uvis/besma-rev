"""Fixed Monday-morning PDF window; no field rendering or message sending."""
from datetime import datetime,timedelta,timezone
KST=timezone(timedelta(hours=9))
def local_now():return datetime.now(KST)
def window_open(now=None):
    now=(now or local_now()).astimezone(KST)
    return now.weekday()==0 and 4<=now.hour<12

def next_run(now=None):
    now=(now or local_now()).astimezone(KST);day=now.date();delta=(0-day.weekday())%7
    candidate=datetime.combine(day+timedelta(days=delta),datetime.min.time(),KST).replace(hour=4)
    if candidate<=now:candidate+=timedelta(days=7)
    return candidate.isoformat()

def prepare(db,store):
    if not window_open():return {'prepared':0,'skipped':0,'outside_window':True}
    from app.modules.safety_features.team_schedule_models import TeamScheduleItem
    from app.modules.users.models import User
    from fastapi import HTTPException
    from . import routes,signature_bundle,demo
    prepared=0;skipped=0
    rows=db.query(TeamScheduleItem).filter(TeamScheduleItem.source=='INSPECTION_PLAN',TeamScheduleItem.archived_at.is_(None)).all()
    for row in rows:
        if not window_open():break
        owner=db.get(User,row.assigned_user_id)
        if owner is None or not owner.is_active:continue
        period=str(row.scheduled_date.year)+('-H1'if row.scheduled_date.month<=6 else'-H2')
        today=local_now().date();current_period=str(today.year)+('-H1'if today.month<=6 else'-H2')
        if period!=current_period:continue
        try:
            selected,key=routes.selected(db,owner,row.public_id,period)
            if demo.is_demo(selected):continue
            p=signature_bundle.prepare(store,key,row,period,owner,routes.profile_for(db,row,key))
            if not p['eligible']:skipped+=1;continue
            if any(s['data']['inspection_date']>local_now().date().isoformat()for s in p['snapshots'].values()):continue
            signature_bundle.queue(store,key,owner,row,period,{'request_key':'weekly-'+p['fingerprint'][:48],'fingerprint':p['fingerprint'],'allow_incomplete':bool(p['missing'])},routes.profile_for(db,row,key));prepared+=1
        except (ValueError,KeyError,HTTPException):skipped+=1
    return {'prepared':prepared,'skipped':skipped,'outside_window':False}

def finalize(store):
    if not window_open():return {'finalized':0}
    import json
    from . import signature_bundle
    count=0
    for path in (store.root/'signature-bundles').glob('*.json'):
        if path.name.endswith('.result.json'):continue
        try:
            p=json.loads(path.read_text('utf8'))
            if len(p.get('jobs',[]))==4 and signature_bundle.status(store,p['context_id'],p['owner'],p['id'])['status']=='READY':count+=1
        except (OSError,ValueError,KeyError):continue
    return {'finalized':count}
