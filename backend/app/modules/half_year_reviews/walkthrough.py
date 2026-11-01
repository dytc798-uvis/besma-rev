"""Dated inspection evidence; no assessment answer or verdict inference."""
from datetime import date
from urllib.parse import urlsplit
import re,uuid,copy
from .catalog import EVIDENCE,FORMS,cleaned,Conflict

VERSION=1

def day_in_period(value,period):
    if not isinstance(value,str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',value):raise ValueError('WALK_DATE_INVALID')
    day=date.fromisoformat(value)
    if f'{day.year}-H{1 if day.month<=6 else 2}'!=period:raise ValueError('DATE_PERIOD_MISMATCH')
    return value

def run_for(data,run_id):
    if not isinstance(run_id,str)or not re.fullmatch('[a-f0-9]{32}',run_id):raise ValueError('WALK_RUN_INVALID')
    run=next((r for r in data.get('inspection_runs',[])if r['id']==run_id),None)
    if run is None:raise KeyError('WALK_RUN_MISSING')
    return run

def mutate(data,action,body,period,actor,name,stamp,context_meta):
    if action=='walk-start':
        if set(body)!={'inspection_date'}:raise ValueError('WALK_INVALID')
        day=day_in_period(body['inspection_date'],period)
        public_id=(context_meta or{}).get('public_id')
        if not isinstance(public_id,str)or not re.fullmatch(r'[a-f0-9-]{36}',public_id):raise ValueError('WALK_PLAN_REQUIRED')
        runs=data.setdefault('inspection_runs',[])
        old=next((r for r in runs if r['plan_id']==public_id and r['inspection_date']==day),None)
        if old:return {'inspection_run':old}
        if len(runs)>=120:raise ValueError('WALK_RUN_LIMIT')
        run={'id':uuid.uuid4().hex,'version':1,'plan_id':public_id,'inspection_date':day,'items':{},'created_by':name,'actor_id':actor,'created_at':stamp}
        runs.append(run);return {'inspection_run':run}
    if action=='walk-report':
        if set(body)-{'run_id','board_url','posted_confirmed','draft_text','meta','public_attachment_ids','public_review_confirmed','public_field_photos'}or not {'run_id','board_url','posted_confirmed','draft_text'}<=set(body)or type(body['posted_confirmed'])is not bool:raise ValueError('WALK_REPORT_INVALID')
        run=run_for(data,body['run_id'])
        if run['plan_id']!=(context_meta or{}).get('public_id'):raise ValueError('WALK_PLAN_MISMATCH')
        link=cleaned(body['board_url'],700);text=cleaned(body['draft_text'],4000)
        if link:
            u=urlsplit(link)
            if u.scheme!='https'or u.hostname!='board.worksmobile.com'or u.username or u.password or u.port or not re.fullmatch(r'/main/article/\d{1,30}/?',u.path):raise ValueError('WALK_REPORT_URL_INVALID')
        allowed={};public_forms={}
        for key,a in data['assessments'].items():
            form=key.split(':',1)[0];final=a.get('completed',{}).get('data',{})
            if form in {'manager','supervisor'}and final.get('walkthrough_run_id')==run['id']:
                for fid in final.get('signed_table_photo_ids',[]):allowed[fid]=form
        selected=body.get('public_attachment_ids',[]);reviewed=body.get('public_review_confirmed',False)
        if not isinstance(selected,list)or len(selected)>40 or any(not isinstance(fid,str)or fid not in allowed for fid in selected)or len(set(selected))!=len(selected)or type(reviewed)is not bool:raise ValueError('WALK_PUBLIC_ATTACHMENTS_INVALID')
        source_files={f['id']:f for f in data['files']}
        internal_ids={fid for key,a in data['assessments'].items()if key.split(':',1)[0]in {'report','law'}for fid in a.get('completed',{}).get('data',{}).get('signed_table_photo_ids',[])}
        internal_hashes={source_files[fid]['sha256']for fid in internal_ids if fid in source_files}
        eligible={p['file_id']for p in run.get('field_photos',[])if p['file_id']in source_files and source_files[p['file_id']]['kind']=='image'and source_files[p['file_id']]['evidence_id']!='paper_assessment'and source_files[p['file_id']]['sha256']not in internal_hashes}
        field_photos=body.get('public_field_photos',run.get('report',{}).get('public_field_photos',[]))
        if not isinstance(field_photos,list)or len(field_photos)>24:raise ValueError('WALK_PUBLIC_ATTACHMENTS_INVALID')
        seen=set();clean_field=[]
        for photo in field_photos:
            if not isinstance(photo,dict)or set(photo)!={'file_id','caption','reviewed'}or photo['file_id']not in eligible or photo['file_id']in seen or photo['reviewed']is not True:raise ValueError('WALK_PUBLIC_ATTACHMENTS_INVALID')
            seen.add(photo['file_id']);clean_field.append({'file_id':photo['file_id'],'caption':cleaned(photo['caption'],120),'reviewed':True})
        if body['posted_confirmed']:
            if not reviewed or {allowed[fid]for fid in selected}!={'manager','supervisor'}:raise ValueError('WALK_PUBLIC_REVIEW_REQUIRED')
            if not link:raise ValueError('WALK_REPORT_URL_REQUIRED')
            complete=set()
            for key,a in data['assessments'].items():
                draft=a.get('draft',{}).get('data',{});final=a.get('completed',{}).get('data',{})
                if draft.get('walkthrough_run_id')!=run['id']and final.get('walkthrough_run_id')!=run['id']:continue
                if draft!=final or final.get('walkthrough_run_id')!=run['id']or not final.get('signed_table_photo_ids')or not final.get('required_signatures_confirmed')or not final.get('signed_pages_complete'):raise ValueError('WALK_FOUR_FORMS_REQUIRED')
                complete.add(key.split(':',1)[0])
            if complete!=set(FORMS):raise ValueError('WALK_FOUR_FORMS_REQUIRED')
        meta=body.get('meta',run.get('report',{}).get('meta',{}))
        limits={'inspection_time':60,'place':100,'hq_attendees':200,'site_attendees':200,'public_summary':1000,'public_findings':1000}
        if not isinstance(meta,dict)or set(meta)-set(limits):raise ValueError('WALK_REPORT_INVALID')
        meta={key:cleaned(meta.get(key,''),limit)for key,limit in limits.items()}
        run['report']={'board_url':link,'posted_confirmed':body['posted_confirmed'],'draft_text':text,'meta':meta,'public_attachment_ids':selected,'public_field_photos':clean_field,'public_review_confirmed':reviewed,'state':'REPORTED_USER_CONFIRMED'if body['posted_confirmed']else'REPORT_PENDING','server_verified':False,'by':name,'actor_id':actor,'at':stamp}
        return {'inspection_run':run}
    if action!='walk-item'or set(body)!={'run_id','evidence_id','expected_version','entry'}:raise ValueError('WALK_INVALID')
    run=run_for(data,body['run_id'])
    if run['plan_id']!=(context_meta or{}).get('public_id'):raise ValueError('WALK_PLAN_MISMATCH')
    eid=body['evidence_id']
    if eid not in EVIDENCE or type(body['expected_version'])is not int:raise ValueError('WALK_INVALID')
    old=run['items'].get(eid,{})
    if body['expected_version']!=old.get('version',0):raise Conflict('WALK_ITEM_CHANGED')
    entry=body['entry']
    allowed={'status','note','risk','previous','today','action','owner','due','photos'}
    if not isinstance(entry,dict)or set(entry)-allowed:raise ValueError('WALK_INVALID')
    status=entry.get('status','PENDING')
    if status not in {'CONFIRMED','MISSING','PENDING','NA'}:raise ValueError('WALK_INVALID')
    clean={k:cleaned(entry.get(k,''),1000 if k=='note'else 500 if k in {'risk','previous','today','action'}else 40 if k=='owner'else 10)for k in allowed-{'status','photos'}}
    if status=='NA'and not clean['note']:raise ValueError('WALK_REASON_REQUIRED')
    if clean['due']:date.fromisoformat(clean['due'])
    photos=entry.get('photos',[])
    known={f['id']for f in data['files']if f['kind']=='image'}
    if not isinstance(photos,list)or len(photos)>24:raise ValueError('WALK_PHOTOS_INVALID')
    seen=set();links=[]
    for link in photos:
        if not isinstance(link,dict)or set(link)!={'id','stage'}or link['id']not in known or link['stage']not in {'BEFORE','AFTER','EVIDENCE'}or link['id']in seen:raise ValueError('WALK_PHOTOS_INVALID')
        seen.add(link['id']);links.append(dict(link))
    # Revisions/events preserve prior entries. Other runs and all assessment data are untouched.
    item={**clean,'status':status,'photos':links,'version':old.get('version',0)+1,'by':name,'actor_id':actor,'at':stamp}
    run['items'][eid]=item;run['updated_at']=stamp
    return {'inspection_run':run,'inspection_item':item}

def assessment_run(data,run_id,inspection_date,plan_id=None):
    if not run_id:return None
    run=run_for(data,run_id)
    if run['plan_id']!=plan_id:raise ValueError('WALK_PLAN_MISMATCH')
    if run['inspection_date']!=inspection_date:raise ValueError('WALK_DATE_MISMATCH')
    return copy.deepcopy(run)


def photo_target(data,body,context_meta):
    fields={'walk_run_id','criterion_id','photo_stage'}
    if not fields&set(body):return None
    if not fields<=set(body):raise ValueError('PHOTO_CONTEXT_REQUIRED')
    run=run_for(data,body['walk_run_id'])
    if run['plan_id']!=(context_meta or{}).get('public_id'):raise ValueError('WALK_PLAN_MISMATCH')
    criterion=next((c for c in FORMS['law']['criteria']if c['id']==body['criterion_id']),None)
    if criterion is None or body['evidence_id']not in criterion['evidence']or body['photo_stage']not in {'BEFORE','AFTER','EVIDENCE'}:raise ValueError('PHOTO_CONTEXT_INVALID')
    if len(run.get('field_photos',[]))>=300:raise ValueError('PHOTO_LINK_LIMIT')
    return run

def record_photo(run,body,file,actor,name,stamp):
    photos=run.setdefault('field_photos',[])
    known=next((p for p in photos if p['file_id']==file['id']and p['criterion_id']==body['criterion_id']),None)
    if known:return known
    link={'file_id':file['id'],'criterion_id':body['criterion_id'],'form':'law','evidence_id':body['evidence_id'],'stage':body['photo_stage'],'by':name,'actor_id':actor,'at':stamp}
    photos.append(link);return link
