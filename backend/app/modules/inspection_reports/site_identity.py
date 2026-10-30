"""Resolve an imported inspection's full source name, never its list ordinal."""
import re,unicodedata
from types import SimpleNamespace
from app.modules.sites.models import Site
from app.modules.safety_features.inspection_plan import INSPECTION_SOURCE

def normalized(value):
    return ''.join(unicodedata.normalize('NFC',value or'').casefold().split())

def label(value):
    # Classification/dept presentation is not a project or work-package number.
    value=re.sub(r'^\[관급\]\s*','',value or'')
    value=re.sub(r'^\[{1,2}\s*\d+\s*\.\s*','[',value)
    value=re.sub(r'\(\s*(?:제)?0*(\d{1,2})\s*공구\s*\)',lambda m:'('+str(int(m[1]))+'공구)',value)
    return normalized(value)

def directory_snapshot():
    from app.modules.site_directory import snapshot
    return snapshot()

def canonical(code,aliases):
    seen=set()
    while code in aliases:
        if code in seen:return None
        seen.add(code);code=aliases[code]
        if not isinstance(code,str)or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',code):return None
    return code

def choose(rows,directory=None):
    if len(rows)==1:return rows[0]
    if not rows:return None
    data=directory if directory is not None else directory_snapshot()
    aliases=data.get('aliases',{})
    if not isinstance(aliases,dict):return None
    targets={canonical(r.site_code,aliases)for r in rows}
    if None in targets or len(targets)!=1:return None
    code=next(iter(targets));exact=[r for r in rows if r.site_code==code]
    return exact[0]if len(exact)==1 else None

def name_for(row):
    names={line.split(':',1)[1].strip()for line in(row.detail_text or'').splitlines()if line.startswith('현장:')}
    if len(names)>1:return None
    return next(iter(names))if names else(row.title or'').removeprefix('[점검] ').strip()

def matching(rows,name,directory=None):
    equal=[s for s in rows if label(s.site_name)==label(name)]
    if equal:return choose(equal,directory)
    base,trades=trade_label(name)
    if trades is None:return None
    equal=[s for s in rows if trade_label(s.site_name)[0]==base]
    selected=choose(equal,directory)
    return selected if selected is not None and trade_label(selected.site_name)[1]is None else None

def trade_label(value):
    """Recognize only a terminal explicit electrical/fire/communications list."""
    match=re.search(r'\(\s*((?:전기|소방|통신)(?:\s*,\s*(?:전기|소방|통신))*)\s*\)\s*$',value or'')
    if not match:return label(value),None
    parts=tuple(part.strip()for part in match[1].split(','))
    if len(parts)!=len(set(parts)):return label(value),None
    return label(value[:match.start()]),frozenset(parts)

def resolve(db,row):
    if row.source!=INSPECTION_SOURCE:return None
    # This joint visit was explicitly reviewed before this resolver existed.
    if row.client_item_key=='inspection:202611:joint-cheonan':
        return db.query(Site).filter(Site.site_code=='25062').one_or_none()
    name=name_for(row)
    if not name:return None
    return matching(db.query(Site).all(),name)

def resolve_source(db,row):
    """HQ evidence lookup may use a verified directory code before SITE registration.

    Publication continues to call resolve(), which returns registered Site rows
    only. This never creates an account, grants SITE access, or rekeys a review.
    """
    if row.source!=INSPECTION_SOURCE:return None
    registered=resolve(db,row)
    if registered is not None:return registered
    name=name_for(row)
    if not name:return None
    rows=db.query(Site).all()
    exact=[s for s in rows if label(s.site_name)==label(name)]
    base,trades=trade_label(name)
    if exact or trades is not None and any(trade_label(s.site_name)[0]==base for s in rows):return None
    data=directory_snapshot();items=data.get('sites')
    if not isinstance(items,list):return None
    rows=[]
    for item in items:
        code=item.get('code');title=item.get('name')
        if not isinstance(code,str)or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',code)or not isinstance(title,str)or not title.strip():return None
        rows.append(SimpleNamespace(id=None,site_code=code,site_name=title))
    return matching(rows,name,data)
