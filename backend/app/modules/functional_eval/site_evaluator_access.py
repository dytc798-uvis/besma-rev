"""Reuse evaluation workflow with an authenticated SITE account, without role changes."""
from fastapi import HTTPException


def is_site_evaluator(user):
    role=getattr(getattr(user,'role',None),'value',getattr(user,'role',None))
    if role=='SITE_FUNCTIONAL_EVAL':
        return True
    if role!='SITE':
        return False
    from app.modules.workspace_site_access import require_site_identity
    try:
        require_site_identity(user)
    except HTTPException:
        return False
    return True


def linked_site_code(db,user):
    from app.modules.workspace_site_access import require_site_identity
    from app.modules.sites.models import Site
    try:
        ident=require_site_identity(user)
    except HTTPException as exc:
        raise ValueError('SITE_MISMATCH')from exc
    site=db.get(Site,ident)
    if site is None or not site.site_code:
        raise ValueError('SITE_MISMATCH')
    return site.site_code


def is_linked_site_manager(db,user,site_code):
    from .models import FunctionalEvalSiteRegistry
    try:
        own=linked_site_code(db,user)
    except ValueError:
        return False
    login=(getattr(user,'login_id',None)or'').strip()
    if own!=site_code or not login:
        return False
    registry=db.query(FunctionalEvalSiteRegistry).filter_by(site_code=own).first()
    return bool(registry and (registry.manager_login_id or'').strip()==login)


def assert_linked_site_evaluator(db,user,period):
    if getattr(user.role,'value',user.role)!='SITE':
        return
    from .models import FunctionalEvalWorker
    own=linked_site_code(db,user)
    if is_linked_site_manager(db,user,own):
        return
    assigned=db.query(FunctionalEvalWorker.id).filter_by(period_id=period.id,site_code=own,
        assigned_evaluator_login_id=(user.login_id or'').strip(),is_active=True).first()
    if assigned is None:
        raise HTTPException(403,'이 현장의 평가 담당자 연결을 확인해 주세요. 기존 평가 이력은 유지됩니다.')
