from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.datetime_utils import kst_today, utc_now
from app.core.permissions import CurrentUserDep, Role
from app.core.upload_processing import is_image_upload, process_uploaded_image
from app.modules.document_generation.models import (
    DocumentInstance,
    DocumentInstanceStatus,
    PeriodBasis,
    WorkflowStatus,
)
from app.modules.document_submissions.models import ReviewAction
from app.modules.document_submissions.service import (
    add_review_history,
    get_instance_or_404,
    map_action_to_history_type,
    transition_instance_workflow_status,
)
from app.modules.document_settings.models import DocumentRequirement
from app.modules.documents.ledger_managed import assert_not_ledger_managed_document_type
from app.modules.documents.models import Document, DocumentUploadHistory
from app.modules.documents.models import DocumentStatus
from app.modules.sites.models import Site


router = APIRouter(prefix="/document-submissions", tags=["document-submissions-ops"])
logger = logging.getLogger(__name__)

HQ_DEMO_READONLY_LOGIN_IDS = {"hq01", "hq02", "hq03", "hq04", "hq05"}
DAILY_UPLOAD_DOC_CODES = {
    "DAILY_TBM",
    "DAILY_SAFETY_MEETING_LOG",
    "SUPERVISOR_CHECKLIST",
    "SITE_MANAGER_CHECKLIST",
    "SAFETY_MANAGER_DAILY_LOG",
}
DAILY_UPLOAD_NAME_BY_CODE = {
    "DAILY_TBM": "TBM",
    "DAILY_SAFETY_MEETING_LOG": "일일안전회의일지",
    "SUPERVISOR_CHECKLIST": "관리감독자점검표",
    "SITE_MANAGER_CHECKLIST": "현장소장점검표",
    "SAFETY_MANAGER_DAILY_LOG": "안전담당자업무일지",
}
MERGE_APPEND_DOCUMENT_CODES = frozenset(
    {
        "DAILY_TBM",
        "DAILY_SAFETY_MEETING_LOG",
        "SUPERVISOR_CHECKLIST",
        "SITE_MANAGER_CHECKLIST",
        "SAFETY_MANAGER_DAILY_LOG",
    }
)


def _ensure_documents_dir() -> Path:
    d = settings.storage_root / settings.documents_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_exports_dir() -> Path:
    d = settings.storage_root / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_filename_component(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "미지정"
    # Windows 금지 문자/제어문자 제거
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120] if text else "미지정"


def _resolve_upload_frequency(document_type_code: str, requirement_frequency: str | None) -> str | None:
    code = (document_type_code or "").strip().upper()
    if code in DAILY_UPLOAD_DOC_CODES:
        return "DAILY"
    return requirement_frequency


def _build_saved_filename(
    *,
    document_type_code: str,
    requirement_title: str | None,
    site_code: str | None,
    site_name: str,
    period_start: date,
    extension: str,
) -> str:
    code = (document_type_code or "").strip().upper()
    if code in DAILY_UPLOAD_DOC_CODES:
        base_label = DAILY_UPLOAD_NAME_BY_CODE.get(code, code)
        site_label = _sanitize_filename_component((site_code or "").strip().upper() or site_name)
        return f"{base_label}_{site_label}_{period_start.strftime('%y%m%d')}{extension}"

    item_label = _sanitize_filename_component(requirement_title or code)
    site_label = _sanitize_filename_component(site_name)
    return f"{item_label}_{site_label}{extension}"


def _optimize_uploaded_content(content: bytes, source_name: str, content_type: str | None) -> tuple[bytes, str]:
    ext = Path(source_name or "upload.bin").suffix.lower()

    if ext == ".pdf" and len(content) > settings.document_upload_max_bytes:
        try:
            from pypdf import PdfReader, PdfWriter
        except Exception:
            return content, ext
        try:
            reader = PdfReader(io.BytesIO(content))
            writer = PdfWriter()
            for page in reader.pages:
                try:
                    page.compress_content_streams()
                except Exception:
                    pass
                writer.add_page(page)
            out = io.BytesIO()
            writer.write(out)
            optimized = out.getvalue()
            if optimized and len(optimized) < len(content):
                return optimized, ext
        except Exception:
            return content, ext

    return content, ext


def _merge_pdf_bytes(parts: list[bytes]) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for part in parts:
        reader = PdfReader(io.BytesIO(part))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


async def _collect_pdf_parts_from_uploads(files: list[UploadFile]) -> list[bytes]:
    parts: list[bytes] = []
    for uf in files:
        raw = await uf.read()
        name = uf.filename or "file.bin"
        ctype = uf.content_type
        if is_image_upload(name, ctype):
            try:
                asset = process_uploaded_image(
                    raw,
                    source_name=name,
                    content_type=ctype,
                    generate_pdf=True,
                )
            except RuntimeError as exc:
                raise ValueError(str(exc)) from exc
            if not asset.pdf_bytes:
                raise ValueError("image_pdf_conversion_failed")
            parts.append(asset.pdf_bytes)
            continue
        ext = Path(name).suffix.lower()
        if ext == ".pdf":
            parts.append(raw)
            continue
        raise ValueError(f"unsupported_attachment:{ext or 'unknown'}")
    return parts


def _write_bytes(storage_dir: Path, filename: str, content: bytes) -> str:
    target = storage_dir / filename
    target.write_bytes(content)
    return str(target.relative_to(settings.storage_root))


def _get_or_create_instance_for_upload(
    db,
    *,
    site_id: int,
    document_type_code: str,
    period_start: date,
    period_end: date,
    requirement_id: int | None,
    frequency: str | None,
) -> DocumentInstance:
    base_q = (
        db.query(DocumentInstance)
        .filter(
            DocumentInstance.site_id == site_id,
            DocumentInstance.document_type_code == document_type_code,
            DocumentInstance.period_basis == PeriodBasis.AS_OF_FALLBACK,
            DocumentInstance.period_start == period_start,
            DocumentInstance.period_end == period_end,
        )
    )

    # requirement 기반 업로드는 requirement 슬롯과 정확히 매핑한다.
    if requirement_id is not None:
        inst = base_q.filter(DocumentInstance.selected_requirement_id == requirement_id).first()
        # 과거 데이터 호환: 동일 슬롯인데 requirement 미지정(null) 인스턴스가 있으면 재사용 후 바인딩
        if inst is None:
            inst = base_q.filter(DocumentInstance.selected_requirement_id.is_(None)).first()
            if inst is not None:
                inst.selected_requirement_id = requirement_id
    else:
        inst = base_q.first()

    if inst is not None:
        return inst

    inst = DocumentInstance(
        site_id=site_id,
        document_type_code=document_type_code,
        period_start=period_start,
        period_end=period_end,
        generation_anchor_date=period_start,
        due_date=period_end,
        status=DocumentInstanceStatus.GENERATED,
        status_reason="MANUAL_UPLOAD",
        selected_requirement_id=requirement_id,
        workflow_status=WorkflowStatus.NOT_SUBMITTED,
        period_basis=PeriodBasis.AS_OF_FALLBACK,
        rule_is_required=True,
        cycle_code=(frequency or "ADHOC"),
        rule_generation_rule="MANUAL_UPLOAD",
        rule_generation_value=None,
        rule_due_offset_days=0,
        resolved_from="MANUAL_UPLOAD",
        resolved_cycle_source="manual",
        master_cycle_id=None,
        master_cycle_code="ADHOC",
        override_cycle_id=None,
        override_cycle_code=None,
        error_message=None,
    )
    db.add(inst)
    db.flush()
    return inst


def _resolve_period_bounds(base_date: date, frequency: str | None) -> tuple[date, date]:
    freq = (frequency or "").upper()
    if freq == "WEEKLY":
        start = base_date - timedelta(days=base_date.weekday())
        return start, start + timedelta(days=6)
    if freq == "MONTHLY":
        start = date(base_date.year, base_date.month, 1)
        if base_date.month == 12:
            next_month = date(base_date.year + 1, 1, 1)
        else:
            next_month = date(base_date.year, base_date.month + 1, 1)
        return start, next_month - timedelta(days=1)
    return base_date, base_date


def _record_upload_history(
    db,
    *,
    doc: Document,
    action_type: str,
) -> None:
    db.add(
        DocumentUploadHistory(
            document_id=doc.id,
            instance_id=doc.instance_id,
            version_no=doc.version_no,
            action_type=action_type,
            document_status=doc.current_status,
            file_path=doc.file_path,
            file_name=doc.file_name,
            file_size=doc.file_size,
            uploaded_by_user_id=doc.uploaded_by_user_id,
            uploaded_at=doc.uploaded_at,
            review_note=doc.rejection_reason,
        )
    )


@router.post("/upload")
async def upload_document_for_instance(
    db: DbDep,
    current_user: CurrentUserDep,
    instance_id: Annotated[int | None, Form()] = None,
    site_id: Annotated[int | None, Form()] = None,
    document_type_code: Annotated[str | None, Form()] = None,
    work_date: Annotated[date | None, Form()] = None,
    requirement_id: Annotated[int | None, Form()] = None,
    period_start: Annotated[date | None, Form()] = None,
    period_end: Annotated[date | None, Form()] = None,
    append_only: Annotated[bool, Form()] = False,
    file: Annotated[UploadFile | None, File()] = None,
    append_files: Annotated[list[UploadFile] | None, File()] = None,
):
    """
    POST /document-submissions/upload
    - instance_id + file 업로드
    - Document(1:1) 연결/생성 (documents.instance_id UNIQUE 기준)
    - instance.workflow_status: NOT_SUBMITTED/REJECTED -> SUBMITTED
    - 오케스트레이션 status/status_reason는 건드리지 않는다
    - append_files: TBM·일일안전회의일지·관리감독자점검표 등 허용 코드에서, 본문 PDF 뒤에 이미지/PDF 페이지 병합
    - append_only + instance_id: 이미 제출된 PDF 뒤에 사진만 추가(SUBMITTED/UNDER_REVIEW만, APPROVED 불가)
    """
    # 데모 혼선 방지를 위해 HQ 데모 계정(hq01~hq05)은 업로드를 읽기전용으로 강제한다.
    if current_user.role == Role.HQ_SAFE and current_user.login_id in HQ_DEMO_READONLY_LOGIN_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HQ demo accounts are read-only")

    append_list = list(append_files) if append_files else []

    if append_only:
        if instance_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="append_only requires instance_id")
        if not append_list:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="append_only requires append_files")
        try:
            inst_append = get_instance_or_404(db, instance_id)
        except LookupError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")
        ledger_append = (inst_append.document_type_code or "").strip()
        if ledger_append not in MERGE_APPEND_DOCUMENT_CODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="attachment append is not enabled for this document type",
            )
        assert_not_ledger_managed_document_type(ledger_append)
        if current_user.role == Role.SITE and inst_append.site_id != current_user.site_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
        if inst_append.workflow_status == WorkflowStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="approved documents cannot be modified with photo append",
            )
        if inst_append.workflow_status not in {WorkflowStatus.SUBMITTED, WorkflowStatus.UNDER_REVIEW}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="append is allowed only for SUBMITTED or UNDER_REVIEW documents",
            )
        doc_append = db.query(Document).filter(Document.instance_id == inst_append.id).first()
        if doc_append is None or not doc_append.file_path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document file not found")
        base_path = settings.storage_root / doc_append.file_path
        if not base_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stored file missing")
        base_bytes = base_path.read_bytes()
        if not base_bytes.startswith(b"%PDF"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="base file must be PDF to append photos",
            )
        try:
            extra_append = await _collect_pdf_parts_from_uploads(append_list)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        try:
            merged_append = _merge_pdf_bytes([base_bytes, *extra_append])
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"pdf_merge_failed: {exc}",
            ) from exc
        if len(merged_append) > settings.document_upload_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"파일 크기는 최적화 후 기준 {settings.document_upload_max_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
            )
        _record_upload_history(db, doc=doc_append, action_type="BEFORE_REUPLOAD")
        doc_append.version_no = (doc_append.version_no or 1) + 1
        storage_dir_append = _ensure_documents_dir()
        timestamp_append = int(utc_now().timestamp())
        safe_keep = doc_append.file_name or "document.pdf"
        filename_append = f"instance_{inst_append.id}_{timestamp_append}_{safe_keep}"
        stored_append = storage_dir_append / filename_append
        stored_append.write_bytes(merged_append)
        doc_append.file_path = str(stored_append.relative_to(settings.storage_root))
        doc_append.file_size = len(merged_append)
        doc_append.uploaded_by_user_id = current_user.id
        doc_append.uploaded_at = utc_now()
        wf_keep = inst_append.workflow_status
        add_review_history(
            db,
            inst=inst_append,
            document_id=doc_append.id,
            action_type=ReviewAction.ATTACH_APPEND,
            action_by_user_id=current_user.id,
            comment=None,
            from_workflow_status=wf_keep,
            to_workflow_status=wf_keep,
        )
        db.add(inst_append)
        db.add(doc_append)
        _record_upload_history(db, doc=doc_append, action_type=ReviewAction.ATTACH_APPEND)
        db.commit()
        db.refresh(inst_append)
        db.refresh(doc_append)
        return {
            "instance_id": inst_append.id,
            "orchestration_status": inst_append.status,
            "workflow_status": inst_append.workflow_status,
            "document_id": doc_append.id,
            "file_path": doc_append.file_path,
            "original_file_path": doc_append.original_file_path,
            "optimized_file_path": doc_append.optimized_file_path,
        }

    if file is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="file is required")

    if instance_id is not None:
        try:
            inst = get_instance_or_404(db, instance_id)
        except LookupError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")
    else:
        requirement: DocumentRequirement | None = None
        if requirement_id is not None:
            requirement = db.query(DocumentRequirement).filter(DocumentRequirement.id == requirement_id).first()
            if requirement is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
            if site_id is None:
                site_id = requirement.site_id
            if not document_type_code:
                document_type_code = requirement.code
            if work_date is None:
                work_date = kst_today()
        if site_id is None or not document_type_code or work_date is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="instance_id or (site_id, document_type_code, work_date) is required",
            )
        if requirement is not None and requirement.site_id not in {None, site_id}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement/site mismatch")
        if period_start is None or period_end is None:
            if requirement is not None:
                effective_frequency = _resolve_upload_frequency(document_type_code, requirement.frequency)
                period_start, period_end = _resolve_period_bounds(work_date, effective_frequency)
            else:
                period_start, period_end = work_date, work_date
        effective_frequency = _resolve_upload_frequency(
            document_type_code,
            requirement.frequency if requirement is not None else None,
        )
        inst = _get_or_create_instance_for_upload(
            db,
            site_id=site_id,
            document_type_code=document_type_code.strip(),
            period_start=period_start,
            period_end=period_end,
            requirement_id=requirement_id,
            frequency=effective_frequency,
        )

    # SITE 사용자는 자기 site만
    if current_user.role == Role.SITE and inst.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    ledger_code = (getattr(inst, "document_type_code", None) or document_type_code or "").strip()
    assert_not_ledger_managed_document_type(ledger_code)
    if requirement_id is not None and inst.selected_requirement_id is None:
        inst.selected_requirement_id = requirement_id

    doc = db.query(Document).filter(Document.instance_id == inst.id).first()
    if doc is None:
        doc = Document(
            document_no=f"INST-{inst.id}-{int(utc_now().timestamp())}",
            title=f"[UPLOAD] {inst.document_type_code} {inst.period_start.isoformat()}",
            document_type=inst.document_type_code,
            site_id=inst.site_id,
            submitter_user_id=current_user.id,
            current_status="DRAFT",
            description="DocumentInstance 제출 파일",
            source_type="MANUAL",
            instance_id=inst.id,
            period_start=inst.period_start,
            period_end=inst.period_end,
            due_date=inst.due_date,
        )
        db.add(doc)
        db.flush()
    else:
        _record_upload_history(db, doc=doc, action_type="BEFORE_REUPLOAD")
        doc.version_no = (doc.version_no or 1) + 1
        doc.period_start = inst.period_start
        doc.period_end = inst.period_end
        doc.due_date = inst.due_date

    storage_dir = _ensure_documents_dir()
    source_name = file.filename or "upload.bin"
    content = await file.read()
    timestamp = int(utc_now().timestamp())
    primary_content, primary_ext = _optimize_uploaded_content(content, source_name, file.content_type)
    original_file_path: str | None = None
    optimized_file_path: str | None = None

    if is_image_upload(source_name, file.content_type):
        try:
            image_asset = process_uploaded_image(
                content,
                source_name=source_name,
                content_type=file.content_type,
                generate_pdf=True,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        primary_content = image_asset.pdf_bytes or primary_content
        primary_ext = ".pdf"
        stem = f"instance_{inst.id}_{timestamp}_{Path(source_name).stem}"
        original_file_path = _write_bytes(
            storage_dir,
            f"{stem}__original{image_asset.original_ext}",
            image_asset.original_bytes,
        )
        optimized_file_path = _write_bytes(
            storage_dir,
            f"{stem}__optimized{image_asset.optimized_ext}",
            image_asset.optimized_bytes,
        )

    ledger_merge = (inst.document_type_code or document_type_code or "").strip()
    if append_list and ledger_merge not in MERGE_APPEND_DOCUMENT_CODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="append_files are only allowed for daily merge-enabled document types",
        )
    if append_list and ledger_merge in MERGE_APPEND_DOCUMENT_CODES:
        if primary_ext != ".pdf":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="merging attachments requires the main file to be PDF",
            )
        try:
            extra_merge = await _collect_pdf_parts_from_uploads(append_list)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        try:
            primary_content = _merge_pdf_bytes([primary_content, *extra_merge])
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"pdf_merge_failed: {exc}",
            ) from exc

    if len(primary_content) > settings.document_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"파일 크기는 최적화 후 기준 {settings.document_upload_max_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
        )
    requirement_title = (
        db.query(DocumentRequirement.title)
        .filter(DocumentRequirement.id == inst.selected_requirement_id)
        .scalar()
        if inst.selected_requirement_id
        else None
    )
    site_row = db.query(Site.site_code, Site.site_name).filter(Site.id == inst.site_id).first()
    site_code = site_row[0] if site_row else None
    site_name = site_row[1] if site_row and site_row[1] else f"site_{inst.site_id}"
    safe_name = _build_saved_filename(
        document_type_code=inst.document_type_code or doc.document_type,
        requirement_title=requirement_title or doc.title,
        site_code=site_code,
        site_name=site_name,
        period_start=inst.period_start,
        extension=primary_ext,
    )
    filename = f"instance_{inst.id}_{timestamp}_{safe_name}"
    stored_path = storage_dir / filename
    stored_path.write_bytes(primary_content)

    doc.file_path = str(stored_path.relative_to(settings.storage_root))
    doc.original_file_path = original_file_path
    doc.optimized_file_path = optimized_file_path
    doc.file_name = safe_name
    doc.file_size = len(primary_content)
    doc.uploaded_by_user_id = current_user.id
    doc.uploaded_at = utc_now()

    previous_doc_status = doc.current_status
    # 운영 데이터에서 문서는 REJECTED인데 인스턴스 workflow가 UNDER_REVIEW로 남는 경우가 있어
    # 수정 업로드가 409로 막히는 문제가 발생한다. 이 경우 workflow를 REJECTED로 정렬한 뒤 업로드 전이를 허용한다.
    if previous_doc_status == DocumentStatus.REJECTED and inst.workflow_status == WorkflowStatus.UNDER_REVIEW:
        logger.warning(
            "workflow mismatch repair before upload: instance_id=%s document_id=%s workflow=%s doc_status=%s",
            inst.id,
            doc.id,
            inst.workflow_status,
            previous_doc_status,
        )
        inst.workflow_status = WorkflowStatus.REJECTED

    doc.current_status = DocumentStatus.SUBMITTED
    doc.rejection_reason = None

    # workflow_status 전이
    try:
        before = inst.workflow_status
        transition_instance_workflow_status(inst, action="upload")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    add_review_history(
        db,
        inst=inst,
        document_id=doc.id,
        action_type=map_action_to_history_type("upload"),
        action_by_user_id=current_user.id,
        comment=None,
        from_workflow_status=before,
        to_workflow_status=inst.workflow_status,
    )

    db.add(inst)
    db.add(doc)
    _record_upload_history(db, doc=doc, action_type="UPLOAD")
    db.commit()
    db.refresh(inst)
    db.refresh(doc)

    logger.info(
        "document upload committed: instance_id=%s selected_requirement_id=%s site_id=%s document_id=%s status=%s workflow_status=%s",
        inst.id,
        inst.selected_requirement_id,
        inst.site_id,
        doc.id,
        doc.current_status,
        inst.workflow_status,
    )

    return {
        "instance_id": inst.id,
        "orchestration_status": inst.status,
        "workflow_status": inst.workflow_status,
        "document_id": doc.id,
        "file_path": doc.file_path,
        "original_file_path": doc.original_file_path,
        "optimized_file_path": doc.optimized_file_path,
    }


@router.post("/replace")
async def replace_uploaded_document_file(
    db: DbDep,
    current_user: CurrentUserDep,
    instance_id: Annotated[int, Form(...)],
    file: Annotated[UploadFile, File(...)],
):
    """
    POST /document-submissions/replace
    - 기존 제출건(DocumentInstance + Document)의 파일을 같은 문서에서 교체한다.
    - Document/Instance id는 유지하고 version_no + 이력만 증가한다.
    - APPROVED는 수정 불가, SITE는 자기 site만 허용.
    """
    if current_user.role == Role.HQ_SAFE and current_user.login_id in HQ_DEMO_READONLY_LOGIN_IDS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HQ demo accounts are read-only")

    try:
        inst = get_instance_or_404(db, instance_id)
    except LookupError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instance not found")

    if current_user.role == Role.SITE and inst.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    ledger_code = (inst.document_type_code or "").strip()
    assert_not_ledger_managed_document_type(ledger_code)

    if inst.workflow_status == WorkflowStatus.APPROVED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="approved documents cannot be replaced")
    if inst.workflow_status not in {WorkflowStatus.SUBMITTED, WorkflowStatus.UNDER_REVIEW, WorkflowStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="replace is allowed only for SUBMITTED, UNDER_REVIEW, or REJECTED documents",
        )

    doc = db.query(Document).filter(Document.instance_id == inst.id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found for instance")

    source_name = file.filename or "upload.bin"
    content = await file.read()
    timestamp = int(utc_now().timestamp())
    primary_content, primary_ext = _optimize_uploaded_content(content, source_name, file.content_type)
    original_file_path: str | None = None
    optimized_file_path: str | None = None

    storage_dir = _ensure_documents_dir()
    if is_image_upload(source_name, file.content_type):
        try:
            image_asset = process_uploaded_image(
                content,
                source_name=source_name,
                content_type=file.content_type,
                generate_pdf=True,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
        primary_content = image_asset.pdf_bytes or primary_content
        primary_ext = ".pdf"
        stem = f"instance_{inst.id}_{timestamp}_{Path(source_name).stem}"
        original_file_path = _write_bytes(
            storage_dir,
            f"{stem}__original{image_asset.original_ext}",
            image_asset.original_bytes,
        )
        optimized_file_path = _write_bytes(
            storage_dir,
            f"{stem}__optimized{image_asset.optimized_ext}",
            image_asset.optimized_bytes,
        )

    if len(primary_content) > settings.document_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"파일 크기는 최적화 후 기준 {settings.document_upload_max_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
        )

    requirement_title = (
        db.query(DocumentRequirement.title)
        .filter(DocumentRequirement.id == inst.selected_requirement_id)
        .scalar()
        if inst.selected_requirement_id
        else None
    )
    site_row = db.query(Site.site_code, Site.site_name).filter(Site.id == inst.site_id).first()
    site_code = site_row[0] if site_row else None
    site_name = site_row[1] if site_row and site_row[1] else f"site_{inst.site_id}"
    safe_name = _build_saved_filename(
        document_type_code=inst.document_type_code or doc.document_type,
        requirement_title=requirement_title or doc.title,
        site_code=site_code,
        site_name=site_name,
        period_start=inst.period_start,
        extension=primary_ext,
    )
    next_version = (doc.version_no or 1) + 1
    filename = f"instance_{inst.id}_{timestamp}_v{next_version}_{safe_name}"
    stored_path = storage_dir / filename
    stored_path.write_bytes(primary_content)

    _record_upload_history(db, doc=doc, action_type="BEFORE_REPLACE_UPLOAD")
    doc.version_no = next_version
    doc.file_path = str(stored_path.relative_to(settings.storage_root))
    doc.original_file_path = original_file_path
    doc.optimized_file_path = optimized_file_path
    doc.file_name = safe_name
    doc.file_size = len(primary_content)
    doc.uploaded_by_user_id = current_user.id
    doc.uploaded_at = utc_now()
    doc.current_status = DocumentStatus.SUBMITTED
    doc.rejection_reason = None

    before = inst.workflow_status
    if before == WorkflowStatus.REJECTED:
        inst.workflow_status = WorkflowStatus.SUBMITTED

    add_review_history(
        db,
        inst=inst,
        document_id=doc.id,
        action_type=ReviewAction.REPLACE_UPLOAD,
        action_by_user_id=current_user.id,
        comment=None,
        from_workflow_status=before,
        to_workflow_status=inst.workflow_status,
    )
    db.add(inst)
    db.add(doc)
    _record_upload_history(db, doc=doc, action_type=ReviewAction.REPLACE_UPLOAD)
    db.commit()
    db.refresh(inst)
    db.refresh(doc)

    return {
        "instance_id": inst.id,
        "orchestration_status": inst.status,
        "workflow_status": inst.workflow_status,
        "document_id": doc.id,
        "file_path": doc.file_path,
        "original_file_path": doc.original_file_path,
        "optimized_file_path": doc.optimized_file_path,
    }


@router.get("/collection")
def collect_instances(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int,
    from_date: date,
    to_date: date,
):
    """
    특정 기간/현장 기준 취합 조회.
    - period_start 기준으로 범위 필터(단순 MVP)
    """
    if current_user.role == Role.SITE and site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    q = (
        db.query(DocumentInstance)
        .filter(
            DocumentInstance.site_id == site_id,
            DocumentInstance.period_start >= from_date,
            DocumentInstance.period_start <= to_date,
        )
        .order_by(DocumentInstance.period_start.asc(), DocumentInstance.id.asc())
    )
    items = []
    for inst in q.all():
        file_exists = False
        doc = db.query(Document).filter(Document.instance_id == inst.id).first()
        if doc and doc.file_path:
            p = settings.storage_root / doc.file_path
            file_exists = p.exists()
        items.append(
            {
                "instance_id": inst.id,
                "document_type_code": inst.document_type_code,
                "period_start": str(inst.period_start),
                "period_end": str(inst.period_end),
                "orchestration_status": inst.status,
                "status_reason": inst.status_reason,
                "workflow_status": inst.workflow_status,
                "file_present": file_exists,
            }
        )
    return {"site_id": site_id, "from_date": str(from_date), "to_date": str(to_date), "items": items}


@router.post("/export")
def export_approved(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: Annotated[int, Form(...)],
    from_date: Annotated[str, Form(...)],
    to_date: Annotated[str, Form(...)],
):
    """
    승인(APPROVED) 문서만 ZIP으로 묶어 export.
    반환: download_url
    """
    if current_user.role == Role.SITE and site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    f = date.fromisoformat(from_date)
    t = date.fromisoformat(to_date)

    insts = (
        db.query(DocumentInstance)
        .filter(
            DocumentInstance.site_id == site_id,
            DocumentInstance.period_start >= f,
            DocumentInstance.period_start <= t,
            DocumentInstance.workflow_status == WorkflowStatus.APPROVED,
        )
        .all()
    )

    exports_dir = _ensure_exports_dir()
    zip_name = f"export_site{site_id}_{from_date}_{to_date}_{int(utc_now().timestamp())}.zip"
    zip_path = exports_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for inst in insts:
            doc = db.query(Document).filter(Document.instance_id == inst.id).first()
            if not doc or not doc.file_path:
                continue
            p = settings.storage_root / doc.file_path
            if not p.exists():
                continue
            arcname = f"{inst.document_type_code}/{p.name}"
            zf.write(p, arcname=arcname)

    return {"download_url": f"/document-submissions/exports/{zip_name}", "zip_name": zip_name}


@router.get("/exports/{zip_name}")
def download_export(
    zip_name: str,
    current_user: CurrentUserDep,
):
    exports_dir = _ensure_exports_dir()
    zip_path = exports_dir / zip_name
    if not zip_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return FileResponse(path=zip_path, filename=zip_path.name)

