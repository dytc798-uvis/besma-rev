from __future__ import annotations

from datetime import datetime
from hashlib import md5
from pathlib import Path
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.schemas.document_explorer import DocumentExplorerFileItem, DocumentExplorerListResponse

router = APIRouter(prefix="/document-explorer", tags=["document-explorer"])

DOCUMENT_EXPLORER_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
    Role.ACCIDENT_ADMIN.value,
    Role.SITE.value,
    Role.HQ_OTHER.value,
}


def _assert_document_explorer_access(current_user) -> None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    if role_value not in DOCUMENT_EXPLORER_ALLOWED_ROLES:
        from fastapi import HTTPException, status

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


def _infer_category(relative_path: str, extension: str, source: str) -> str:
    if source == "field":
        return "field"
    value = f"{relative_path} {extension}".lower()
    field_markers = {
        "현장문서",
        "업로드본",
        "제출본",
        "취합본",
        "site-upload",
        "field-doc",
    }
    if any(marker in value for marker in field_markers):
        return "field"
    if "양식" in value or "template" in value or extension in {".xlsx", ".xls", ".xltx", ".xlt", ".dotx", ".ai"}:
        return "template"
    if "법규" in value or "기준" in value or "참고" in value or extension in {".pdf"}:
        return "reference"
    # docs/base는 현재 기본 양식 보관 폴더로 사용하므로, 명시적 현장문서가 아니면 기본값을 양식으로 둔다.
    return "template"


def _scan_document_files() -> list[DocumentExplorerFileItem]:
    items: list[DocumentExplorerFileItem] = []
    scan_sources: dict[str, Path] = {
        "base": _document_explorer_base_dir(),
        "field": _document_explorer_field_docs_dir(),
    }

    for source, root_dir in scan_sources.items():
        for path in sorted(root_dir.rglob("*")):
            if not path.is_file():
                continue
            root_rel = path.relative_to(root_dir).as_posix()
            rel = f"{source}/{root_rel}" if root_rel else source
            stat = path.stat()
            ext = path.suffix.lower()
            if ext != ".pdf":
                continue
            items.append(
                DocumentExplorerFileItem(
                    id=md5(rel.encode("utf-8")).hexdigest(),
                    name=path.name,
                    relative_path=rel,
                    modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    size_bytes=stat.st_size,
                    extension=ext,
                    category=_infer_category(root_rel, ext, source),
                )
            )

    items.sort(key=lambda item: (item.modified_at, item.relative_path), reverse=True)
    return items


def _matches_query(item: DocumentExplorerFileItem, q: str) -> bool:
    if not q:
        return True
    needle = q.strip().lower()
    if not needle:
        return True
    return needle in item.name.lower() or needle in item.relative_path.lower()


@router.get("/list", response_model=DocumentExplorerListResponse)
def list_document_explorer_files(current_user: CurrentUserDep):
    _assert_document_explorer_access(current_user)
    return DocumentExplorerListResponse(items=_scan_document_files())


@router.get("/search", response_model=DocumentExplorerListResponse)
def search_document_explorer_files(
    current_user: CurrentUserDep,
    q: str = Query(default=""),
):
    _assert_document_explorer_access(current_user)
    items = [item for item in _scan_document_files() if _matches_query(item, q)]
    return DocumentExplorerListResponse(items=items)


@router.get("/file")
def open_or_download_document_explorer_file(
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relative_path must start with base/ or field/")
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
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    if candidate.suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Only PDF files are allowed")
    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")
    media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
    filename = candidate.name
    response = FileResponse(path=candidate, media_type=media_type, filename=filename)
    response.headers["Content-Disposition"] = f"{resolved_disposition}; filename*=UTF-8''{quote(filename)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

