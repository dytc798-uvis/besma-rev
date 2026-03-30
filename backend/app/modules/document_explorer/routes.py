from __future__ import annotations

from datetime import datetime
from hashlib import md5
from pathlib import Path

from fastapi import APIRouter, Query

from app.config.settings import settings
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.schemas.document_explorer import DocumentExplorerFileItem, DocumentExplorerListResponse

router = APIRouter(prefix="/document-explorer", tags=["document-explorer"])

DOCUMENT_EXPLORER_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
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


def _infer_category(relative_path: str, extension: str) -> str:
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
    base_dir = _document_explorer_base_dir()
    items: list[DocumentExplorerFileItem] = []

    for path in sorted(base_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base_dir).as_posix()
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
                category=_infer_category(rel, ext),
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

