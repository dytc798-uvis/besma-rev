"""Append-only rejection and signature versions. Existing rows and PDFs stay intact."""
from __future__ import annotations
import hashlib,json,os,re,uuid
from sqlalchemy import inspect,func
from .models import (FunctionalEvalSignature as Signature,FunctionalEvalSignatureVersion as Version,
    FunctionalEvalSignatureRejection as Rejection,FunctionalEvalSignatureRevocation as Revocation,
    FunctionalEvalAssessment,FunctionalEvalWorker)
from app.core.datetime_utils import utc_now

FLAG='BESMA_FE_SIGNATURE_REVISIONS_ENABLED'
TABLES=(Version.__tablename__,Rejection.__tablename__,Revocation.__tablename__)

def schema_ready(db):
    bind=db.get_bind();cached=db.info.get('fe_signature_revision_schema')
    if cached and cached[0]is bind:return cached[1]
    inspector=inspect(bind);ready=all(inspector.has_table(name)for name in TABLES)
    db.info['fe_signature_revision_schema']=(bind,ready)
    return ready

def policy(db):
    value=os.getenv(FLAG,'false').strip().lower();ready=schema_ready(db)
    return {'enabled':value=='true'and ready,'state':'ENABLED'if value=='true'and ready else'CHECK_REQUIRED'if value not in {'true','false'}or value=='true'and not ready else'OFF'}

def key(row):return ('version:'if isinstance(row,Version)else'original:')+str(row.id)

def is_revoked(db,row):return bool(schema_ready(db)and db.get(Revocation,key(row)))

def active(db,original):
    if original is None:return None
    if not schema_ready(db):return original
    latest=db.query(Version).filter_by(root_signature_id=original.id).order_by(Version.revision_no.desc()).first()
    row=latest if latest else original
    return None if is_revoked(db,row)else row

def all_records(db,period_id,*,site_code=None,batch=None,signer_id=None):
    rows=[]
    for model in [Signature,*([Version]if schema_ready(db)else[])]:
        query=db.query(model).filter_by(period_id=period_id)
        if site_code is not None:query=query.filter_by(site_code=site_code)
        if batch is not None:query=query.filter_by(evaluation_batch=batch)
        if signer_id is not None:query=query.filter_by(signer_user_id=signer_id)
        rows.extend(query.all())
    return sorted(rows,key=lambda row:(row.signed_at,str(row.id)),reverse=True)

def payload(db,row):
    from .signature_service import serialize_signature
    data=serialize_signature(row);revocation=db.get(Revocation,key(row))if schema_ready(db)else None
    data.update(is_rejected=bool(revocation),revision_no=getattr(row,'revision_no',0),
                document_url=f'/functional-eval/signatures/{row.id}/document')
    if revocation:
        event=db.get(Rejection,revocation.rejection_id)
        data.update(rejected_at=event.created_at.isoformat(),reject_note=event.note)
    return data

def create_version(db,original,values):
    if not policy(db)['enabled']:raise ValueError('SIGNATURE_REVISION_DISABLED')
    if active(db,original)is not None:raise ValueError('SIGNATURE_ALREADY_EXISTS')
    revision=(db.query(func.max(Version.revision_no)).filter_by(root_signature_id=original.id).scalar()or 0)+1
    row=Version(id=uuid.uuid4().hex,root_signature_id=original.id,revision_no=revision,**values)
    db.add(row);db.flush();return row

def resolve(db,identifier):
    value=str(identifier)
    if re.fullmatch(r'[0-9]{1,18}',value):return db.get(Signature,int(value))
    if re.fullmatch(r'[0-9a-f]{32}',value)and schema_ready(db):return db.get(Version,value)
    return None

def fingerprint_state(db,period_id,site_code,batch):
    if not schema_ready(db):return None
    versions=db.query(Version).filter_by(period_id=period_id,site_code=site_code,evaluation_batch=batch).order_by(Version.id).all()
    events=db.query(Rejection).filter_by(period_id=period_id,site_code=site_code,evaluation_batch=batch).order_by(Rejection.id).all()
    if not versions and not events:return None
    return {'versions':[{'id':row.id,'root':row.root_signature_id,'revision':row.revision_no,'signed_at':str(row.signed_at),'signature_hash':row.signature_hash}for row in versions],
            'rejections':[{'id':row.id,'payload_sha256':row.payload_sha256}for row in events]}

def _authorized(db,user,site_code,stage):
    from . import approval_workflow,service
    role=getattr(user.role,'value',user.role)
    if stage in {'SITE','TEAM'}:
        if role!='SITE_FUNCTIONAL_EVAL'or service._site_code_for_user(user,db)!=site_code or not service._is_primary_site_evaluator(db,user,site_code):raise ValueError('MANAGER_ONLY')
    elif stage=='HQ_OFFICER':approval_workflow.assert_hq_officer_approver(user)
    elif stage=='HQ_DIRECTOR':approval_workflow.assert_hq_director_approver(user)
    elif stage=='CEO':approval_workflow.assert_ceo_approver(user)
    else:raise ValueError('INVALID_APPROVAL_TRANSITION')

def _snapshot(row):return {column.name:json.loads(json.dumps(getattr(row,column.name),default=str))for column in row.__table__.columns}

def reject(db,user,period,site_code,*,stage,note,request_id,expected_batch,expected_sha,leader_login=None):
    from . import additional_rounds,approval_workflow,service
    _authorized(db,user,site_code,stage)
    if not isinstance(request_id,str)or not re.fullmatch(r'[0-9a-f]{32}',request_id)or expected_batch is None or expected_sha is None:raise ValueError('EVALUATION_ROUND_CHANGED')
    note=(note or'').strip();leader_login=(leader_login or'').strip()or None
    if not note:raise ValueError('REJECTION_NOTE_REQUIRED')
    request={'actor':user.id,'period':period.id,'site':site_code,'batch':expected_batch,'stage':stage,'note':note,'scope':expected_sha,'leader':leader_login}
    digest=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if schema_ready(db):
        previous=db.get(Rejection,request_id)
        if previous:
            if previous.actor_id!=user.id or previous.payload_sha256!=digest:raise ValueError('REJECTION_REQUEST_CHANGED')
            return previous.result_json
    if not policy(db)['enabled']:raise ValueError('SIGNATURE_REVISION_DISABLED')
    batch,approval=additional_rounds.lock_round(db,period.id,site_code,expected_batch,expected_sha,current_only=False)
    allowed={'TEAM':{'IN_PROGRESS','REJECTED'},'SITE':{'SITE_APPROVED'},'HQ_OFFICER':{'SITE_APPROVED'},'HQ_DIRECTOR':{'HQ_OFFICER_APPROVED'},'CEO':{'HQ_APPROVED'}}
    if approval.status not in allowed[stage]:raise ValueError('INVALID_APPROVAL_TRANSITION')
    workers=[row for row in service._evaluation_target_workers(db,period,site_code=site_code)if additional_rounds.worker_approval_batch(db,row)==batch]
    # Legacy raw batches need an explicit mapping; never reinterpret old signatures.
    if batch==0 and any((row.evaluation_batch or 0)>0 for row in workers):raise ValueError('LEGACY_ROUND_MAPPING_REQUIRED')
    if stage=='TEAM':
        if not leader_login:raise ValueError('TEAM_LEADER_NOT_SIGNED')
        workers=[row for row in workers if(row.assigned_evaluator_login_id or'').strip()==leader_login]
    if not workers:raise ValueError('INCOMPLETE_EVALUATIONS')
    roots=db.query(Signature).filter_by(period_id=period.id,site_code=site_code,evaluation_batch=batch).all()
    if stage=='TEAM':roots=[row for row in roots if row.team_leader_login_id==leader_login and row.stage in {'TEAM_LEADER','TEAM_MANAGER_APPROVE'}]
    current=[row for root in roots if(row:=active(db,root))is not None]
    required='TEAM_LEADER'if stage=='TEAM'else'SITE'
    if not any(row.stage==required for row in current):raise ValueError('TEAM_LEADER_NOT_SIGNED'if stage=='TEAM'else'INCOMPLETE_APPROVAL_HISTORY')
    assessments=db.query(FunctionalEvalAssessment).filter(FunctionalEvalAssessment.worker_id.in_([row.id for row in workers])).order_by(FunctionalEvalAssessment.id).all()
    event=Rejection(id=request_id,actor_id=user.id,period_id=period.id,site_code=site_code,evaluation_batch=batch,stage=stage,team_leader_login_id=leader_login,note=note,payload_sha256=digest,before_scope_sha256=expected_sha,approval_snapshot=_snapshot(approval),assessment_snapshot=[_snapshot(row)for row in assessments],result_json={})
    db.add(event);db.flush()
    for row in current:
        db.add(Revocation(signature_key=key(row),rejection_id=event.id,root_signature_id=getattr(row,'root_signature_id',row.id),version_id=row.id if isinstance(row,Version)else None))
    if stage!='TEAM':
        approval.status='REJECTED';approval.rejected_stage=stage;approval.reject_note=note;approval.rejected_at=utc_now();approval.rejected_by_user_id=user.id
        for field in ['evaluation_completed_at','site_submitted_at','site_submitted_by_user_id','hq_officer_approved_at','hq_officer_approved_by_user_id','hq_officer_comment','hq_approved_at','hq_approved_by_user_id','ceo_approved_at','ceo_approved_by_user_id']:
            setattr(approval,field,None)
        db.add(approval)
    event.result_json={'request_id':event.id,'evaluation_batch':batch,'rejected':True,'reject_note':note,'rejected_signature_count':len(current),'approval':approval_workflow.serialize_site_approval(approval),'team_leader_login_id':leader_login}
    db.flush();db.commit();return event.result_json

def receipt(db,user,request_id):
    if not schema_ready(db):raise ValueError('NOT_FOUND')
    row=db.get(Rejection,request_id)
    if row is None or row.actor_id!=user.id:raise ValueError('NOT_FOUND')
    _authorized(db,user,row.site_code,row.stage)
    return row.result_json

def revision_open(db,period_id,site_code,batch):
    if not schema_ready(db):return False
    return db.query(Rejection.id).filter_by(period_id=period_id,site_code=site_code,evaluation_batch=batch).first()is not None
