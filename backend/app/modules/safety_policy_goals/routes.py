from pathlib import Path
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, status, UploadFile
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.safety_policy_goals.models import SafetyPolicyGoalDocument
from app.modules.sites.models import Site

router = APIRouter(prefix="/safety-policy-goals", tags=["safety-policy-goals"])


def _ensure_documents_dir() -> Path:
    d = settings.storage_root / settings.documents_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _normalize_scope(value: str) -> str:
    v = (value or "").strip().upper()
    if v not in {"HQ", "SITE"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope must be HQ or SITE")
    return v


def _normalize_kind(value: str) -> str:
    v = (value or "").strip().upper()
    if v not in {"POLICY", "TARGET"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kind must be POLICY or TARGET")
    return v


@router.get("/view")
def get_policy_goal_view(
    db: DbDep,
    current_user: CurrentUserDep,
    scope: str = Query(...),
    site_id: int | None = Query(None),
):
    normalized_scope = _normalize_scope(scope)
    resolved_site_id = site_id
    if normalized_scope == "SITE":
        if current_user.role == Role.SITE:
            resolved_site_id = current_user.site_id
        if not resolved_site_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required for SITE scope")

    def _latest(kind: str):
        q = db.query(SafetyPolicyGoalDocument).filter(
            SafetyPolicyGoalDocument.scope == normalized_scope,
            SafetyPolicyGoalDocument.kind == kind,
        )
        if normalized_scope == "SITE":
            q = q.filter(SafetyPolicyGoalDocument.site_id == resolved_site_id)
        else:
            q = q.filter(SafetyPolicyGoalDocument.site_id.is_(None))
        return q.order_by(SafetyPolicyGoalDocument.uploaded_at.desc(), SafetyPolicyGoalDocument.id.desc()).first()

    policy = _latest("POLICY")
    target = _latest("TARGET")

    def _to_payload(row: SafetyPolicyGoalDocument | None):
        if row is None:
            return None
        return {
            "id": row.id,
            "scope": row.scope,
            "kind": row.kind,
            "site_id": row.site_id,
            "title": row.title,
            "file_name": row.file_name,
            "file_size": row.file_size,
            "uploaded_at": row.uploaded_at,
            "file_url": f"/safety-policy-goals/file/{row.id}",
        }

    return {
        "scope": normalized_scope,
        "site_id": resolved_site_id,
        "policy": _to_payload(policy),
        "target": _to_payload(target),
    }


@router.post("/upload")
async def upload_policy_goal_document(
    db: DbDep,
    current_user: CurrentUserDep,
    scope: str = Form(...),
    kind: str = Form(...),
    title: str = Form(...),
    site_id: int | None = Form(None),
    file: UploadFile = File(...),
):
    if current_user.role not in {Role.HQ_SAFE.value, Role.HQ_SAFE_ADMIN.value, Role.SUPER_ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    normalized_scope = _normalize_scope(scope)
    normalized_kind = _normalize_kind(kind)
    clean_title = (title or "").strip()
    if not clean_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title is required")
    target_site_id = site_id
    if normalized_scope == "SITE":
        if not target_site_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required for SITE scope")
        site_exists = db.query(Site.id).filter(Site.id == target_site_id).first()
        if site_exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    else:
        target_site_id = None

    storage_dir = _ensure_documents_dir()
    source_name = file.filename or "upload.bin"
    ext = Path(source_name).suffix or ".bin"
    content = await file.read()
    if len(content) > settings.document_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"파일 크기는 {settings.document_upload_max_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
        )
    filename = f"policy_goal_{normalized_scope}_{normalized_kind}_{int(utc_now().timestamp())}{ext}"
    stored_path = storage_dir / filename
    stored_path.write_bytes(content)

    row = SafetyPolicyGoalDocument(
        scope=normalized_scope,
        kind=normalized_kind,
        site_id=target_site_id,
        title=clean_title,
        file_path=str(stored_path.relative_to(settings.storage_root)),
        file_name=source_name,
        file_size=len(content),
        uploaded_by_user_id=current_user.id,
        uploaded_at=utc_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.get("/file/{document_id}")
def download_policy_goal_file(
    document_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    row = db.query(SafetyPolicyGoalDocument).filter(SafetyPolicyGoalDocument.id == document_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if row.scope == "SITE" and current_user.role == Role.SITE and current_user.site_id != row.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    file_path = settings.storage_root / row.file_path
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(path=file_path, media_type=media_type, filename=row.file_name)
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(row.file_name)}"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
