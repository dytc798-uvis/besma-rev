from __future__ import annotations

from datetime import datetime
from hashlib import md5
from pathlib import Path
import mimetypes
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import (
    HQ_SAFE_WORKSPACE_ROLES,
    CurrentUserDep,
    assert_document_file_access,
)
from app.modules.document_generation.models import DocumentInstance
from app.modules.sites.models import Site  # noqa: F401 - registers ORM relationship target
from app.modules.documents.storage_paths import (
    field_file_display_name,
    instance_id_from_storage_relative_path,
    is_field_derivative_filename,
    resolve_existing_storage_path,
)
from app.modules.document_explorer.search_index import (
    refresh_document_index,
    score_document,
)
from app.schemas.document_explorer import DocumentExplorerFileItem, DocumentExplorerListResponse

router = APIRouter(prefix="/document-explorer", tags=["document-explorer"])

DOCUMENT_EXPLORER_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
    Role.ACCIDENT_ADMIN.value,
    Role.SITE.value,
    Role.SITE_FUNCTIONAL_EVAL.value,
    Role.HQ_OTHER.value,
}

_HQ_DEMO_READONLY_LOGIN_IDS = frozenset({"hq01", "hq02", "hq03", "hq04", "hq05"})

DOCUMENT_EXPLORER_BASE_UPLOAD_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
}

_DISALLOWED_EXPLORER_SUFFIXES = frozenset(
    {
        ".exe",
        ".dll",
        ".scr",
        ".bat",
        ".cmd",
        ".com",
        ".msi",
        ".pif",
        ".vbs",
        ".wsf",
        ".ps1",
    }
)

BASE_TEMPLATE_EXTENSIONS = {
    ".pdf",
    ".hwp",
    ".hwpx",
    ".xlsx",
    ".xls",
    ".xltx",
    ".xlt",
    ".pptx",
    ".ppt",
    ".docx",
    ".doc",
    ".txt",
    ".zip",
}

SAMSUNG_TEMPLATE_PREFIX = "삼성관련 양식/"
GENERAL_TEMPLATE_PREFIX = "일반 양식/"
# 구 폴더는 스캔·분류 대상에서 제외(신규 폴더와 중복 노출 방지)
LEGACY_BASE_PREFIXES = (
    "삼성인정제/",
    "현장 안전서류양식/",
)

def _assert_document_explorer_access(current_user) -> None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    if role_value not in DOCUMENT_EXPLORER_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document explorer is allowed for HQ/SITE users only",
        )


def _document_explorer_base_dir() -> Path:
    base_dir = settings.document_explorer_base_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def _document_explorer_field_docs_dir() -> Path:
    field_dir = settings.storage_root / settings.documents_dir_name
    field_dir.mkdir(parents=True, exist_ok=True)
    return field_dir


def _explorer_file_allowed(path: Path) -> bool:
    name = path.name
    if name.startswith("."):
        return False
    if name in {"Thumbs.db", "desktop.ini", "Desktop.ini"}:
        return False
    suf = path.suffix.lower()
    if suf in _DISALLOWED_EXPLORER_SUFFIXES:
        return False
    return True


def _safe_relative_under_root(root: Path, relative_path: str) -> Path:
    normalized = (relative_path or "").replace("\\", "/").strip("/")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    parts = Path(normalized).parts
    if ".." in parts or normalized.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    candidate = (root / normalized).resolve()
    root_resolved = root.resolve()
    if root_resolved not in candidate.parents and candidate != root_resolved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    return candidate


def _assert_document_explorer_base_upload(current_user) -> None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    if role_value not in DOCUMENT_EXPLORER_BASE_UPLOAD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Document explorer base upload is allowed for HQ safety admins only",
        )
    login_id = (getattr(current_user, "login_id", None) or "").strip().lower()
    if role_value == Role.HQ_SAFE.value and login_id in _HQ_DEMO_READONLY_LOGIN_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HQ demo accounts are read-only")


def _allowed_extensions_for_source(source: str) -> set[str] | None:
    if source == "base":
        return BASE_TEMPLATE_EXTENSIONS
    return None


def _is_legacy_base_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    lower = normalized.lower()
    return any(lower.startswith(prefix.lower()) for prefix in LEGACY_BASE_PREFIXES)


def _explorer_item_name(path: Path, category: str) -> str:
    if category == "field":
        return field_file_display_name(path.name)
    return path.name


def _infer_category(relative_path: str, source: str) -> str | None:
    if source == "field":
        return "field"
    normalized = relative_path.replace("\\", "/")
    lower = normalized.lower()
    if lower.startswith(SAMSUNG_TEMPLATE_PREFIX.lower()):
        return "template"
    if lower.startswith(GENERAL_TEMPLATE_PREFIX.lower()):
        return "general"
    return None


def _scan_document_file_entries() -> list[tuple[DocumentExplorerFileItem, Path]]:
    entries: list[tuple[DocumentExplorerFileItem, Path]] = []
    scan_sources: dict[str, Path] = {
        "base": _document_explorer_base_dir(),
        "field": _document_explorer_field_docs_dir(),
    }

    for source, root_dir in scan_sources.items():
        allowed_ext = _allowed_extensions_for_source(source)
        for path in sorted(root_dir.rglob("*")):
            if not path.is_file():
                continue
            if not _explorer_file_allowed(path):
                continue
            if source == "field" and is_field_derivative_filename(path.name):
                continue
            ext = path.suffix.lower()
            if allowed_ext is not None and ext not in allowed_ext:
                continue
            root_rel = path.relative_to(root_dir).as_posix()
            if source == "base" and _is_legacy_base_path(root_rel):
                continue
            category = _infer_category(root_rel, source)
            if category is None:
                continue
            rel = f"{source}/{root_rel}" if root_rel else source
            stat = path.stat()
            entries.append(
                (
                    DocumentExplorerFileItem(
                    id=md5(rel.encode("utf-8")).hexdigest(),
                    name=_explorer_item_name(path, category),
                    relative_path=rel,
                    modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    size_bytes=stat.st_size,
                    extension=ext,
                    category=category,
                    ),
                    path,
                )
            )

    entries.sort(
        key=lambda entry: (entry[0].modified_at, entry[0].relative_path),
        reverse=True,
    )
    return entries


def _scan_document_files() -> list[DocumentExplorerFileItem]:
    return [item for item, _path in _scan_document_file_entries()]


def _entries_for_user(entries, db, current_user):
    if current_user.role in HQ_SAFE_WORKSPACE_ROLES:
        return entries
    allowed = []
    for item, path in entries:
        if item.relative_path.startswith("base/"):
            allowed.append((item, path))
            continue
        instance_id = instance_id_from_storage_relative_path(item.relative_path)
        if instance_id is None:
            continue
        instance = db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        if (
            instance is not None
            and current_user.role in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}
            and current_user.site_id == instance.site_id
        ):
            allowed.append((item, path))
    return allowed


def _matches_query(item: DocumentExplorerFileItem, q: str) -> bool:
    if not q:
        return True
    needle = q.strip().lower()
    if not needle:
        return True
    return needle in item.name.lower() or needle in item.relative_path.lower()


@router.get("/list", response_model=DocumentExplorerListResponse)
def list_document_explorer_files(db: DbDep, current_user: CurrentUserDep):
    _assert_document_explorer_access(current_user)
    entries = _entries_for_user(_scan_document_file_entries(), db, current_user)
    return DocumentExplorerListResponse(items=[item for item, _path in entries])


@router.get("/search", response_model=DocumentExplorerListResponse)
def search_document_explorer_files(
    db: DbDep,
    current_user: CurrentUserDep,
    q: str = Query(default=""),
):
    _assert_document_explorer_access(current_user)
    query = (q or "").strip()
    entries = _entries_for_user(_scan_document_file_entries(), db, current_user)
    if not query:
        return DocumentExplorerListResponse(items=[item for item, _path in entries])
    index = refresh_document_index(
        (item.relative_path, path) for item, path in entries
    )
    indexed_items = index["items"]
    items: list[DocumentExplorerFileItem] = []
    for item, _path in entries:
        indexed = indexed_items.get(item.relative_path, {})
        relevance, snippet, match_source = score_document(
            query=query,
            name=item.name,
            relative_path=item.relative_path,
            indexed_text=indexed.get("text") or "",
        )
        if relevance <= 0:
            continue
        items.append(
            item.model_copy(
                update={
                    "relevance": relevance,
                    "snippet": snippet,
                    "match_source": match_source,
                    "index_status": indexed.get("status"),
                }
            )
        )
    items.sort(
        key=lambda item: (item.relevance, item.modified_at, item.relative_path),
        reverse=True,
    )
    return DocumentExplorerListResponse(items=items)


@router.post("/upload")
async def upload_document_explorer_base_file(
    current_user: CurrentUserDep,
    relative_path: Annotated[str, Form(...)],
    file: UploadFile = File(...),
):
    _assert_document_explorer_access(current_user)
    _assert_document_explorer_base_upload(current_user)

    rel = (relative_path or "").replace("\\", "/").strip()
    if rel.startswith("base/"):
        rel = rel[len("base/") :]
    dest = _safe_relative_under_root(_document_explorer_base_dir(), rel)
    if not _explorer_file_allowed(dest):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed")
    allowed_ext = _allowed_extensions_for_source("base")
    if dest.suffix.lower() not in allowed_ext:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed for base templates")

    content = await file.read()
    max_bytes = int(settings.document_upload_max_bytes)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds document_upload_max_bytes ({max_bytes})",
        )

    if _is_legacy_base_path(rel):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Legacy template folders are read-only")
    category = _infer_category(rel, "base")
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload path must be under 삼성관련 양식/ or 일반 양식/",
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    stat = dest.stat()
    ext = dest.suffix.lower()
    root_rel = dest.relative_to(_document_explorer_base_dir()).as_posix()
    rel_api = f"base/{root_rel}"
    return DocumentExplorerFileItem(
        id=md5(rel_api.encode("utf-8")).hexdigest(),
        name=dest.name,
        relative_path=rel_api,
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        size_bytes=stat.st_size,
        extension=ext,
        category=category,
    )


@router.get("/file")
def open_or_download_document_explorer_file(
    db: DbDep,
    current_user: CurrentUserDep,
    relative_path: str = Query(...),
    disposition: str = Query("attachment"),
):
    _assert_document_explorer_access(current_user)
    normalized = (relative_path or "").replace("\\", "/").strip("/")
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    source, sep, remainder = normalized.partition("/")
    if not sep or not remainder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="relative_path must start with base/ or field/",
        )
    source_dirs: dict[str, Path] = {
        "base": _document_explorer_base_dir().resolve(),
        "field": _document_explorer_field_docs_dir().resolve(),
    }
    root_dir = source_dirs.get(source)
    if root_dir is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown document source")
    candidate = (root_dir / remainder).resolve()
    if root_dir not in candidate.parents and candidate != root_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path")
    if source == "field":
        storage_rel = f"{settings.documents_dir_name}/{remainder.replace('\\', '/')}"
        instance_id = instance_id_from_storage_relative_path(storage_rel)
        if current_user.role not in HQ_SAFE_WORKSPACE_ROLES:
            instance = (
                db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
                if instance_id is not None
                else None
            )
            if instance is None:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
            assert_document_file_access(current_user, site_id=instance.site_id)
        resolved = resolve_existing_storage_path(
            settings.storage_root,
            storage_rel,
            instance_id=instance_id,
            file_name=candidate.name,
        )
        if resolved is not None:
            candidate = resolved.resolve()
    else:
        if current_user.role not in HQ_SAFE_WORKSPACE_ROLES and current_user.role not in {
            Role.SITE,
            Role.SITE_FUNCTIONAL_EVAL,
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if not _explorer_file_allowed(candidate):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File type not allowed")
    allowed_ext = _allowed_extensions_for_source(source)
    if allowed_ext is not None and candidate.suffix.lower() not in allowed_ext:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File type not allowed")
    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")
    media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
    filename = field_file_display_name(candidate.name) if source == "field" else candidate.name
    response = FileResponse(path=candidate, media_type=media_type, filename=filename)
    response.headers["Content-Disposition"] = f"{resolved_disposition}; filename*=UTF-8''{quote(filename)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
