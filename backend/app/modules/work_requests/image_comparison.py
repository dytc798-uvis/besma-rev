"""Bounded same-user photo context. Metadata never grants NAS source access."""
import re
from .store import Conflict

CAP='UPLOADED_IMAGE_SOURCE_V1'

def intent(text):
    current=text.rsplit('\n\n현재 요청:\n',1)[-1]
    return bool(re.search(r'사진|첨부|여기에|이\s*중|그\s*중|비교|명단|명부|리스트|누락|빠진|\d+\s*번\s*폴더',current))

def needs_source(text):
    current=text.rsplit('\n\n현재 요청:\n',1)[-1]
    return bool(re.search(r'없는|비교|명단|명부|리스트|누락|빠진|폴더',current))

def inputs(connection,row):
    from .input_images import for_request
    direct=for_request(connection,row['id'])
    if direct:return [dict(item,context_request_id=row['id'])for item in direct]
    if row['kind']!='QUESTION'or not intent(row['body']):return []
    current=row;seen={row['id']};pair=(row['user_id'],row['login_id']);conversation=row['conversation_id']or row['id']
    for _ in range(20):
        parent=current['parent_request_id']
        if not parent:return []
        if parent in seen:raise Conflict('IMAGE_CONTEXT_CYCLE')
        seen.add(parent)
        current=connection.execute('SELECT * FROM requests WHERE id=?',(parent,)).fetchone()
        if current is None or (current['user_id'],current['login_id'])!=pair or (current['conversation_id']or current['id'])!=conversation:
            raise KeyError('NOT_FOUND')
        if current['status']in {'CANCELLED','DECLINED','ACCESS_REVOKED'}:return []
        direct=for_request(connection,current['id'])
        if direct:
            if len(direct)!=1:raise Conflict('EXACT_IMAGE_CONTEXT_REQUIRED')
            return [dict(direct[0],context_request_id=current['id'])]
    return []

def require_lookup(cfg,connection,row,action='QUESTION'):
    from .input_images import for_request
    photos=inputs(connection,row)if cfg.image_source_comparison_enabled else for_request(connection,row['id'])
    if photos and (not cfg.image_source_comparison_enabled or action!='QUESTION'):
        raise Conflict('IMAGE_SOURCE_COMPARISON_DISABLED')
    return photos
