from __future__ import annotations

import logging
import math
import re
import sqlite3
import threading
import time
from collections import OrderedDict, deque
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Path, Query, Request, UploadFile, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.modules.file_search.access import FileSearchContextDep, require_search
from app.modules.file_search.important_files import (
    IMPORTANT_FILES_CONTRACT_VERSION,
    IMPORTANT_FILE_EXPLICIT_CONFIRMATION,
    IMPORTANT_FILE_MEDIA_TYPES,
    IMPORTANT_FILE_RETENTION_DAYS,
    IMPORTANT_FILE_RETIRE_CONFIRMATION,
    ImportantFileContractError,
    discard_staged_upload,
    important_storage_is_isolated,
    list_visible_important_files,
    publish_explicit_important_file,
    resolve_important_file_for_download,
    retire_important_file,
    stage_explicit_upload,
    validate_upload_selection,
)
from app.modules.file_search.index_database import IndexDatabaseContractError
from app.modules.file_search.schemas import (
    FILE_SEARCH_CONTRACT_VERSION,
    FileSearchScope,
    FolderRequest,
    IndexChunkRequest,
    IndexSessionBeginRequest,
    MAX_CHUNK_REQUEST_BYTES,
    SearchRequest,
    SearchResponse,
    TEAM_SAFETY_NAS_LOGICAL_ROOT_ID,
    normalize_nfc,
    normalize_query_tokens,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/desktop/v1/file-search", tags=["desktop-file-search"])
important_files_router = APIRouter(
    prefix="/file-access/v1/important-files",
    tags=["important-file-access"],
)
_PERSONAL_SOURCE_ID_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_INSTALLATION_ID_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_SESSION_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SEARCH_RATE_LIMIT_PER_MINUTE = 20
SEARCH_RATE_LIMIT_WINDOW_SECONDS = 60.0
SEARCH_RATE_LIMIT_MAX_ACTORS = 1_000
STATE_RATE_LIMIT_PER_MINUTE = 30
GENERAL_RATE_LIMIT_PER_MINUTE = 180


class _ActorRateLimiter:
    def __init__(self, *, limit: int, window_seconds: float, max_actors: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._max_actors = max_actors
        self._lock = threading.Lock()
        self._events: OrderedDict[int, deque[float]] = OrderedDict()

    def retry_after(self, actor_user_id: int) -> int | None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        with self._lock:
            events = self._events.setdefault(actor_user_id, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            self._events.move_to_end(actor_user_id)
            if len(events) >= self._limit:
                return max(1, math.ceil(self._window_seconds - (now - events[0])))
            events.append(now)
            while len(self._events) > self._max_actors:
                self._events.popitem(last=False)
        return None

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_search_rate_limiter = _ActorRateLimiter(
    limit=SEARCH_RATE_LIMIT_PER_MINUTE,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)
_state_rate_limiter = _ActorRateLimiter(
    limit=STATE_RATE_LIMIT_PER_MINUTE,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)
_general_rate_limiter = _ActorRateLimiter(
    limit=GENERAL_RATE_LIMIT_PER_MINUTE,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)
_important_upload_rate_limiter = _ActorRateLimiter(
    limit=10,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)
_folder_rate_limiter = _ActorRateLimiter(
    limit=60,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)
_important_list_rate_limiter = _ActorRateLimiter(
    limit=30,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)
_important_download_rate_limiter = _ActorRateLimiter(
    limit=60,
    window_seconds=SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    max_actors=SEARCH_RATE_LIMIT_MAX_ACTORS,
)


def _enforce_general_rate_limit(actor_user_id: int) -> None:
    retry_after = _general_rate_limiter.retry_after(actor_user_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FILE_SEARCH_GENERAL_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )


def _raise_contract_error(exception: IndexDatabaseContractError) -> None:
    if exception.code in {
        "FILE_SEARCH_SESSION_NOT_FOUND",
        "FILE_SEARCH_PERSONAL_SOURCE_NOT_FOUND",
    }:
        code = status.HTTP_404_NOT_FOUND
    elif exception.conflict:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=exception.code) from exception


def _raise_important_file_error(exception: ImportantFileContractError) -> None:
    if exception.not_found:
        code = status.HTTP_404_NOT_FOUND
    elif exception.unavailable:
        code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif exception.code == "IMPORTANT_FILE_TOO_LARGE":
        code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    elif exception.conflict:
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    raise HTTPException(status_code=code, detail=exception.code) from exception


def _require_important_file_access(context, *, upload: bool = False) -> None:
    require_search(context)
    if not settings.file_search_important_files_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IMPORTANT_FILES_DISABLED",
        )
    if not important_storage_is_isolated(
        settings.file_search_important_files_root,
        index_database_path=settings.file_search_db_path,
        business_database_path=settings.sqlite_path,
        business_storage_root=settings.storage_root,
        require_production_path=settings.env == "prod",
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IMPORTANT_FILE_STORAGE_NOT_ISOLATED",
        )
    if upload and not context.member.can_upload_personal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IMPORTANT_FILE_UPLOAD_FORBIDDEN",
        )


def _session_for_actor(context, session_id: str):
    row = context.database.session(session_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FILE_SEARCH_SESSION_NOT_FOUND")
    if row["scope"] == FileSearchScope.PERSONAL.value:
        allowed = (
            int(row["owner_user_id"]) == context.actor_user_id
            and context.member.can_upload_personal
        )
    else:
        allowed = context.member.can_publish_nas
    # Staging uploads cannot be taken over by another publisher.
    allowed = allowed and int(row["created_by_user_id"]) == context.actor_user_id
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FILE_SEARCH_SESSION_NOT_FOUND")
    return row


@router.get("/capabilities")
def capabilities(context: FileSearchContextDep) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    important_storage_ready = important_storage_is_isolated(
        settings.file_search_important_files_root,
        index_database_path=settings.file_search_db_path,
        business_database_path=settings.sqlite_path,
        business_storage_root=settings.storage_root,
        require_production_path=settings.env == "prod",
    )
    important_files_enabled = (
        settings.file_search_important_files_enabled and important_storage_ready
    )
    return {
        "contract_version": FILE_SEARCH_CONTRACT_VERSION,
        "account_scope_id": context.account_scope_id,
        "can_search": context.member.can_search,
        "can_upload_personal": context.member.can_upload_personal,
        "can_publish_nas": context.member.can_publish_nas,
        "important_files": {
            "enabled": important_files_enabled,
            "storage_isolated": important_storage_ready,
            "contract_version": IMPORTANT_FILES_CONTRACT_VERSION,
            "can_upload_important": (
                important_files_enabled
                and context.member.can_search
                and context.member.can_upload_personal
            ),
            "upload_path": "/file-access/v1/important-files",
            "explicit_confirmation": IMPORTANT_FILE_EXPLICIT_CONFIRMATION,
            "max_file_bytes": min(
                settings.file_search_important_file_max_bytes,
                5 * 1024 * 1024,
            ),
            "allowed_extensions": sorted(IMPORTANT_FILE_MEDIA_TYPES),
            "retention_days": IMPORTANT_FILE_RETENTION_DAYS,
            "active_files_per_owner": settings.file_search_important_active_files_per_owner,
            "active_bytes_per_owner": settings.file_search_important_active_bytes_per_owner,
            "total_active_bytes": settings.file_search_important_total_active_bytes,
        },
        "besma_records": {
            "status": "PLANNED_LINK_ONLY",
            "available": False,
            "url": "https://www.besma.co.kr/",
        },
    }


@router.post("/index-sessions", status_code=status.HTTP_201_CREATED)
def begin_index_session(body: IndexSessionBeginRequest, context: FileSearchContextDep) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    if body.scope is FileSearchScope.PERSONAL and not context.member.can_upload_personal:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FILE_SEARCH_PERSONAL_UPLOAD_FORBIDDEN")
    if body.scope is FileSearchScope.TEAM_SAFETY_NAS and not context.member.can_publish_nas:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FILE_SEARCH_NAS_PUBLISH_FORBIDDEN")
    try:
        return context.database.begin_session(context.actor_user_id, body)
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)


@router.put("/index-sessions/{session_id}/chunks/{chunk_number}")
def put_index_chunk(
    body: IndexChunkRequest,
    context: FileSearchContextDep,
    request: Request,
    session_id: str = Path(min_length=36, max_length=36),
    chunk_number: int = Path(ge=0, le=1_000_000),
) -> dict:
    raw_content_length = request.headers.get("content-length")
    try:
        content_length = int(raw_content_length) if raw_content_length is not None else -1
    except ValueError:
        content_length = -1
    if not 0 <= content_length <= MAX_CHUNK_REQUEST_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="FILE_SEARCH_CHUNK_BODY_TOO_LARGE",
        )
    _session_for_actor(context, session_id)
    try:
        return context.database.put_chunk(session_id, chunk_number, body.sha256, body.entries)
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)


@router.post("/index-sessions/{session_id}/commit")
def commit_index_session(
    context: FileSearchContextDep,
    session_id: str = Path(min_length=36, max_length=36),
) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    _session_for_actor(context, session_id)
    try:
        return context.database.commit_session(session_id)
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)


@router.delete("/sources/personal/{logical_root_id}")
def retire_personal_source(
    context: FileSearchContextDep,
    logical_root_id: str = Path(min_length=1, max_length=128),
    installation_id: str = Query(..., min_length=32, max_length=32),
) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    if not context.member.can_upload_personal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FILE_SEARCH_PERSONAL_UPLOAD_FORBIDDEN",
        )
    if (
        not _PERSONAL_SOURCE_ID_RE.fullmatch(logical_root_id)
        or not _INSTALLATION_ID_RE.fullmatch(installation_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILE_SEARCH_PERSONAL_SOURCE_NOT_FOUND",
        )
    try:
        return context.database.retire_personal_source(
            context.actor_user_id,
            logical_root_id.lower(),
            installation_id.lower(),
        )
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception


@router.delete("/sources/personal/{logical_root_id}/staging")
def abort_personal_staging(
    context: FileSearchContextDep,
    logical_root_id: str = Path(min_length=1, max_length=128),
    installation_id: str = Query(..., min_length=32, max_length=32),
) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    if not context.member.can_upload_personal:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FILE_SEARCH_PERSONAL_UPLOAD_FORBIDDEN",
        )
    if (
        not _PERSONAL_SOURCE_ID_RE.fullmatch(logical_root_id)
        or not _INSTALLATION_ID_RE.fullmatch(installation_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILE_SEARCH_PERSONAL_SOURCE_NOT_FOUND",
        )
    try:
        return context.database.abort_personal_staging(
            context.actor_user_id,
            logical_root_id.lower(),
            installation_id.lower(),
        )
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception


@router.delete("/sources/team-safety-nas/staging")
def abort_team_staging(
    context: FileSearchContextDep,
    installation_id: str = Query(..., min_length=32, max_length=32),
) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    if not context.member.can_publish_nas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FILE_SEARCH_NAS_PUBLISH_FORBIDDEN",
        )
    if not _INSTALLATION_ID_RE.fullmatch(installation_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILE_SEARCH_TEAM_SOURCE_NOT_FOUND",
        )
    try:
        result = context.database.abort_team_staging(
            context.actor_user_id,
            installation_id.lower(),
        )
        if result["logical_root_id"] != TEAM_SAFETY_NAS_LOGICAL_ROOT_ID:
            raise IndexDatabaseContractError("FILE_SEARCH_TEAM_STAGING_ABORT_INCOMPLETE")
        return result
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception


@router.delete("/sources/team-safety-nas/staging/{session_id}")
def abort_team_staging_session(
    context: FileSearchContextDep,
    session_id: str = Path(min_length=36, max_length=36),
    installation_id: str = Query(..., min_length=32, max_length=32),
) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    if not context.member.can_publish_nas:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="FILE_SEARCH_NAS_PUBLISH_FORBIDDEN",
        )
    if (
        not _INSTALLATION_ID_RE.fullmatch(installation_id)
        or not _SESSION_ID_RE.fullmatch(session_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILE_SEARCH_TEAM_SOURCE_NOT_FOUND",
        )
    try:
        return context.database.abort_team_staging_session(
            context.actor_user_id,
            installation_id.lower(),
            session_id.lower(),
        )
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception


def _parse_scopes(raw_values: list[str] | None) -> tuple[FileSearchScope, ...]:
    if not raw_values:
        return (FileSearchScope.PERSONAL, FileSearchScope.TEAM_SAFETY_NAS)
    values: list[FileSearchScope] = []
    for raw_value in raw_values:
        normalized = normalize_nfc(raw_value, field_name="scopes", maximum_length=100)
        for item in normalized.split(","):
            try:
                scope = FileSearchScope(item.strip().upper())
            except ValueError as exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="FILE_SEARCH_SCOPE_INVALID",
                ) from exception
            if scope not in values:
                values.append(scope)
    if not values:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="FILE_SEARCH_SCOPE_INVALID")
    return tuple(values)


@router.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    context: FileSearchContextDep,
) -> dict:
    require_search(context)
    retry_after = _search_rate_limiter.retry_after(context.actor_user_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FILE_SEARCH_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        included_tokens, excluded_tokens = normalize_query_tokens(
            body.q,
            allow_empty=body.folder is not None,
        )
        normalized_scopes = _parse_scopes(body.scopes)
        if body.folder is not None and body.folder.scope not in normalized_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="FILE_SEARCH_FOLDER_SCOPE_INVALID",
            )
    except HTTPException:
        raise
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FILE_SEARCH_QUERY_INVALID",
        ) from exception
    try:
        items, total_count, duration_ms = context.database.search(
            context.actor_user_id,
            normalized_scopes,
            included_tokens,
            excluded_tokens,
            tuple(body.extensions or ()),
            body.folder,
            body.limit,
            body.sort,
            body.offset,
        )
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception
    logger.info(
        "file_search actor=%s scopes=%s token_count=%s include_count=%s "
        "exclude_count=%s extension_count=%s folder_selected=%s "
        "result_count=%s total_count=%s duration_ms=%s",
        context.actor_user_id,
        ",".join(scope.value for scope in normalized_scopes),
        len(included_tokens) + len(excluded_tokens),
        len(included_tokens),
        len(excluded_tokens),
        len(body.extensions or ()),
        body.folder is not None,
        len(items),
        total_count,
        duration_ms,
    )
    return {"items": items, "count": len(items), "total_count": total_count}


@router.post("/folders")
def folders_endpoint(
    body: FolderRequest,
    context: FileSearchContextDep,
) -> dict:
    require_search(context)
    retry_after = _folder_rate_limiter.retry_after(context.actor_user_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FILE_SEARCH_FOLDER_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        items, duration_ms = context.database.folders(
            context.actor_user_id,
            body,
        )
    except IndexDatabaseContractError as exception:
        _raise_contract_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception
    logger.info(
        "file_search_folders actor=%s scope=%s result_count=%s duration_ms=%s",
        context.actor_user_id,
        body.scope.value,
        len(items),
        duration_ms,
    )
    return {"items": items}


@router.get("/state")
def state_endpoint(context: FileSearchContextDep) -> dict:
    require_search(context)
    retry_after = _state_rate_limiter.retry_after(context.actor_user_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="FILE_SEARCH_STATE_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    return {"sources": context.database.state(context.actor_user_id)}


@important_files_router.get("/capabilities")
def important_file_capabilities(
    context: FileSearchContextDep,
    surface: Literal["PC", "MOBILE"] = Query(...),
) -> dict:
    _enforce_general_rate_limit(context.actor_user_id)
    _require_important_file_access(context)
    return {
        "contract_version": IMPORTANT_FILES_CONTRACT_VERSION,
        "surface": surface,
        "can_read": True,
        # www.besma.co.kr is deliberately read-only on both responsive
        # surfaces.  Upload capability is advertised only by the desktop
        # file-search capabilities endpoint.
        "can_upload": False,
        "can_retire": False,
        "max_file_bytes": min(
            settings.file_search_important_file_max_bytes,
            5 * 1024 * 1024,
        ),
        "retention_days": IMPORTANT_FILE_RETENTION_DAYS,
    }


@important_files_router.get("")
def list_important_files_endpoint(
    context: FileSearchContextDep,
    surface: Literal["PC", "MOBILE"] = Query(...),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict:
    del surface  # Contract marker; the website is read-only on both surfaces.
    retry_after = _important_list_rate_limiter.retry_after(context.actor_user_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="IMPORTANT_FILE_LIST_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    _require_important_file_access(context)
    try:
        items = list_visible_important_files(
            context.database,
            actor_user_id=context.actor_user_id,
            limit=limit,
        )
        return {"items": items, "count": len(items)}
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception


@important_files_router.post("", status_code=status.HTTP_201_CREATED)
async def upload_important_file_endpoint(
    context: FileSearchContextDep,
    surface: Annotated[Literal["PC"], Form(...)],
    scope: Annotated[str, Form(...)],
    logical_root_id: Annotated[str, Form(...)],
    installation_id: Annotated[str, Form(...)],
    relative_path: Annotated[str, Form(...)],
    expected_sha256: Annotated[str, Form(...)],
    explicit_confirmation: Annotated[str, Form(...)],
    file: Annotated[UploadFile, File(...)],
) -> dict:
    del surface  # Pydantic enforces exact PC; MOBILE is not a valid upload surface.
    _require_important_file_access(context, upload=True)
    retry_after = _important_upload_rate_limiter.retry_after(context.actor_user_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="IMPORTANT_FILE_UPLOAD_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    if explicit_confirmation != IMPORTANT_FILE_EXPLICIT_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMPORTANT_FILE_EXPLICIT_CONFIRMATION_REQUIRED",
        )
    if not _SHA256_RE.fullmatch(expected_sha256):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMPORTANT_FILE_SHA256_INVALID",
        )
    try:
        selector = FolderRequest.model_validate(
            {
                "scope": scope,
                "logical_root_id": logical_root_id,
                "installation_id": installation_id,
                "relative_path": relative_path,
            }
        )
        if not selector.relative_path:
            raise ValueError("important file requires an exact file path")
    except ValueError as exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMPORTANT_FILE_SELECTOR_INVALID",
        ) from exception

    staged = None
    try:
        staged = await stage_explicit_upload(
            file,
            storage_root=settings.file_search_important_files_root,
            maximum_bytes=min(
                settings.file_search_important_file_max_bytes,
                5 * 1024 * 1024,
            ),
            expected_sha256=expected_sha256,
        )
        validate_upload_selection(
            context.database,
            actor_user_id=context.actor_user_id,
            selector=selector,
            staged=staged,
        )
        return publish_explicit_important_file(
            context.database,
            storage_root=settings.file_search_important_files_root,
            actor_user_id=context.actor_user_id,
            selector=selector,
            staged=staged,
            max_active_files_per_owner=(
                settings.file_search_important_active_files_per_owner
            ),
            max_active_bytes_per_owner=(
                settings.file_search_important_active_bytes_per_owner
            ),
            max_total_active_bytes=(
                settings.file_search_important_total_active_bytes
            ),
            max_total_stored_bytes=(
                settings.file_search_important_total_stored_bytes
            ),
        )
    except ImportantFileContractError as exception:
        _raise_important_file_error(exception)
    except (OSError, sqlite3.Error) as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IMPORTANT_FILE_STORAGE_UNAVAILABLE",
        ) from exception
    finally:
        discard_staged_upload(staged)


@important_files_router.get("/{file_id}/content")
def download_important_file_endpoint(
    context: FileSearchContextDep,
    file_id: str = Path(min_length=36, max_length=36),
) -> FileResponse:
    retry_after = _important_download_rate_limiter.retry_after(
        context.actor_user_id
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="IMPORTANT_FILE_DOWNLOAD_RATE_LIMITED",
            headers={"Retry-After": str(retry_after)},
        )
    _require_important_file_access(context)
    try:
        resolved = resolve_important_file_for_download(
            context.database,
            storage_root=settings.file_search_important_files_root,
            actor_user_id=context.actor_user_id,
            file_id=file_id,
        )
    except ImportantFileContractError as exception:
        _raise_important_file_error(exception)
    except (OSError, sqlite3.Error) as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="IMPORTANT_FILE_STORAGE_UNAVAILABLE",
        ) from exception
    response = FileResponse(
        resolved.path,
        media_type=resolved.media_type,
        filename=resolved.file_name,
    )
    response.headers["Content-Disposition"] = (
        f"{resolved.disposition}; filename*=UTF-8''{quote(resolved.file_name)}"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@important_files_router.delete("/{file_id}")
def retire_important_file_endpoint(
    context: FileSearchContextDep,
    file_id: str = Path(min_length=36, max_length=36),
    surface: Literal["PC"] = Query(...),
    explicit_confirmation: str = Query(...),
) -> dict:
    del surface
    _enforce_general_rate_limit(context.actor_user_id)
    _require_important_file_access(context, upload=True)
    if explicit_confirmation != IMPORTANT_FILE_RETIRE_CONFIRMATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IMPORTANT_FILE_RETIRE_CONFIRMATION_REQUIRED",
        )
    try:
        return retire_important_file(
            context.database,
            actor_user_id=context.actor_user_id,
            file_id=file_id,
        )
    except ImportantFileContractError as exception:
        _raise_important_file_error(exception)
    except sqlite3.Error as exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FILE_SEARCH_DATABASE_UNAVAILABLE",
        ) from exception
