from __future__ import annotations

from datetime import datetime
from hashlib import md5, sha256
from pathlib import Path
import mimetypes
import os
import shutil
import tempfile
from threading import Lock
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import HQ_SAFE_WORKSPACE_ROLES, assert_document_file_access
from app.core.government_workspace_access import GovernmentUserDep as CurrentUserDep, can_manage_government
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
from app.modules.document_explorer.government_access import (
    PUBLIC_PREFIX,
    PUBLIC_CANDIDATE_RELATIVE_PATHS,
    configured_file_visible,
    is_government_site,
    public_folder_visible,
    public_file_visible,
    read_visible_folders,
    set_file_visibility,
    set_folder_visibility,
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
GOVERNMENT_PUBLIC_PREFIX = PUBLIC_PREFIX
MASTER_GUIDE_NAME = "★ 안전보건 문서관리 가이드라인(VER.26.03.25).xlsx"
RETIRED_PUBLIC_GUIDE_NAME = "관급공사_현장안전서류_공개안내.xlsx"
_guide_upload_lock = Lock()
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
    if name == RETIRED_PUBLIC_GUIDE_NAME:
        return False
    if name.startswith("~$"):
        return False
    if path.is_symlink():
        return False
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


def _assert_government_settings(current_user) -> None:
    if not can_manage_government(current_user):
        raise HTTPException(403, "Government forms management is not allowed")


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
    if lower.startswith(GOVERNMENT_PUBLIC_PREFIX.lower()):
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


def _matches_query(item: DocumentExplorerFileItem, q: str) -> bool:
    if not q:
        return True
    needle = q.strip().lower()
    if not needle:
        return True
    return needle in item.name.lower() or needle in item.relative_path.lower()


def _visible_entries(db, current_user) -> list[tuple[DocumentExplorerFileItem, Path]]:
    entries = _scan_document_file_entries()
    government = is_government_site(current_user)
    folders = read_visible_folders() if government else set()
    if current_user.role in HQ_SAFE_WORKSPACE_ROLES:
        return entries
    allowed = []
    for item, path in entries:
        if item.relative_path.startswith("base/"):
            if not government or public_file_visible(item.relative_path, folders):
                allowed.append((item, path))
            continue
        instance_id = instance_id_from_storage_relative_path(item.relative_path)
        if instance_id is None:
            continue
        instance = db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        if (instance is not None and current_user.role in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}
                and current_user.site_id == instance.site_id):
            allowed.append((item, path))
    return allowed


class GovernmentFolderVisibility(BaseModel):
    folder: str
    visible: bool


class GovernmentFileVisibility(BaseModel):
    relative_path: str
    visible: bool


@router.get("/government-folders")
def list_government_folders(current_user: CurrentUserDep):
    _assert_government_settings(current_user)
    root = _document_explorer_base_dir() / GOVERNMENT_PUBLIC_PREFIX.rstrip("/")
    visible = read_visible_folders()
    if not root.is_dir():
        return {"folders": []}
    return {"folders": [
        {"folder": folder.relative_to(_document_explorer_base_dir()).as_posix(),
         "visible": folder.relative_to(_document_explorer_base_dir()).as_posix() in visible}
        for folder in sorted(root.rglob("*")) if folder.is_dir() and not folder.is_symlink()
    ]}


@router.get("/government-document-catalog")
def government_document_catalog(current_user: CurrentUserDep):
    """Report every standard form and whether an approved public copy is actually visible."""
    _assert_government_settings(current_user)
    entries = _scan_document_file_entries()
    internal_prefix = "base/일반 양식/"
    public_prefix = "base/" + GOVERNMENT_PUBLIC_PREFIX
    originals = {
        item.relative_path[len(internal_prefix):]: item
        for item, _ in entries if item.relative_path.startswith(internal_prefix)
    }
    copies = {
        item.relative_path[len(public_prefix):]: item
        for item, _ in entries if item.relative_path.startswith(public_prefix)
    }
    visible_folders = read_visible_folders()
    rows = []
    for relative in sorted(originals.keys() | copies.keys()):
        copy = copies.get(relative)
        public_path = copy.relative_path if copy else ""
        folder_visible = public_folder_visible(public_prefix + relative, visible_folders)
        visible = bool(copy and public_file_visible(public_path, visible_folders))
        rows.append({
            "relative_path": relative,
            "folder": relative.rpartition("/")[0] or "(최상위)",
            "name": relative.rpartition("/")[2],
            "visibility": "PUBLIC" if visible else "PRIVATE",
            "recommended_visibility": "PUBLIC_CANDIDATE" if relative in PUBLIC_CANDIDATE_RELATIVE_PATHS else "PRIVATE",
            "public_copy_prepared": copy is not None,
            "public_folder_visible": folder_visible,
            "file_enabled": configured_file_visible(relative),
            "has_internal_original": relative in originals,
        })
    return {
        "items": rows,
        "total": len(rows),
        "public": sum(row["visibility"] == "PUBLIC" for row in rows),
        "private": sum(row["visibility"] == "PRIVATE" for row in rows),
        "public_candidates": sum(row["recommended_visibility"] == "PUBLIC_CANDIDATE" for row in rows),
    }


@router.put("/government-folders")
def update_government_folder_visibility(payload: GovernmentFolderVisibility, current_user: CurrentUserDep):
    _assert_government_settings(current_user)
    return {"visible_folders": set_folder_visibility(payload.folder, payload.visible)}


@router.put("/government-files")
def update_government_file_visibility(payload: GovernmentFileVisibility, current_user: CurrentUserDep):
    _assert_government_settings(current_user)
    return {"relative_path": payload.relative_path, "visible": set_file_visibility(payload.relative_path, payload.visible)}


def _master_guide_path() -> Path:
    return _document_explorer_base_dir() / "일반 양식" / MASTER_GUIDE_NAME


@router.get("/master-guide-version")
def master_guide_version(current_user: CurrentUserDep):
    _assert_document_explorer_base_upload(current_user)
    path = _master_guide_path()
    if not path.is_file():
        return {"exists": False, "sha256": None, "size_bytes": 0}
    return {"exists": True, "sha256": sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size}


@router.post("/master-guide-upload")
async def upload_master_guide(
    current_user: CurrentUserDep,
    expected_sha256: Annotated[str, Form(...)],
    file: UploadFile = File(...),
):
    _assert_document_explorer_base_upload(current_user)
    content = await file.read()
    if not content.startswith(b"PK\x03\x04") or len(content) > min(int(settings.document_upload_max_bytes), 10 * 1024 * 1024):
        raise HTTPException(status_code=400, detail="Expected an XLSX guide under 10 MB")
    try:
        with ZipFile(BytesIO(content)) as workbook:
            if "xl/workbook.xml" not in workbook.namelist() or "[Content_Types].xml" not in workbook.namelist():
                raise HTTPException(status_code=400, detail="Invalid XLSX guide")
    except BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid XLSX guide") from exc
    path = _master_guide_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _guide_upload_lock:
        current = path.read_bytes() if path.is_file() else b""
        current_hash = sha256(current).hexdigest() if current else ""
        if expected_sha256 != current_hash:
            raise HTTPException(status_code=409, detail="Guide changed on server; reload its version")
        new_hash = sha256(content).hexdigest()
        if new_hash == current_hash:
            return {"sha256": new_hash, "updated": False}
        if current:
            versions = settings.storage_root / "document-explorer" / "master-guide-versions"
            versions.mkdir(parents=True, exist_ok=True)
            prior = versions / f"{current_hash}.xlsx"
            if not prior.exists():
                shutil.copy2(path, prior)
                if sha256(prior.read_bytes()).hexdigest() != current_hash:
                    prior.unlink(missing_ok=True)
                    raise HTTPException(status_code=500, detail="Could not preserve previous guide")
        fd, temporary = tempfile.mkstemp(prefix=".master-guide-", suffix=".xlsx", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return {"sha256": new_hash, "updated": True}


@router.get("/list", response_model=DocumentExplorerListResponse)
def list_document_explorer_files(db: DbDep, current_user: CurrentUserDep):
    _assert_document_explorer_access(current_user)
    return DocumentExplorerListResponse(items=[item for item, _ in _visible_entries(db, current_user)])


@router.get("/search", response_model=DocumentExplorerListResponse)
def search_document_explorer_files(
    db: DbDep,
    current_user: CurrentUserDep,
    q: str = Query(default=""),
):
    _assert_document_explorer_access(current_user)
    query = (q or "").strip()
    entries = _visible_entries(db, current_user)
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

    rel = (relative_path or "").replace("\\", "/").strip()
    if rel.startswith("base/"):
        rel = rel[len("base/") :]
    if rel.startswith(GOVERNMENT_PUBLIC_PREFIX):
        _assert_government_settings(current_user)
    else:
        _assert_document_explorer_base_upload(current_user)
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
            detail="Upload path must be under 삼성관련 양식/, 일반 양식/, or 관급 공개 양식/",
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    if rel.startswith(GOVERNMENT_PUBLIC_PREFIX):
        with _guide_upload_lock:
            if dest.is_file():
                prior_content = dest.read_bytes()
                prior_hash = sha256(prior_content).hexdigest()
                versions = settings.storage_root / 'document-explorer' / 'public-form-versions'
                versions.mkdir(parents=True, exist_ok=True)
                backup = versions / (prior_hash + dest.suffix)
                if not backup.exists():
                    with backup.open('xb') as stream:
                        stream.write(prior_content)
                if sha256(backup.read_bytes()).hexdigest() != prior_hash:
                    raise HTTPException(500, 'Could not preserve previous public form')
            fd, temporary = tempfile.mkstemp(prefix='.public-form-', dir=dest.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, dest)
            finally:
                Path(temporary).unlink(missing_ok=True)
    else:
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
    if source == "base" and is_government_site(current_user) and not public_file_visible(normalized):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
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
    if source == "base" and is_government_site(current_user) and not public_file_visible(f"base/{candidate.relative_to(root_dir).as_posix()}"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if source == "field":
        storage_rel = f"{settings.documents_dir_name}/{remainder.replace('\\', '/')}"
        instance_id = instance_id_from_storage_relative_path(storage_rel)
        if current_user.role not in HQ_SAFE_WORKSPACE_ROLES:
            instance = (
                db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
                if instance_id is not None else None
            )
            if instance is None or current_user.role not in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL} or current_user.site_id is None or current_user.site_id != instance.site_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        if current_user.role not in HQ_SAFE_WORKSPACE_ROLES:
            assert_document_file_access(current_user, site_id=instance.site_id)
        resolved = resolve_existing_storage_path(
            settings.storage_root,
            storage_rel,
            instance_id=instance_id,
            file_name=candidate.name,
        )
        if resolved is not None:
            candidate = resolved.resolve()
    elif current_user.role not in HQ_SAFE_WORKSPACE_ROLES and current_user.role not in {Role.SITE, Role.SITE_FUNCTIONAL_EVAL}:
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
