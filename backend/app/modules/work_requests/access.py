"""Headquarters account boundary; membership and file grants remain separate."""
HQ_REQUEST_ROLES=frozenset({'HQ_SAFE','HQ_SAFE_ADMIN','ACCIDENT_ADMIN','SUPER_ADMIN',
    'HQ_OTHER','HQ_BUDGET_ESTIMATE','HQ_OUTSOURCING_PURCHASE'})


def headquarters_user(user):
    role=getattr(getattr(user,'role',None),'value',getattr(user,'role',None))
    ui=getattr(getattr(user,'ui_type',None),'value',getattr(user,'ui_type',None))
    return bool(getattr(user,'is_active',False)
        and not getattr(user,'must_change_password',False)
        and not getattr(user,'government_preview',False)
        and getattr(user,'site_id',None) is None
        and role in HQ_REQUEST_ROLES and ui in {'HQ_SAFE','HQ_OTHER'})
