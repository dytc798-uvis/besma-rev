"""Explicit HQ refresh of the existing Google ledger. Existing rows are immutable."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os, sqlite3, tempfile, fcntl
from fastapi import APIRouter, HTTPException
from app.config.settings import settings
from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep
from .models import WorkerFeedbackOpinion
from .routes import _can_hq_write, _fetch_script_rows, _opinion_from_raw, _assert_can_read

router=APIRouter(prefix='/worker-feedback', tags=['worker-feedback-refresh'])

def state_root():
    return Path(settings.sqlite_path).resolve().parent/'worker-feedback-refresh'

def status_value():
    try:
        value=json.loads((state_root()/'status.json').read_text(encoding='utf-8'))
        return {k:value.get(k) for k in ['last_success_at','last_attempt_at','last_attempt_ok']}
    except (OSError,ValueError,TypeError):
        return {'last_success_at':None,'last_attempt_at':None,'last_attempt_ok':None}

def save_status(value):
    root=state_root();fd,name=tempfile.mkstemp(prefix='status-',suffix='.tmp',dir=root)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
        os.replace(name,root/'status.json')
    finally:
        if os.path.exists(name):os.unlink(name)

@router.get('/refresh-status')
def refresh_status(current_user:CurrentUserDep):
    _assert_can_read(current_user)
    from app.modules.worker_feedback.routes import _is_hq_user
    # Global source counts and identity data are never exposed through this status.
    return status_value()

@router.post('/refresh')
def refresh(db:DbDep,current_user:CurrentUserDep):
    if (not getattr(current_user,'is_active',False) or getattr(current_user,'must_change_password',False)
        or getattr(current_user,'government_preview',False) or not _can_hq_write(current_user)
        or getattr(current_user,'site_id',None) is not None):
        raise HTTPException(403,'본사 담당자만 새 의견을 가져올 수 있습니다.')
    return run_refresh(db)

def run_refresh(db):
    root=state_root();root.mkdir(mode=0o700,parents=True,exist_ok=True)
    if root.is_symlink():raise HTTPException(503,'의견 수신 기록을 확인해 주세요.')
    with (root/'refresh.lock').open('a+b') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise HTTPException(409,'다른 요청에서 의견을 가져오고 있습니다. 잠시 후 조회해 주세요.')
        prior=status_value();at=datetime.now(timezone.utc).isoformat()
        try:
            rows=_fetch_script_rows(1000)
            # Validate the entire source batch before inserting anything.
            payloads=[_opinion_from_raw(db,row) for row in rows]
            if any(not p.get('submitted_at_raw') or not p.get('phone_normalized') for p in payloads):
                raise HTTPException(502,'설문 응답의 접수 정보를 확인해 주세요.')
            candidates=[];held=0;seen=set();source_keys={}
            for p in payloads:source_keys.setdefault((p['submitted_at_raw'],p['phone_normalized']),set()).add(p['source_fingerprint'])
            lab=None
            try:lab=json.loads((root/'lab-identity.json').read_text(encoding='utf-8'))
            except FileNotFoundError:pass
            if lab is not None:
                from app.modules.sites.models import Site
                site=db.query(Site).filter(Site.site_code=='HQ_LAB').first()
                if not site or site.status!='LAB' or site.contract_type!='내부시험':raise RuntimeError('LAB_SCOPE_INVALID')
            for payload in payloads:
                fingerprint=payload['source_fingerprint']
                if fingerprint in seen:continue
                seen.add(fingerprint)
                if db.query(WorkerFeedbackOpinion).filter(WorkerFeedbackOpinion.source_fingerprint==fingerprint).first():continue
                if len(source_keys[(payload['submitted_at_raw'],payload['phone_normalized'])])>1:
                    held+=1;continue
                if db.query(WorkerFeedbackOpinion).filter(WorkerFeedbackOpinion.submitted_at_raw==payload['submitted_at_raw'],WorkerFeedbackOpinion.phone_normalized==payload['phone_normalized']).first():
                    held+=1;continue
                if lab is not None and payload['worker_name']==lab.get('worker_name') and hashlib.sha256(payload['phone_normalized'].encode()).hexdigest()==lab.get('phone_sha256'):
                    payload.update(matched_site_code='HQ_LAB',matched_site_name='본사 실험실',matched_worker_id=None,match_status='matched')
                candidates.append(payload)
            backup_name=None
            if candidates:
                # A verified private SQLite snapshot precedes every additive import.
                backup_name='before-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.sqlite3'
                with sqlite3.connect(Path(settings.sqlite_path).resolve().as_uri()+'?mode=ro',uri=True) as source:
                    with sqlite3.connect(root/backup_name) as target:
                        source.backup(target)
                        if target.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('BACKUP_CHECK_FAILED')
                os.chmod(root/backup_name,0o600)
                for payload in candidates:db.add(WorkerFeedbackOpinion(**payload))
                db.commit()
            else:db.rollback()
            value={'last_success_at':at,'last_attempt_at':at,'last_attempt_ok':True}
            save_status(value)
            receipt={'at':at,'fetched':len(rows),'created':len(candidates),'held':held,'existing_rows_updated':0,'backup':backup_name}
            (root/('receipt-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')).write_text(json.dumps(receipt),encoding='utf-8')
            return {**value,'fetched':len(rows),'created':len(candidates),'held':held,'existing_rows_updated':0}
        except Exception as exc:
            db.rollback();save_status({**prior,'last_attempt_at':at,'last_attempt_ok':False})
            if isinstance(exc,HTTPException):raise
            raise HTTPException(503,'새 의견을 가져오지 못했습니다. 잠시 후 다시 조회해 주세요.') from exc

def main():
    from app.core.database import SessionLocal
    with SessionLocal() as db:
        value=run_refresh(db)
    print(json.dumps(value))

if __name__=='__main__':main()
