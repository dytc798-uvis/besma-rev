"""Bounded filename-query planning; no filesystem paths, model tools or new grants."""
import re
from .grounding import answer as answer_from_known_data

INTENT=re.compile(r'찾아\s*(?:줘|주세요|주라|주십시오)|검색\s*해\s*(?:줘|주세요)|검색해|찾아봐|보여\s*(?:줘|주세요)|보내\s*(?:줘|주세요)|다운로드|어디에?\s*있(?:어|는지|나요)')
MATERIAL=re.compile(r'파일|자료|문서|기준|양식|절차서|지침서|보고서|점검표')
compact=lambda value:re.sub(r'\s+','',value.casefold())

def plan(text):
    if not isinstance(text,str)or not 1<=len(text)<=6000:raise ValueError('LOOKUP_TEXT_REQUIRED')
    # Metadata/history questions already have a factual route. Do not turn them
    # into a guessed filename query or prevent their normal queued answer.
    if answer_from_known_data({'kind':'QUESTION','body':text},lambda *_:{'metadata':True}):return None
    document=re.search(r'절차서|지침서|매뉴얼|규정|평가\s*기준|안전\s*기준',text)
    content_question=bool(document and re.search(r'내용|조항|적용|어떻게|무엇|뭐|설명|문의|알려|[?？]',text)
                          and not re.search(r'만들|작성해|생성해',text))
    if not MATERIAL.search(text)or not(INTENT.search(text)or content_question):return None
    topic=text[:document.end()]if content_question else INTENT.sub(' ',text)
    topic=re.sub(r'최근에?\s*변경된|변경된|가장|현재|최신(?:의)?|최근|최종',' ',topic)
    topic=re.sub(r'고객사|관련된|관련|해당|이라는|파일|자료|문서|좀|부탁합니다|부탁해',' ',topic)
    topic=re.sub(r'(안전\s*평가\s*기준|평가\s*기준)',' 평가기준 ',topic)
    words=[]
    for word in re.findall(r'[가-힣A-Za-z0-9_.-]+',topic):
        word=re.sub(r'(?:으로|에서|에게|이라도|이랑|하고|을|를|의)$','',word)
        if word and word not in {'최신','최근','최종','있는','것','거','안전보건실'}and word not in words:words.append(word)
    if not words:return None
    purpose='평가기준'if'평가기준'in compact(topic)else None
    specific=[w for w in words if w not in {'평가기준','안전기준','기준','안전','양식','절차서','지침서','보고서','점검표'}]
    queries=[' '.join(words)]
    if purpose:
        queries.extend([' '.join([*specific,'평가']),' '.join([*specific,'기준'])])
    queries=list(dict.fromkeys(q[:100].strip()for q in queries if q.strip()))[:3]
    return {'queries':queries,'purpose':purpose,'specific':specific,'requires_revision':bool(re.search(r'최신|최근|최종',text)),'action':'QUESTION'if content_question else'FILE'}

def rank(item,query):
    # Filenames and the immediate folder are evidence of relevance, never proof of currency.
    components=item['relative_path'].replace('\\','/').split('/')[-2:]
    if query['purpose']=='평가기준':
        return 2 if any('평가기준'in compact(c)for c in components)else 0
    words=query['specific']
    return 2 if words and all(compact(w)in compact(item['file_name'])for w in words)else 1

def discover(user,text,search,*,source_workflow=False,source_choices_workflow=False,owner_sources=False):
    # Keep pure file finding, but do not let the old preflight turn a write request
    # into raw-original delivery or block it before the requester-bound worker.
    if source_workflow and re.search(r"수정(?:해|하|해서)|바꿔|바꾸|교체(?:해|하)|만들(?:어|고)|작성(?:해|하|해서)|생성(?:해|하)|요약(?:해|하)|정리(?:해|하)|바탕으로|참고해서",text):
        return {"handled":False,"items":[],"auto_select":False,"queued_source_work":True}
    query=plan(text)
    if owner_sources and source_workflow and query:return {'handled':False,'items':[],'auto_select':False,'queued_source_work':True}
    if source_choices_workflow and query and query['action']=='QUESTION':return {'handled':False,'items':[],'auto_select':False,'queued_source_work':True}
    if query is None:return {'handled':False,'items':[],'auto_select':False}
    found={};searched=[];complete=True
    for q in query['queries']:
        value=search(user,q)
        if not isinstance(value,dict)or not isinstance(value.get('items'),list)or type(value.get('complete'))is not bool:raise ValueError('EXACT_SEARCH_STATE_REQUIRED')
        searched.append(q);complete=complete and value['complete']
        for item in value['items']:found[(item['logical_root_id'],item['relative_path'])]=item
        if any(rank(item,query)==2 for item in found.values()):break
    rows=sorted(found.values(),key=lambda item:(-rank(item,query),item['relative_path']))
    strong=[item for item in rows if rank(item,query)==2]
    if not rows and source_workflow and source_choices_workflow:
        return {'handled':False,'items':[],'auto_select':False,'queued_source_work':True}
    auto=bool(complete and len(strong)==1 and query['specific']and not query['requires_revision'])
    return {'handled':True,'queries':searched,'items':strong or rows[:20],'auto_select':auto,'complete':complete,'revision_verified':False,'action':query['action']}
