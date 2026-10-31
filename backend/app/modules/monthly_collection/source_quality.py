"""Read-only source-month notes from received metadata; never grade or rewrite it."""
from collections import defaultdict
import re

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
    return result
