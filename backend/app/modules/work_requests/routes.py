"""Opt-in production wiring. Importing does not create stores or start a worker."""
import json
from pathlib import Path
from app.config.settings import settings
from app.core.auth import get_current_user
from .api import RequestConfig, create_router
from .store import RequestStore, safe_path
from .access import headquarters_user

LEGACY_ROOT=Path(settings.storage_root)/'work-requests'
ROOT=Path('/srv/besma/work-requests-private')if settings.env=='prod'else Path(settings.storage_root).parent/'work-requests-private'


class OptionalNasSources:
    """Questions and generated documents do not require a NAS-search deployment."""
    def __init__(self):
        self._instance = None
        self._missing = False

    def _backend(self):
        if self._missing:
            return None
        if self._instance is None:
            try:
                from .nas_sources import NasSources
                self._instance = NasSources()
            except ModuleNotFoundError as error:
                if not (error.name == 'app.modules.file_search' or
                        error.name and error.name.startswith('app.modules.file_search.')):
                    raise
                self._missing = True
        return self._instance

    def available(self, user):
        backend = self._backend()
        return bool(backend is not None and backend.available(user))

    def valid(self, user, source):
        backend = self._backend()
        return bool(backend is not None and backend.valid(user, source))

    def member_valid(self, user):
        backend = self._backend()
        return bool(backend is not None and backend.member_valid(user))

    def search(self, user, query):
        backend = self._backend()
        if backend is None:
            from fastapi import HTTPException
            raise HTTPException(404, 'NAS 자료 요청을 준비하고 있습니다.')
        return backend.search(user, query)

    def load_user(self, actor):
        backend=self._backend()
        if backend is None:
            from fastapi import HTTPException
            raise HTTPException(404,'NAS 자료 요청을 준비하고 있습니다.')
        return backend.load_user(actor)

    def validate(self, actor, source):
        backend=self._backend()
        if backend is None:
            from fastapi import HTTPException
            raise HTTPException(404,'NAS 자료 요청을 준비하고 있습니다.')
        return backend.validate(actor,source)

    def search_state(self,user,query):
        backend=self._backend()
        if backend is None:
            from fastapi import HTTPException
            raise HTTPException(404,'NAS 자료 요청을 준비하고 있습니다.')
        return backend.search_state(user,query)

    def context_answer(self,actor,operation,limit):
        backend=self._backend()
        if backend is None:
            from fastapi import HTTPException
            raise HTTPException(404,'NAS 검색 연결을 확인해 주세요.')
        return backend.context_answer(actor,operation,limit)


def private_root_ready():
    root=safe_path(ROOT).resolve();storage=Path(settings.storage_root).resolve()
    if root==storage or root.is_relative_to(storage)or storage.is_relative_to(root):raise RuntimeError('PRIVATE_REQUEST_ROOT_REQUIRED')
    if (ROOT/'migration-incomplete.json').exists():raise RuntimeError('PRIVATE_QUEUE_MIGRATION_INCOMPLETE')
    if (LEGACY_ROOT/'requests.sqlite3').is_file()and not (ROOT/'requests.sqlite3').is_file():
        raise RuntimeError('EXPLICIT_LEGACY_PRIVATE_MOVE_REQUIRED')


def migrate_legacy_private():
    """Offline administrative operation; not an HTTP capability or startup action."""
    target=RequestStore(ROOT);copied=target.copy_from_legacy(LEGACY_ROOT)
    return {'copy':copied,'schema':target.upgrade_v1()}


def get_config():
    private_root_ready()
    file=safe_path(ROOT/'config.json')
    if not file.is_file():return RequestConfig()
    raw=json.loads(file.read_text(encoding='utf-8'))
    required={'schema','enabled','members','owner'}
    if (not required<=set(raw)<=required|{'nas_files_enabled','naver_delivery_enabled','source_lookup_enabled','source_generation_enabled','workbook_edit_enabled','owner_result_followup_enabled','image_source_comparison_enabled'}or raw['schema']!=1 or type(raw['enabled'])is not bool
            or type(raw.get('nas_files_enabled',False))is not bool or type(raw.get('naver_delivery_enabled',False))is not bool or type(raw.get('source_lookup_enabled',False))is not bool or type(raw.get('source_generation_enabled',False))is not bool or type(raw.get('workbook_edit_enabled',False))is not bool or type(raw.get('owner_result_followup_enabled',False))is not bool or type(raw.get('image_source_comparison_enabled',False))is not bool):
        raise ValueError('INVALID_WORK_REQUEST_CONFIG')
    def pair(value):
        if (not isinstance(value,list) or len(value)!=2 or type(value[0])is not int
                or value[0]<1 or not isinstance(value[1],str) or not value[1] or len(value[1])>100):
            raise ValueError('EXACT_SERVER_IDENTITY_REQUIRED')
        return tuple(value)
    members=tuple(pair(x) for x in raw['members']);owner=pair(raw['owner'])
    if len(members)>20 or len(set(members))!=len(members):raise ValueError('INVALID_TEAM_MEMBERS')
    return RequestConfig(enabled=raw['enabled'],members=members,owner=owner,nas_files_enabled=raw.get('nas_files_enabled',False),naver_delivery_enabled=raw.get('naver_delivery_enabled',False),source_lookup_enabled=raw.get('source_lookup_enabled',False),source_generation_enabled=raw.get('source_generation_enabled',False),workbook_edit_enabled=raw.get('workbook_edit_enabled',False),owner_result_followup_enabled=raw.get('owner_result_followup_enabled',False),image_source_comparison_enabled=raw.get('image_source_comparison_enabled',False))


def get_store():
    private_root_ready()
    store=RequestStore(ROOT)
    if not store.database.is_file():raise RuntimeError('EXPLICIT_STORE_INITIALIZATION_REQUIRED')
    return store


def eligible_actors():
    from app.core.database import SessionLocal
    from app.modules.users.models import User
    cfg=get_config()
    if not cfg.enabled:return []
    pairs={*cfg.members,cfg.owner}
    with SessionLocal() as db:
        rows=db.query(User).filter(User.id.in_([p[0] for p in pairs])).all()
        return [{'id':u.id,'login_id':u.login_id,'display_name':u.name,'owner':(u.id,u.login_id)==cfg.owner} for u in rows
                if (u.id,u.login_id) in pairs and headquarters_user(u)]


router=create_router(get_current_user,get_config,get_store,eligible_actors,OptionalNasSources())
