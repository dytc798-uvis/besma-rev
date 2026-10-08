"""Manual, authenticated government document export. No background sync."""
import hashlib
import re
from pathlib import Path

from fastapi import HTTPException
from app.config.settings import settings
from app.modules.documents.storage_paths import resolve_existing_storage_path
from .core import CATEGORIES, GOV_CATEGORY, government_documents, readonly, period_key


def safe_label(value, limit=90):
    value=re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(value or '')).strip(' .')[:limit]
    return value if value and value not in {'.','..'} else '서류'


def export_items(month):
    storage=Path(settings.storage_root).resolve()
    result=[];seen=set();unavailable=0
    with readonly(settings.sqlite_path) as main:
        docs=government_documents(main)
        versions=[]
        for d in docs:
            versions.append(d)
            for h in main.execute('SELECT version_no,file_name,file_path,file_size,uploaded_at FROM document_upload_histories WHERE document_id=? AND file_path IS NOT NULL ORDER BY id',(d['id'],)):
                if h['version_no']!=d['version_no']:
                    versions.append({**d,**dict(h),'original_file_path':None})
        for d in versions:
            day=d['period_start'] or str(d['uploaded_at'] or '')[:10]
            if not day:continue
            req=main.execute('SELECT title,frequency FROM document_requirements WHERE site_id=? AND code=? LIMIT 1',(d['site_id'],d['code'])).fetchone()
            frequency=req['frequency'] if req else 'MONTHLY'
            # Startup records stay available in every month's view.
            if frequency not in {'EVENT','ADHOC'} and day[:7]!=month:
                if not (d['period_start'] and d['period_end'] and d['period_start'][:7]<=month<=d['period_end'][:7]):continue
            p=resolve_existing_storage_path(storage,d['original_file_path'] or d['file_path'],instance_id=d['instance_id'],file_name=d['file_name'],version_no=d['version_no'])
            if p is None or p.is_symlink() or not p.resolve().is_relative_to(storage):unavailable+=1;continue
            before=p.stat();content=p.read_bytes();after=p.stat()
            if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise HTTPException(409,'SOURCE_CHANGED')
            sha=hashlib.sha256(content).hexdigest();key=f"{d['id']}-{d['version_no']}-{sha}"
            if key in seen:continue
            seen.add(key)
            cat=GOV_CATEGORY[d['code']]
            label=safe_label((req['title'] if req else d['code']).removeprefix('관급 '))
            site=safe_label(re.sub(r'^\[[^]]+\]\s*','',d['site_name']),65)
            source_month=day[:7];yy,mm=source_month.split('-');folder=f'{yy[2:]}.{mm}월'
            parts=[CATEGORIES[cat][1],'관급',folder]
            if cat=='nonconformity':parts.append(period_key('WEEKLY',d['period_end'] or day))
            parts += [d['site_code']+' '+site,label]
            name=f"{d['site_code']}_문서{d['id']}_v{d['version_no']}_{sha[:10]}_"+safe_label(d['file_name'] or p.name,100)
            result.append({'key':key,'relative_path':'/'.join(parts+[name]),'sha256':sha,'size':len(content),'path':p})
    return result,unavailable


def public_plan(month):
    rows,unavailable=export_items(month)
    return {'month':month,'items':[{k:v for k,v in r.items() if k!='path'} for r in rows],
            'unavailable_count':unavailable,'nas_root_name':'★월간 자료 취합'}


def content_for(month,key):
    if not re.fullmatch(r'\d+-\d+-[0-9a-f]{64}',key):raise HTTPException(400,'INVALID_EXPORT_KEY')
    rows,_=export_items(month)
    row=next((r for r in rows if r['key']==key),None)
    if row is None:raise HTTPException(404,'FILE_NOT_FOUND_OR_CHANGED')
    content=row['path'].read_bytes()
    if hashlib.sha256(content).hexdigest()!=row['sha256']:raise HTTPException(409,'SOURCE_CHANGED')
    return row,content
