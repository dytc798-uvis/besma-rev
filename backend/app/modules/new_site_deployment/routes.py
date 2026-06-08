from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep
from app.modules.new_site_deployment import service

router = APIRouter(prefix="/new-site-deployment", tags=["new-site-deployment"])


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    if code == "NOT_FOUND":
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=code)
    if code in {"FORBIDDEN", "SITE_ONLY", "SAFETY_CHECK_FORBIDDEN"}:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=code)
    if code in {"SITE_NAME_REQUIRED", "INVALID_ITEM", "INVALID_DOC", "INVALID_KIND"}:
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)


@router.get("/menu-status")
def menu_status(db: DbDep, current_user: CurrentUserDep):
    return service.menu_status(db, current_user)


@router.get("/deployments")
def list_deployments(db: DbDep, current_user: CurrentUserDep):
    return {"items": service.list_deployments(db, current_user)}


@router.get("/my-site")
def my_site_deployment(db: DbDep, current_user: CurrentUserDep):
    item = service.get_site_deployment(db, current_user)
    return {"item": item}


@router.get("/deployments/{deployment_id}")
def get_deployment(deployment_id: int, db: DbDep, current_user: CurrentUserDep):
    try:
        return service.get_deployment(db, current_user, deployment_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/deployments")
def create_deployment(payload: dict, db: DbDep, current_user: CurrentUserDep):
    try:
        return service.create_deployment(db, current_user, payload)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.put("/deployments/{deployment_id}")
def update_deployment_budget(deployment_id: int, payload: dict, db: DbDep, current_user: CurrentUserDep):
    try:
        return service.update_deployment_budget(db, current_user, deployment_id, payload)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.put("/deployments/{deployment_id}/procurement")
def update_deployment_procurement(deployment_id: int, payload: dict, db: DbDep, current_user: CurrentUserDep):
    try:
        return service.update_deployment_procurement(db, current_user, deployment_id, payload)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/deployments/{deployment_id}/photos/{item_key}")
async def upload_photo(
    deployment_id: int,
    item_key: str,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "photo.jpg").suffix or ".jpg"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
        return service.upload_photo(
            db,
            current_user,
            deployment_id,
            item_key,
            file_path=tmp_path,
            original_filename=file.filename or "photo.jpg",
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    finally:
        if "tmp_path" in locals() and tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)


@router.post("/deployments/{deployment_id}/documents/{doc_type}")
async def upload_document(
    deployment_id: int,
    doc_type: str,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "doc.pdf").suffix or ".pdf"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)
        return service.upload_document(
            db,
            current_user,
            deployment_id,
            doc_type,
            file_path=tmp_path,
            original_filename=file.filename or "document.pdf",
        )
    except ValueError as exc:
        raise _http_error(exc) from exc
    finally:
        if "tmp_path" in locals() and tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)


@router.get("/files/{kind}/{file_id}")
def download_file(kind: str, file_id: int, db: DbDep, current_user: CurrentUserDep):
    del current_user
    try:
        path, filename = service.resolve_stored_file(db, kind=kind, file_id=file_id)
        return FileResponse(path, filename=filename)
    except ValueError as exc:
        raise _http_error(exc) from exc
