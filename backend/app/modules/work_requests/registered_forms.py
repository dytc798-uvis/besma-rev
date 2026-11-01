"""Exact registered-form originals; reuse document-explorer download authorization.

This is a separate provider, never a NAS path or a same-name NAS substitution.
The queue stores only an immutable relative reference and content fingerprint.
"""
from pathlib import Path, PurePosixPath
import hashlib, os, re, stat, unicodedata
from fastapi import HTTPException
from .nas_sources import accident_source

SCOPE='BESMA_REGISTERED_FORM'
CAP='REGISTERED_FORM_SOURCE_V1'
MAX_BYTES=32*1024*1024
EXTENSIONS=frozenset({'.txt','.csv','.pdf','.hwp','.hwpx','.docx','.xlsx','.pptx','.xls','.zip'})
ROLES=frozenset({'HQ_SAFE','HQ_SAFE_ADMIN','ACCIDENT_ADMIN','SUPER_ADMIN'})

def relative_path(value):
    if (not isinstance(value,str)or not 6<=len(value)<=1600 or value!=unicodedata.normalize('NFC',value)
            or '\\'in value or any(ord(c)<32 for c in value)or ':'in value or '%'in value):
        raise ValueError('등록 양식의 원본 경로를 확인해 주세요.')
    parts=value.split('/')
    if parts[0]!='base'or any(p in {'','.','..'}for p in parts)or accident_source(value):
        raise ValueError('등록 양식의 원본을 선택해 주세요.')
    if PurePosixPath(value).suffix.lower()not in EXTENSIONS:
        raise ValueError('채팅에서 사용할 수 있는 양식 형식을 확인해 주세요.')
    return value


class RegisteredForms:
    def __init__(self,load_user=None,resolve_file=None):
        self.load_user=load_user or self._load_user
        self.resolve_file=resolve_file or self._resolve_file

    @staticmethod
    def _load_user(actor):
        # Existing active HQ download boundary, without NAS membership substitution.
        from .nas_sources import NasSources
        return NasSources._load_user(actor)

    @staticmethod
    def _authorize(user):
        from .access import headquarters_user
        role=getattr(user.role,'value',user.role)
        if not headquarters_user(user)or role not in ROLES:
            raise HTTPException(404,'등록 양식 이용 권한을 확인해 주세요.')
        from app.modules.document_explorer.routes import _assert_document_explorer_access
        _assert_document_explorer_access(user)

    @staticmethod
    def _resolve_file(user,relative):
        from app.core.database import SessionLocal
        from app.modules.document_explorer.routes import open_or_download_document_explorer_file
        with SessionLocal()as db:
            response=open_or_download_document_explorer_file(db,user,relative,'attachment')
        return Path(response.path)

    def member_valid(self,actor):
        try:self._authorize(self.load_user(actor));return True
        except HTTPException as error:
            if error.status_code in {403,404}:return False
            raise

    def snapshot(self,actor,relative):
        relative=relative_path(relative);user=self.load_user(actor);self._authorize(user)
        path=Path(self.resolve_file(user,relative))
        # The resolver is the existing authorized download handler, not user input.
        before=path.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):raise ValueError('등록 양식의 원본 파일을 선택해 주세요.')
        if before.st_size==0:raise ValueError('내용이 없는 파일입니다. 내용이 있는 원본을 선택해 주세요.')
        if before.st_size>MAX_BYTES:raise ValueError('채팅에서는 32MB 이하 등록 양식을 선택해 주세요.')
        flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
        fd=os.open(path,flags)
        with os.fdopen(fd,'rb')as stream:
            opened=os.fstat(stream.fileno())
            if (opened.st_dev,opened.st_ino,opened.st_size,opened.st_mtime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns):
                raise ValueError('양식이 변경되었습니다. 다시 선택해 주세요.')
            content=stream.read(MAX_BYTES+1);after=os.fstat(stream.fileno())
        final=path.stat(follow_symlinks=False)
        fingerprint=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if len(content)!=before.st_size or len(content)>MAX_BYTES or fingerprint(before)!=fingerprint(after)or fingerprint(before)!=fingerprint(final):
            raise ValueError('양식이 변경되었습니다. 다시 선택해 주세요.')
        source={'schema':1,'scope':SCOPE,'logical_root_id':'besma-registered-base','relative_path':relative,
                'file_name':PurePosixPath(relative).name,'extension':PurePosixPath(relative).suffix.lower(),
                'size':len(content),'is_directory':False,'label':'BESMA 등록 양식',
                'approved_content_sha256':hashlib.sha256(content).hexdigest()}
        return source,content

    def read(self,actor,source):
        if (not isinstance(source,dict)or source.get('schema')!=1 or source.get('scope')!=SCOPE
                or source.get('logical_root_id')!='besma-registered-base'
                or not re.fullmatch('[a-f0-9]{64}',source.get('approved_content_sha256',''))):
            raise ValueError('등록 양식의 원본 연결을 확인해 주세요.')
        current,raw=self.snapshot(actor,source.get('relative_path'))
        if current!=source:raise ValueError('양식이 변경되었습니다. 다시 선택해 주세요.')
        return raw

    def valid(self,actor,source):
        try:self.read(actor,source);return True
        except HTTPException as error:
            if error.status_code in {400,403,404}:return False
            raise
        except(OSError,ValueError,TypeError):return False
