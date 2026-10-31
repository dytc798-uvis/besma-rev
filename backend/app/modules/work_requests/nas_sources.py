"""Existing file-search membership and active-source rules, without a new NAS index."""
from fastapi import HTTPException
from app.modules.file_search.access import require_file_search_member, require_search
from app.modules.file_search.important_files import IMPORTANT_FILE_MEDIA_TYPES, _active_index_entry
from app.modules.file_search.index_database import IndexDatabase
from app.modules.file_search.schemas import IndexEntry, FolderSelector, FileSearchScope, SearchRequest, TEAM_SAFETY_NAS_DENIED_RELATIVE_PREFIXES
from .store import MAX_BYTES, MAX_ORIGINAL_BYTES, Conflict

# Original download formats; mobile publication and content analysis keep their own limits.
NAS_ORIGINAL_EXTENSIONS = frozenset(IMPORTANT_FILE_MEDIA_TYPES) | {".zip", ".xls"}


import hashlib,json,re,unicodedata
ACCIDENT_SOURCE=re.compile('사고(?=$|[/\\\\\\s_.()\\[\\]0-9-]|관리|조사|보고|접수|기록|이력|현황|대장|통계|경위|발생|사진|사례|자료|대응|처리|분석|원인|후속)|(?:^|[/\\\\\\s_.()\\[\\]0-9-])(?:accidents?|incidents?)(?=$|[/\\\\\\s_.()\\[\\]0-9-])',re.I)
def accident_source(value):return bool(ACCIDENT_SOURCE.search(unicodedata.normalize('NFC',value)))


class NasSources:
    def __init__(self, context_for_user=require_file_search_member, load_user=None):
        self.context_for_user=context_for_user
        self.load_user=load_user or self._load_user

    @staticmethod
    def _load_user(actor):
        from app.core.database import SessionLocal
        from app.modules.users.models import User
        with SessionLocal() as db:
            user=db.get(User,actor['id'])
            if (not user or user.login_id!=actor['login_id'] or not user.is_active or user.must_change_password
                    or user.ui_type!='HQ_SAFE' or getattr(user.role,'value',user.role) not in {'HQ_SAFE','HQ_SAFE_ADMIN','ACCIDENT_ADMIN','SUPER_ADMIN'}):
                raise HTTPException(404,'자료 이용 권한을 확인해 주세요.')
            db.expunge(user)
            return user

    def context(self,user):
        context=self.context_for_user(user);require_search(context)
        return context

    def available(self,user):
        try:self.context(user);return True
        except HTTPException as error:
            if error.status_code in {403,404}:return False
            raise

    def member_valid(self,actor):
        try:self.context(self.load_user(actor));return True
        except HTTPException as error:
            if error.status_code in {403,404}:return False
            raise

    @staticmethod
    def resolve(context,selector):
        if selector.scope is not FileSearchScope.TEAM_SAFETY_NAS:
            raise HTTPException(404,'공용 NAS 자료를 선택해 주세요.')
        with context.database.connection() as db:
            row=_active_index_entry(db,actor_user_id=context.actor_user_id,selector=selector)
        if row is None:raise HTTPException(404,'자료를 다시 찾아 선택해 주세요.')
        entry=IndexEntry.model_validate({key:row[key]for key in ['relative_path','file_name','extension','size','modified_at','is_directory']})
        compact=lambda value:''.join(value.casefold().split())
        compact_path=compact(entry.relative_path)
        if (accident_source(entry.relative_path) or entry.is_directory or entry.extension not in NAS_ORIGINAL_EXTENSIONS or not 0<entry.size<=MAX_ORIGINAL_BYTES
                or entry.modified_at is None or IndexDatabase._team_path_is_denied(entry.relative_path)
                or any(compact_path==compact(prefix)or compact_path.startswith(compact(prefix)+'/')for prefix in TEAM_SAFETY_NAS_DENIED_RELATIVE_PREFIXES)):
            raise HTTPException(404,'전송할 수 있는 공용 자료를 선택해 주세요.')
        result={'schema':1,'scope':'TEAM_SAFETY_NAS','logical_root_id':str(row['logical_root_id']),
                'installation_id':str(row['installation_id']),'source_session_id':str(row['session_id']),
                **entry.model_dump(mode='json'),'label':'안전보건실 NAS'}
        # A searchable filename is not a publication grant. Only the existing
        # explicit mobile publication can supply an automatic shared-content grant.
        from app.modules.file_search.routes import _require_important_file_access
        try:_require_important_file_access(context)
        except HTTPException as error:
            if error.status_code==404:return result
            raise
        with context.database.connection()as db:
            published=db.execute("SELECT file_id,content_sha256 FROM important_file_versions WHERE status='ACTIVE' AND scope='TEAM_SAFETY_NAS' AND logical_root_id=? AND relative_path_key=? AND indexed_size=? AND COALESCE(indexed_modified_at,'')=COALESCE(?,'')",(row['logical_root_id'],row['relative_path_key'],row['size'],row['modified_at'])).fetchone()
        if published:
            result['shared_file_id']=str(published['file_id']);result['approved_content_sha256']=str(published['content_sha256'])
        return result

    def search(self,user,q):
        return self.search_state(user,q)['items']

    def context_answer(self,actor,operation,limit):
        from datetime import datetime,timezone,timedelta
        from app.modules.file_search.routes import search,state_endpoint
        user=self.load_user(actor);context=self.context(user)
        sources=[s for s in state_endpoint(context)['sources'] if s['scope']=='TEAM_SAFETY_NAS' and s['logical_root_id']=='team-safety-nas-z4']
        if not sources:
            return {'status':'NEEDS_INFO','reply':'안전보건관리실의 검색자료를 아직 확인하지 못했습니다. 파일 목록을 다시 보내실 필요는 없습니다.'}
        count=sum(s['entry_count'] for s in sources)
        def stamp(value):
            try:
                parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
                if parsed.utcoffset() is None:return '시각 확인 필요'
                return parsed.astimezone(timezone(timedelta(hours=9))).strftime('%m/%d %H:%M')
            except (TypeError,ValueError,AttributeError):return '시각 확인 필요'
        generated=max((s.get('generated_at')or'' for s in sources),default='')
        freshness='검색자료 갱신: '+stamp(generated)+'.'
        if operation=='scope':
            return {'status':'COMPLETED','reply':f'현재 채팅에서는 안전보건관리실 NAS의 파일명과 폴더명 {count:,}건을 검색합니다. 원가관리팀 NAS는 별도 인덱스에 있으나 이 채팅의 NAS 검색에는 연결되지 않았습니다. 자료를 찾고, 이용 권한이 확인된 원본을 받아 보거나 그 내용으로 질문할 수 있습니다. NAS 전체가 연결된 상태는 아닙니다.\n{freshness} 색인 이후 바뀐 파일은 다음 갱신 전까지 반영되지 않을 수 있습니다.'}
        if operation!='recent' or type(limit)is not int or not 1<=limit<=10:
            raise ValueError('INVALID_METADATA_OPERATION')
        rows=[]
        for source in sources:
            selector=FolderSelector(scope='TEAM_SAFETY_NAS',logical_root_id=source['logical_root_id'],installation_id=source['installation_id'],relative_path='')
            found=search(SearchRequest(q='',scopes=['TEAM_SAFETY_NAS'],folder=selector,limit=500,sort='newest'),context)
            rows.extend(x for x in found['items'] if not x['is_directory'] and x['modified_at'] and not accident_source(x['relative_path']) and not IndexDatabase._team_path_is_denied(x['relative_path']))
        rows=sorted(rows,key=lambda x:(x['modified_at'],x['relative_path']),reverse=True)[:limit]
        if not rows:return {'status':'NEEDS_INFO','reply':'현재 검색자료에서 수정일이 확인된 파일을 찾지 못했습니다. 검색자료 상태를 확인해야 합니다.'}
        reply=f'안전보건관리실에서 최근 수정된 파일 {len(rows)}개입니다.\n'
        reply+='\n'.join(f"{i}. {x['file_name']} · {stamp(x['modified_at'])}\n   {x['relative_path'].rsplit('/',1)[0] if '/'in x['relative_path']else '안전보건관리실'}" for i,x in enumerate(rows,1))
        reply+=f'\n검색자료 갱신: {stamp(generated)}. 수정일 순서이며 최신 승인본이라는 뜻은 아닙니다.'
        return {'status':'COMPLETED','reply':reply,'_file_names':[x['file_name'] for x in rows]}

    def search_state(self,user,q,*,offset=0,sort='relevance',snapshot=None):
        # Reuse the original query semantics, limiter, audit and visibility predicates.
        from app.modules.file_search.routes import search
        context=self.context(user)
        def revision():
            rows=context.database.state(context.actor_user_id)
            generations=sorted((row['logical_root_id'],row['installation_id'],row['session_id'],row['sha256'])for row in rows if row['scope']=='TEAM_SAFETY_NAS')
            return hashlib.sha256(json.dumps([context.actor_user_id,unicodedata.normalize('NFC',q),sort,generations],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        current=revision()
        if (offset and not snapshot)or(snapshot is not None and snapshot!=current):
            raise HTTPException(409,'검색 자료가 갱신됐습니다. 처음부터 다시 찾아 주세요.')
        found=search(SearchRequest(q=q,scopes=['TEAM_SAFETY_NAS'],extensions=sorted(NAS_ORIGINAL_EXTENSIONS),limit=20,offset=offset,sort=sort),context)
        if offset>found['total_count']:raise HTTPException(409,'검색 범위가 달라졌습니다. 처음부터 다시 찾아 주세요.')
        sources=[];unavailable=0;excluded=0
        for item in found['items']:
            if item['is_directory'] or accident_source(item['relative_path']) or IndexDatabase._team_path_is_denied(item['relative_path']):excluded+=1;continue
            if item['size']>MAX_ORIGINAL_BYTES:
                unavailable+=1;continue
            try:
                selector=FolderSelector(scope=item['scope'],logical_root_id=item['logical_root_id'],installation_id=item['installation_id'],relative_path=item['relative_path'])
                sources.append(self.resolve(context,selector))
            except HTTPException as error:
                if error.status_code!=404:raise
                excluded+=1
        if revision()!=current:raise HTTPException(409,'검색 자료가 갱신됐습니다. 처음부터 다시 찾아 주세요.')
        scanned=offset+len(found['items']);next_offset=scanned if scanned<found['total_count'] else None
        return {'items':sources,'total_count':found['total_count'],'complete':next_offset is None,'unavailable_count':unavailable,'original_max_bytes':MAX_ORIGINAL_BYTES,'offset':offset,'next_offset':next_offset,'scanned_count':scanned,'excluded_count':excluded,'snapshot':current,'sort':sort}

    def validate(self,actor,source):
        user=self.load_user(actor);context=self.context(user)
        if not isinstance(source,dict)or source.get('schema')!=1:raise Conflict('INVALID_NAS_SOURCE')
        selector=FolderSelector.model_validate({k:source.get(k)for k in ['scope','logical_root_id','installation_id','relative_path']})
        current=self.resolve(context,selector)
        # Daily re-indexing alone does not revoke an unchanged original or grant.
        ignored={'source_session_id'}
        if not source.get('shared_file_id'):ignored|={'shared_file_id','approved_content_sha256'}
        stable=lambda value:{k:v for k,v in value.items()if k not in ignored}
        if stable(current)!=stable(source):raise Conflict('NAS_SOURCE_CHANGED')
        return current

    def valid(self,actor,source):
        try:self.validate(actor,source);return True
        except (Conflict,ValueError):return False
        except HTTPException as error:
            if error.status_code in {403,404}:return False
            raise
