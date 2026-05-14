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

# document_submissions과 동일 — 데모 HQ 계정은 표준자료 일괄 반입도 막는다(순환 import 회피용 로컬 상수).
_HQ_DEMO_READONLY_LOGIN_IDS = frozenset({"hq01", "hq02", "hq03", "hq04", "hq05"})

DOCUMENT_EXPLORER_BASE_UPLOAD_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
}

# 실행 파일·스크립트류는 목록/다운로드/업로드 모두 제외
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
    """relative_path를 root 아래로만 해석한다. path traversal 차단."""
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
            if not _explorer_file_allowed(path):
                continue
            # field(문서취합 저장소)는 base와 동일하게 _explorer_file_allowed로만 제한한다.
            # PDF만 노출하면 .hwp/.xlsx/.txt 등 실제 업로드 문서가 목록에서 사라진다.
            root_rel = path.relative_to(root_dir).as_posix()
            rel = f"{source}/{root_rel}" if root_rel else source
            stat = path.stat()
            ext = path.suffix.lower()
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


@router.post("/upload")
async def upload_document_explorer_base_file(
    current_user: CurrentUserDep,
    relative_path: Annotated[str, Form(...)],
    file: UploadFile = File(...),
):
    """
    POST /document-explorer/upload
    - `docs/base`(문서 탐색 기준 자료) 아래에만 저장한다.
    - 동일 relative_path로 다시 올리면 파일을 덮어쓴다(overwrite).
    - multipart: relative_path (POSIX 상대경로, base/ 접두사 없음), file
    """
    _assert_document_explorer_access(current_user)
    _assert_document_explorer_base_upload(current_user)

    rel = (relative_path or "").replace("\\", "/").strip()
    if rel.startswith("base/"):
        rel = rel[len("base/") :]
    dest = _safe_relative_under_root(_document_explorer_base_dir(), rel)
    if not _explorer_file_allowed(dest):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed")

    content = await file.read()
    max_bytes = int(settings.document_upload_max_bytes)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds document_upload_max_bytes ({max_bytes})",
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
        category=_infer_category(root_rel, ext, "base"),
    )


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
    if not _explorer_file_allowed(candidate):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File type not allowed")
    resolved_disposition = (disposition or "attachment").strip().lower()
    if resolved_disposition not in {"attachment", "inline"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="disposition must be attachment or inline")
    media_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
    filename = candidate.name
    response = FileResponse(path=candidate, media_type=media_type, filename=filename)
    response.headers["Content-Disposition"] = f"{resolved_disposition}; filename*=UTF-8''{quote(filename)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

