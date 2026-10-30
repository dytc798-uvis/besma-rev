"""Exact canonical project labels only; no edit distance or best-match selection."""
import re,unicodedata,collections
def norm(value):return re.sub(r'[^a-z0-9가-힣]','',unicodedata.normalize('NFC',value).casefold())
def labels(site):
 result=set()
 for source in [site['site'],*site.get('aliases',[])]:
  name=re.sub(r'^\[[^]]+\]\s*','',source).strip()
  variants=[name]
  # Parenthetical details are optional only when the remaining complete label
  # is itself unique across the entire catalog (including other trades/units).
  variants.append(re.sub(r'\([^()]*\)','',name))
  for text in list(variants):
   variants.append(re.sub(r'\s*(?:중\s*)?(?:일반전기공사|전기공사|신축공사|신축현장)\s*$','',text))
  for text in variants:
   key=norm(text)
   if len(key)>=8 and re.search('[가-힣a-z]',key)and(re.search(r'\d',key)or len(key)>=12):result.add(key)
 return result
def project_labels(site):
 """Whole canonical project names, with terminal work descriptors removed."""
 result=set()
 suffixes=('공동주택신축공사','주택재개발정비사업','전기설비공사','일반전기공사','전기및소방공사','소방시설공사','임시전력공사','임시동력공사','가설전기공사','신축공사','신축현장','전기공사')
 for source in [site['site'],*site.get('aliases',[])]:
  name=re.sub(r'^\[[^]]+\]\s*','',source).strip()
  vendor=re.match(r'^\[(?:준공-)?[1-6]\.([^]]+)\]',source)
  vendor=norm(vendor[1])if vendor else ''
  for variant in [name,re.sub(r'\([^()]*\)','',name)]:
   queue=[norm(variant)];seen=set(queue)
   while queue:
    value=queue.pop()
    for suffix in suffixes:
     if not value.endswith(suffix):continue
     project=value[:-len(suffix)]
     if not project or project in seen:continue
     seen.add(project);queue.append(project)
     if len(project)>=8 and re.search('[가-힣a-z]',project):result.add(project)
     if len(project)>=5 and re.search(r'\d',project)and len(vendor)>=3:result.add(vendor+project)
 return result

def bind(text,sites):
 value=norm(text);explicit={s['code']:s for s in sites if re.search(r'(?<!\d)'+re.escape(s['code'])+r'(?!\d)',text)}
 if len(explicit)>1:return {'state':'AMBIGUOUS','reason':'MULTIPLE_EXPLICIT_CODES'}
 owners=collections.defaultdict(set)
 for s in sites:
  for label in labels(s):owners[label].add(s['code'])
 hits=collections.defaultdict(list)
 for label,codes in owners.items():
  if label in value:
   for code in codes:hits[code].append(label)
 # Full original labels keep their existing meaning. Shorter project labels
 # are considered only when none matched; every catalog code participates so
 # temporary power, other units and legacy IDs still veto ambiguous projects.
 if not hits:
  for site in sites:
   for label in project_labels(site):
    if label not in value:continue
    hits[site['code']].append(label)
    # Even an unrecognized work descriptor on a sibling contract vetoes a
    # shortened project label; the suffix list cannot silently hide that code.
    for other in sites:
     for name in [other['site'],*other.get('aliases',[])]:
      if label in norm(name)or label in norm(re.sub(r'\([^()]*\)','',name)):
       hits[other['code']].append(label)
 if explicit:
  code=next(iter(explicit))
  if set(hits)-{code}:return {'state':'AMBIGUOUS','reason':'CODE_NAME_CONFLICT'}
  return {'state':'EXACT_CODE','code':code,'evidence':code}
 if len(hits)!=1:return {'state':'AMBIGUOUS'if hits else'UNMATCHED','reason':'CANONICAL_LABEL_CONFLICT'if hits else'NO_EXACT_PROJECT_LABEL'}
 code=next(iter(hits));return {'state':'EXACT_CANONICAL_LABEL','code':code,'evidence':max(hits[code],key=len)}
