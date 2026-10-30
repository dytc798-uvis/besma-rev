"""Resolve an imported inspection's full source name, never its list ordinal."""
import re,unicodedata
from app.modules.sites.models import Site
from app.modules.safety_features.inspection_plan import INSPECTION_SOURCE

def normalized(value):
    return ''.join(unicodedata.normalize('NFC',value or'').casefold().split())

def label(value):
    # Department numbering is presentation; retain customer and full project.
    return normalized(re.sub(r'^\[\s*\d+\s*\.\s*','[',value or''))

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
    names={line.split(':',1)[1].strip()for line in(row.detail_text or'').splitlines()if line.startswith('현장:')}
    if len(names)>1:return None
    name=next(iter(names))if names else(row.title or'').removeprefix('[점검] ').strip()
    if not name:return None
    rows=db.query(Site).all()
    equal=[s for s in rows if label(s.site_name)==label(name)]
    if equal:return equal[0]if len(equal)==1 else None
    # Imported plans add their combined trades to an otherwise unchanged full
    # ERP project name. A separate contract/unit or legacy duplicate vetoes this
    # fallback. Never remove project-number or temporary-power descriptors.
    base,trades=trade_label(name)
    if trades is None:return None
    equal=[s for s in rows if trade_label(s.site_name)[0]==base]
    return equal[0]if len(equal)==1 and trade_label(equal[0].site_name)[1]is None else None
