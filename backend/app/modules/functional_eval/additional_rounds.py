"""Confirmed reference targets and independent additional rounds. Default intake OFF."""
from __future__ import annotations
import os,hashlib,json
from sqlalchemy import inspect,func,exists,select,or_
from sqlalchemy.orm import object_session
from app.core.datetime_utils import utc_now
from .models import (FunctionalEvalAdditionalApproval as Additional,FunctionalEvalTargetEnrollment as Enrollment,
    FunctionalEvalPeriodMode as PeriodMode,FunctionalEvalPeriod,FunctionalEvalSiteApproval as BaseApproval,
    FunctionalEvalWorker,FunctionalEvalAssessment,FunctionalEvalAttendanceEntry,FunctionalEvalSignature,FunctionalEvalIntakeReceipt as Receipt)

FLAG='BESMA_FE_ADDITIONAL_EVALUATION_ENABLED'
TABLES=(Additional.__tablename__,Enrollment.__tablename__,PeriodMode.__tablename__,Receipt.__tablename__)

def schema_ready(db):
    bind=db.get_bind();cached=db.info.get('fe_additional_schema')
    if cached and cached[0]is bind:return cached[1]
    inspector=inspect(bind);ready=all(inspector.has_table(name)for name in TABLES)
    db.info['fe_additional_schema']=(bind,ready)
    return ready

def policy(db):
    value=os.getenv(FLAG,'false').strip().lower()
    ready=schema_ready(db)
    return {'enabled':value=='true'and ready,'state':'ENABLED'if value=='true'and ready else'CHECK_REQUIRED'if value not in {'true','false'}or value=='true'and not ready else'OFF'}

def continuous(period):
    db=object_session(period)
    if db is None or not period.id or not schema_ready(db):return False
    row=db.get(PeriodMode,period.id)
    return bool(row and row.mode=='CONTINUOUS')

def set_mode(db,actor_id,period_id,mode,expected_mode,deadline=None):
    if not policy(db)['enabled']:raise ValueError('ADDITIONAL_EVALUATION_DISABLED')
    current=db.query(FunctionalEvalPeriod).filter_by(is_active=True).order_by(FunctionalEvalPeriod.id.desc()).first()
    if current is None or current.id!=period_id:raise ValueError('PERIOD_SCOPE_CHANGED')
    record=db.get(PeriodMode,period_id);before=record.mode if record else'PERIODIC'
    if before==mode:return current
    if before!=expected_mode or mode not in {'PERIODIC','CONTINUOUS'}:raise ValueError('PERIOD_MODE_CHANGED')
    if mode=='PERIODIC':
        from app.core.datetime_utils import kst_today
        if deadline is None or deadline<kst_today():raise ValueError('PERIOD_DEADLINE_REQUIRED')
        current.deadline_date=deadline
    if record is None:record=PeriodMode(period_id=period_id,mode=mode,updated_by_user_id=actor_id,history_json=[])
    record.history_json=[*(record.history_json or[]),{'from':before,'to':mode,'actor_id':actor_id,'at':utc_now().isoformat(),'deadline_date':str(current.deadline_date)}]
    record.mode=mode;record.updated_by_user_id=actor_id;db.add(record);db.commit();return current

def _observed_workers(db,period_id,site_code):
    """Daily attendance/assessment is a source; it is not a roster enrollment."""
    attended=exists(select(FunctionalEvalAttendanceEntry.id).where(
        FunctionalEvalAttendanceEntry.period_id==period_id,
        FunctionalEvalAttendanceEntry.rrn_hash==FunctionalEvalWorker.rrn_hash))
    assessed=exists(select(FunctionalEvalAssessment.id).where(
        FunctionalEvalAssessment.worker_id==FunctionalEvalWorker.id))
    return db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id==period_id,
        FunctionalEvalWorker.site_code==site_code,FunctionalEvalWorker.is_site_manager.is_(False),
        or_(attended,assessed))

def active_batch(db,period_id,site_code):
    if not schema_ready(db):return 0
    enrolled=db.query(func.max(Enrollment.evaluation_batch)).join(FunctionalEvalWorker,Enrollment.worker_id==FunctionalEvalWorker.id).filter(Enrollment.period_id==period_id,FunctionalEvalWorker.site_code==site_code).scalar()or 0
    observed=_observed_workers(db,period_id,site_code).with_entities(func.max(FunctionalEvalWorker.evaluation_batch)).scalar()or 0
    return max(int(enrolled),int(observed))

def worker_approval_batch(db,worker):
    if not schema_ready(db):return 0
    record=db.get(Enrollment,worker.id)
    return record.evaluation_batch if record else int(worker.evaluation_batch or 0)

def get_approval(db,period_id,site_code,batch=None,create=False):
    batch=active_batch(db,period_id,site_code)if batch is None else batch
    model=Additional if batch>0 else BaseApproval
    query=db.query(model).filter_by(period_id=period_id,site_code=site_code)
    if batch>0:
        if not schema_ready(db):raise ValueError('ADDITIONAL_SCHEMA_REQUIRED')
        query=query.filter_by(evaluation_batch=batch)
    row=query.first()
    if row is None and create:
        if batch>0:
            enrolled=db.query(Enrollment.worker_id).join(FunctionalEvalWorker,Enrollment.worker_id==FunctionalEvalWorker.id).filter(Enrollment.period_id==period_id,Enrollment.evaluation_batch==batch,FunctionalEvalWorker.site_code==site_code).first()
            observed=_observed_workers(db,period_id,site_code).filter(FunctionalEvalWorker.evaluation_batch==batch).first()
            if enrolled is None and observed is None:raise ValueError('EVALUATION_ROUND_CHANGED')
        values={'period_id':period_id,'site_code':site_code,'status':'IN_PROGRESS'}
        if batch>0:values['evaluation_batch']=batch
        row=model(**values);db.add(row);db.flush()
    return row

def current_approvals(db,period_id):
    rows={r.site_code:r for r in db.query(BaseApproval).filter_by(period_id=period_id)}
    if schema_ready(db):
        extra=db.query(Additional).filter_by(period_id=period_id).order_by(Additional.evaluation_batch).all()
        for row in extra:
            if row.evaluation_batch==active_batch(db,period_id,row.site_code):rows[row.site_code]=row
    return list(rows.values())

def all_approvals(db,period_id):
    rows=list(db.query(BaseApproval).filter_by(period_id=period_id))
    if schema_ready(db):rows.extend(db.query(Additional).filter_by(period_id=period_id))
    return rows

def requires_round_scope(db,period_id,site_code):
    from . import signature_revisions
    if signature_revisions.schema_ready(db) and db.query(signature_revisions.Rejection.id).filter_by(period_id=period_id,site_code=site_code).first():return True
    if not schema_ready(db):return False
    if active_batch(db,period_id,site_code)>0:return True
    return db.query(Enrollment.worker_id).join(FunctionalEvalWorker,Enrollment.worker_id==FunctionalEvalWorker.id).filter(Enrollment.period_id==period_id,FunctionalEvalWorker.site_code==site_code).first()is not None

def round_history(db,period_id,site_code):
    rows=[];base=get_approval(db,period_id,site_code,batch=0)
    if base:rows.append(base)
    if schema_ready(db):rows.extend(db.query(Additional).filter_by(period_id=period_id,site_code=site_code).order_by(Additional.evaluation_batch).all())
    return rows

def enrolled_workers(db,period_id,site_code=None):
    if not schema_ready(db):return []
    query=db.query(FunctionalEvalWorker).join(Enrollment,Enrollment.worker_id==FunctionalEvalWorker.id).filter(Enrollment.period_id==period_id,FunctionalEvalWorker.period_id==period_id,FunctionalEvalWorker.is_site_manager.is_(False))
    if site_code:query=query.filter(FunctionalEvalWorker.site_code==site_code)
    return query.all()

def current_workers(db,period_id,workers):
    batches={code:active_batch(db,period_id,code)for code in {w.site_code for w in workers}}
    return [w for w in workers if not batches[w.site_code]or(w.evaluation_batch or 0)==batches[w.site_code]]

def next_batch(db,period_id,site_code):
    current=active_batch(db,period_id,site_code);row=get_approval(db,period_id,site_code,batch=current)
    signed=db.query(func.max(FunctionalEvalSignature.evaluation_batch)).filter_by(period_id=period_id,site_code=site_code).scalar()
    sealed=bool(row and(row.evaluation_completed_at or row.site_submitted_at or row.status not in {'IN_PROGRESS','REJECTED'}))
    if not current and not sealed:
        from .models import FunctionalEvalDailyReport
        from .service import _site_completed_in_report_snapshot
        sealed=any(_site_completed_in_report_snapshot(report.report_json_snapshot,site_code)for report in db.query(FunctionalEvalDailyReport).filter_by(period_id=period_id))
    return max(current+(1 if sealed else 0),int(signed)+1 if signed is not None else 0)

def enrollment_review(db,period_id,actions,sites):
    state=policy(db)
    if not state['enabled']:return {**state,'eligible_count':None,'can_add':False,'gaps':[]},[]
    from app.modules.users.models import User
    existing={x.worker_id for x in db.query(Enrollment).filter_by(period_id=period_id)}
    assessed={ident for ident, in db.query(FunctionalEvalAssessment.worker_id).join(FunctionalEvalWorker,FunctionalEvalAssessment.worker_id==FunctionalEvalWorker.id).filter(FunctionalEvalWorker.period_id==period_id)}
    attended={value for value, in db.query(FunctionalEvalAttendanceEntry.rrn_hash).filter_by(period_id=period_id)}
    candidates=[];gaps=[];accounts={}
    for row,old,action,_ in actions:
        if action in {'PRESERVED','CHECK_REQUIRED'}or row.is_site_manager or old and(not old.is_active or old.is_site_manager or old.id in assessed or old.id in existing or old.rrn_hash in attended):continue
        registry=sites.get(row.site_code);login=(old.assigned_evaluator_login_id if old else None)or(registry.manager_login_id if registry else'')
        if login not in accounts:accounts[login]=db.query(User).filter_by(login_id=login,is_active=True,must_change_password=False).first()if login else None
        user=accounts[login]
        role = getattr(user.role, 'value', user.role) if user else None
        if not user or role not in {'SITE_FUNCTIONAL_EVAL', 'SITE'} or getattr(user.ui_type,'value',user.ui_type)!='SITE':
            gaps.append({'site_code':row.site_code,'message':'현재 평가 담당 계정을 확인해 주세요.'});continue
        from .service import _site_code_for_user
        try:
            account_site=_site_code_for_user(user,db)
            if role == 'SITE':
                from . import site_evaluator_access
                # Reuse the existing SITE manager/assigned-worker boundary.
                # Same name or mere membership of a site never creates authority.
                linked = site_evaluator_access.is_linked_site_manager(db,user,row.site_code)
                assigned = bool(old and old.assigned_evaluator_login_id == login and old.site_code == account_site)
                if not linked and not assigned:
                    account_site = None
        except ValueError:account_site=None
        if account_site!=row.site_code:
            gaps.append({'site_code':row.site_code,'message':'평가 담당자의 현장 연결을 확인해 주세요.'});continue
        candidates.append((row,old,login))
    return {**state,'eligible_count':len(candidates),'can_add':bool(candidates)and not gaps,'gaps':gaps},candidates

def enroll(db,period_id,actor_id,source_sha,roster_batch_id,candidates,created):
    if not policy(db)['enabled']:raise ValueError('ADDITIONAL_EVALUATION_DISABLED')
    batches={row.site_code:next_batch(db,period_id,row.site_code)for row,_,_ in candidates}
    enrolled=[]
    for source,old,login in candidates:
        worker=old if old is not None else created[source.rrn_hash]
        if db.get(Enrollment,worker.id)or db.query(FunctionalEvalAssessment.id).filter_by(worker_id=worker.id).first():raise ValueError('TARGET_SCOPE_CHANGED')
        worker.evaluation_batch=batches[source.site_code]
        if not worker.assigned_evaluator_login_id:worker.assigned_evaluator_login_id=login
        db.add(Enrollment(worker_id=worker.id,period_id=period_id,roster_batch_id=roster_batch_id,evaluation_batch=worker.evaluation_batch,confirmed_by_user_id=actor_id,source_sha256=source_sha))
        db.flush()
        get_approval(db,period_id,source.site_code,batch=worker.evaluation_batch,create=True)
        enrolled.append({'worker_id':worker.id,'site_code':source.site_code,'evaluation_batch':worker.evaluation_batch})
    return enrolled

def assert_expected_batch(db,period_id,site_code,expected):
    actual=active_batch(db,period_id,site_code)
    if requires_round_scope(db,period_id,site_code)and expected is None or expected is not None and expected!=actual:raise ValueError('EVALUATION_ROUND_CHANGED')
    return actual

def round_fingerprint(db,period_id,site_code,batch):
    if not schema_ready(db):return None
    from .service import _evaluation_target_workers
    period=db.get(FunctionalEvalPeriod,period_id)
    if period is None:raise ValueError('PERIOD_SCOPE_CHANGED')
    enrolled={row.worker_id:row for row in db.query(Enrollment).filter_by(period_id=period_id)}
    workers=[w for w in _evaluation_target_workers(db,period,site_code=site_code)if(enrolled[w.id].evaluation_batch if w.id in enrolled else 0)==batch]
    worker_ids=[w.id for w in workers]
    assessments=db.query(FunctionalEvalAssessment).filter(FunctionalEvalAssessment.worker_id.in_(worker_ids)).order_by(FunctionalEvalAssessment.id).all()
    signatures=db.query(FunctionalEvalSignature).filter_by(period_id=period_id,site_code=site_code,evaluation_batch=batch).order_by(FunctionalEvalSignature.id).all()
    values=lambda rows:[{c.name:getattr(row,c.name)for c in row.__table__.columns}for row in rows]
    state={'period_id':period_id,'site_code':site_code,'batch':batch,'mode':'CONTINUOUS'if continuous(period)else'PERIODIC','deadline':str(period.deadline_date),'workers':values(sorted(workers,key=lambda w:w.id)),'assessments':values(assessments),'enrollments':values([enrolled[w.id]for w in sorted(workers,key=lambda w:w.id)if w.id in enrolled]),'signatures':[{'id':s.id,'stage':s.stage,'signed_at':s.signed_at,'signature_hash':s.signature_hash}for s in signatures]}
    approval=get_approval(db,period_id,site_code,batch=batch)
    state['approval']={key:getattr(approval,key)for key in ['status','evaluation_completed_at','site_submitted_at','hq_officer_approved_at','hq_officer_comment','hq_approved_at','ceo_approved_at','rejected_at','reject_note']}if approval is not None else None
    from . import signature_revisions
    revisions=signature_revisions.fingerprint_state(db,period_id,site_code,batch)
    if revisions is not None:state['signature_revisions']=revisions
    return hashlib.sha256(json.dumps(state,ensure_ascii=False,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()

def lock_round(db,period_id,site_code,expected_batch,expected_sha,*,current_only,create=False):
    required=requires_round_scope(db,period_id,site_code)
    if required and(expected_batch is None or expected_sha is None):raise ValueError('EVALUATION_ROUND_CHANGED')
    batch=assert_expected_batch(db,period_id,site_code,expected_batch)if current_only else(expected_batch if expected_batch is not None else active_batch(db,period_id,site_code))
    row=get_approval(db,period_id,site_code,batch=batch,create=current_only or create)
    if row is None:raise ValueError('INVALID_APPROVAL_TRANSITION')
    model=type(row)
    changed=db.query(model).filter(model.id==row.id,model.status==row.status).update({model.status:model.status},synchronize_session=False)
    if changed!=1:raise ValueError('EVALUATION_ROUND_CHANGED')
    if current_only:assert_expected_batch(db,period_id,site_code,expected_batch)
    if expected_sha is not None and expected_sha!=round_fingerprint(db,period_id,site_code,batch):raise ValueError('EVALUATION_ROUND_CHANGED')
    return batch,row
