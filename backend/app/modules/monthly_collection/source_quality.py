"""Read-only source-month notes from received metadata; never grade or rewrite it."""
from collections import defaultdict
import calendar,re

MONTH=re.compile(r'20\d{2}-(0[1-9]|1[0-2])\Z')
NAMED_MONTH=re.compile(r'(?<!\d)(20\d{2}|\d{2})\s*년\s*(1[0-2]|0?[1-9])\s*월')
SHA=re.compile(r'[a-f0-9]{64}\Z')

def named_months(filename):
    if not isinstance(filename,str):return set()
    return {('20'+year if len(year)==2 else year)+'-'+month.zfill(2) for year,month in NAMED_MONTH.findall(filename)}

def notes_by_id(snapshot):
    """Equal receipt hashes show equal originals, not equal monthly fulfillment."""
    rows=snapshot.get('items',[])
    if not isinstance(rows,list):return {}
    months=defaultdict(set)
    for row in rows:
        if not isinstance(row,dict):continue
        digest=row.get('sha256');size=row.get('size');month=row.get('month')
        if isinstance(digest,str)and SHA.fullmatch(digest)and type(size)is int and size>0 and isinstance(month,str)and MONTH.fullmatch(month):
            months[(row.get('category'),digest,size)].add(month)
    result={}
    for row in rows:
        if not isinstance(row,dict):continue
        key=row.get('id');month=row.get('month')
        if not isinstance(key,str)or not SHA.fullmatch(key)or not isinstance(month,str)or not MONTH.fullmatch(month):continue
        notes=[];named=named_months(row.get('filename'))
        if len(named)==1 and month not in named:
            notes.append('자료월 확인: 등록 '+month.replace('-','.')+' / 파일명 '+next(iter(named)).replace('-','.'))
        digest=row.get('sha256');size=row.get('size')
        if isinstance(digest,str)and SHA.fullmatch(digest)and type(size)is int and size>0:
            others=sorted(months.get((row.get('category'),digest,size),set())-{month})
            if others:
                text=', '.join(value.replace('-','.')for value in others[:3])
                if len(others)>3:text+=' 외 '+str(len(others)-3)+'개 월'
                notes.append('다른 자료월과 같은 원본: '+text)
        if notes:result[key]=notes
    # Explicit review codes bind only to these exact received bytes; no free-text source content.
    reviewed=snapshot.get('reviewed_source_notes',[])
    index={r.get('id'):r for r in rows if isinstance(r,dict)}
    if isinstance(reviewed,list)and len(reviewed)<=1000:
        for note in reviewed:
            if not isinstance(note,dict):continue
            key=note.get('id')
            if not isinstance(key,str)or not SHA.fullmatch(key):continue
            row=index.get(key);digest=note.get('sha256')
            if row is None or not isinstance(digest,str)or not SHA.fullmatch(digest)or row.get('sha256')!=digest:continue
            kind=note.get('kind');message=None
            if kind=='PERIOD'and set(note)=={'id','sha256','kind','document_month'}:
                period=note['document_month'];month=row.get('month')
                if isinstance(period,str)and MONTH.fullmatch(period)and isinstance(month,str)and MONTH.fullmatch(month)and period!=month:
                    message='원문 날짜 확인: '+period.replace('-','.')+' / 등록 자료월 '+month.replace('-','.')
            elif kind=='PAGES'and set(note)=={'id','sha256','kind','present','expected'}:
                present=note['present'];expected=note['expected']
                if type(present)is int and type(expected)is int and 1<=present<expected<=1000:
                    message=f'원문 확인: PDF {present}쪽 / 원문 표기 {expected}쪽. 전체 자료 여부 확인 필요'
            elif kind=='LABEL_MONTH'and set(note)=={'id','sha256','kind','label_month'}:
                label=note['label_month'];month=row.get('month')
                if type(label)is int and 1<=label<=12 and isinstance(month,str)and MONTH.fullmatch(month)and label!=int(month[5:]):
                    message=f'원문 월 표기 확인: 표제 {label}월 / 등록 자료월 '+month.replace('-','.')
            elif kind=='INVALID_DATE'and set(note)=={'id','sha256','kind','document_month','day'}:
                month=note['document_month'];day=note['day']
                if isinstance(month,str)and MONTH.fullmatch(month)and type(day)is int and 0<=day<=31 and (day==0 or day>calendar.monthrange(int(month[:4]),int(month[5:]))[1]):
                    message=f'원문 날짜 확인: {month.replace("-",".")}.{day:02d}은 존재하지 않는 날짜입니다.'
            elif kind=='OPINION_NONE_DECLARED'and set(note)=={'id','sha256','kind','date_scope'}and row.get('category')=='opinions':
                scope=note['date_scope']
                if isinstance(scope,str)and scope in ('DAY','PERIOD_ONLY','MISSING'):
                    message='원문 의견표: ‘해당 없음’으로 기재'
                    if scope=='PERIOD_ONLY':message+=' · 의견일자는 기간만 표시'
                    elif scope=='MISSING':message+=' · 의견일자 없음'
            elif kind=='OPINION_STATE_DIFFERENCE'and set(note)=={'id','sha256','kind'}and row.get('category')=='opinions':
                message='같은 의견의 원본별 조치상태가 다릅니다.'
            if message and message not in result.get(row['id'],[]):result.setdefault(row['id'],[]).append(message)

    return result
