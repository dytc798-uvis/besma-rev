from __future__ import annotations

import io
import csv
import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from openpyxl import load_workbook

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.documents.models import Document
from app.modules.safety_features.models import (
    NonconformityItem,
    NonconformityLedger,
    SafetyEducationMaterial,
    SafetyInspectionComment,
    WorkerVoiceComment,
    WorkerVoiceItem,
    WorkerVoiceLedger,
)
from app.modules.sites.models import Site
from app.modules.users.models import User

router = APIRouter(prefix="/safety-features", tags=["safety-features"])


def _ensure_documents_dir() -> Path:
    d = settings.storage_root / settings.documents_dir_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _assert_site_access(current_user, site_id: int | None) -> None:
    if current_user.role == Role.SITE and site_id is not None and current_user.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


def _role_value(current_user) -> str:
    role = getattr(current_user, "role", None)
    return role.value if hasattr(role, "value") else str(role)


@router.get("/education")
def list_education_materials(db: DbDep, current_user: CurrentUserDep):
    q = db.query(SafetyEducationMaterial)
    if current_user.role == Role.SITE:
        q = q.filter((SafetyEducationMaterial.site_id.is_(None)) | (SafetyEducationMaterial.site_id == current_user.site_id))
    items = q.order_by(SafetyEducationMaterial.uploaded_at.desc(), SafetyEducationMaterial.id.desc()).all()
    user_ids = {i.uploaded_by_user_id for i in items}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    name_map = {u.id: u.name for u in users}
    return {
        "items": [
            {
                "id": i.id,
                "title": i.title,
                "site_id": i.site_id,
                "file_name": i.file_name,
                "uploaded_at": i.uploaded_at,
                "uploaded_by_name": name_map.get(i.uploaded_by_user_id),
                "file_url": f"/safety-features/file/education/{i.id}",
            }
            for i in items
        ]
    }


@router.post("/education/upload")
async def upload_education_material(
    db: DbDep,
    current_user: CurrentUserDep,
    title: str = Form(...),
    site_id: int | None = Form(None),
    file: UploadFile = File(...),
):
    if _role_value(current_user) not in {Role.HQ_SAFE.value, Role.HQ_SAFE_ADMIN.value, Role.SUPER_ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    clean_title = (title or "").strip()
    if not clean_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title is required")
    if site_id is not None and db.query(Site.id).filter(Site.id == site_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    content = await file.read()
    if len(content) > settings.document_upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="file too large")
    ext = Path(file.filename or "upload.bin").suffix or ".bin"
    filename = f"education_{int(utc_now().timestamp())}{ext}"
    stored = _ensure_documents_dir() / filename
    stored.write_bytes(content)
    row = SafetyEducationMaterial(
        title=clean_title,
        site_id=site_id,
        file_path=str(stored.relative_to(settings.storage_root)),
        file_name=file.filename or filename,
        file_size=len(content),
        uploaded_by_user_id=current_user.id,
        uploaded_at=utc_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.get("/inspections")
def list_safety_inspections(db: DbDep, current_user: CurrentUserDep):
    q = db.query(Document).filter(Document.document_type == "INSPECTION", Document.file_path.isnot(None))
    if current_user.role == Role.SITE:
        q = q.filter(Document.site_id == current_user.site_id)
    docs = q.order_by(Document.uploaded_at.asc().nullslast(), Document.id.asc()).all()
    doc_ids = [d.id for d in docs]
    comments = (
        db.query(SafetyInspectionComment)
        .filter(SafetyInspectionComment.document_id.in_(doc_ids))
        .order_by(SafetyInspectionComment.created_at.asc(), SafetyInspectionComment.id.asc())
        .all()
        if doc_ids
        else []
    )
    user_ids = {c.created_by_user_id for c in comments}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    name_map = {u.id: u.name for u in users}
    comment_map: dict[int, list[dict]] = {}
    for c in comments:
        comment_map.setdefault(c.document_id, []).append(
            {
                "id": c.id,
                "body": c.body,
                "created_at": c.created_at,
                "created_by_name": name_map.get(c.created_by_user_id),
            }
        )
    return {
        "items": [
            {
                "document_id": d.id,
                "title": d.title,
                "file_name": d.file_name,
                "uploaded_at": d.uploaded_at,
                "file_url": f"/documents/{d.id}/file",
                "comments": comment_map.get(d.id, []),
            }
            for d in docs
        ]
    }


@router.post("/inspections/{document_id}/comments")
def add_safety_inspection_comment(
    document_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    body: str = Form(...),
):
    doc = db.query(Document).filter(Document.id == document_id, Document.document_type == "INSPECTION").first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection document not found")
    _assert_site_access(current_user, doc.site_id)
    text = (body or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body is required")
    comment = SafetyInspectionComment(
        document_id=document_id,
        body=text,
        created_by_user_id=current_user.id,
        created_at=utc_now(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id}


def _extract_ledger_rows(content: bytes) -> list[dict]:
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    def norm(v: object) -> str:
        if v is None:
            return ""
        return str(v).strip().replace(" ", "").replace("\n", "")

    header_idx = None
    for i, row in enumerate(rows[:30]):
        cells = [norm(c) for c in row]
        line = "|".join(cells)
        if ("부적합" in line or "지적" in line) and ("조치" in line or "담당" in line):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    headers = [norm(c) for c in rows[header_idx]]

    def find_col(candidates: list[str]) -> int | None:
        for i, h in enumerate(headers):
            if not h:
                continue
            if any(k in h for k in candidates):
                return i
        return None

    issue_col = find_col(["부적합사항", "부적합", "지적사항", "지적내용"])
    if issue_col is None:
        issue_col = 0
    action_col = find_col(["개선조치", "조치계획및내용", "조치계획", "조치내용", "조치"])
    date_col = find_col(["개선조치일자", "조치일자", "개선일자", "완료일자"])
    owner_col = find_col(["조치담당자", "담당자", "담당"])

    data: list[dict] = []
    for idx, row in enumerate(rows[header_idx + 1 :], start=1):
        issue = str(row[issue_col]).strip() if issue_col < len(row) and row[issue_col] is not None else ""
        if not issue:
            continue
        data.append(
            {
                "row_no": idx,
                "issue_text": issue,
                "improvement_action": (
                    str(row[action_col]).strip() if action_col is not None and action_col < len(row) and row[action_col] is not None else None
                ),
                "improvement_owner": (
                    str(row[owner_col]).strip() if owner_col is not None and owner_col < len(row) and row[owner_col] is not None else None
                ),
                "improvement_date_raw": (
                    row[date_col] if date_col is not None and date_col < len(row) else None
                ),
            }
        )
    return data


def _extract_worker_voice_rows(content: bytes) -> list[dict]:
    wb = load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    return _extract_worker_voice_rows_from_rows(rows)


def _extract_worker_voice_rows_from_rows(rows: list[tuple | list]) -> list[dict]:
    if not rows:
        return []

    def norm(v: object) -> str:
        if v is None:
            return ""
        return str(v).strip().replace(" ", "").replace("\n", "")

    header_idx = None
    for i, row in enumerate(rows[:30]):
        cells = [norm(c) for c in row]
        non_empty_count = sum(1 for c in cells if c)
        opinion_indices = [idx for idx, c in enumerate(cells) if ("의견" in c or "건의" in c or "제안" in c or c == "내용")]
        name_indices = [idx for idx, c in enumerate(cells) if ("근로자" in c or "성명" in c or "이름" in c)]
        has_split_columns = any(oi != ni for oi in opinion_indices for ni in name_indices)
        if non_empty_count >= 2 and opinion_indices and name_indices and has_split_columns:
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    def is_secondary_header(row: tuple | list) -> bool:
        cells = [norm(c) for c in row]
        markers = ["성명", "이름", "내용", "조치", "전화", "공종", "직무", "담당", "생년월일", "휴대전화"]
        return sum(1 for c in cells if any(marker in c for marker in markers)) >= 2

    def is_primary_header(row: tuple | list) -> bool:
        cells = [norm(c) for c in row]
        markers = ["NO", "일자", "현장명", "의견", "회신", "비고", "조치"]
        return sum(1 for c in cells if any(marker in c for marker in markers)) >= 2

    headers = [norm(c) for c in rows[header_idx]]
    data_start_idx = header_idx + 1
    if header_idx > 0 and is_secondary_header(rows[header_idx]) and is_primary_header(rows[header_idx - 1]):
        primary = [norm(c) for c in rows[header_idx - 1]]
        secondary = headers
        merged_headers: list[str] = []
        for idx in range(max(len(primary), len(secondary))):
            top = primary[idx] if idx < len(primary) else ""
            bottom = secondary[idx] if idx < len(secondary) else ""
            if top and bottom and bottom not in top:
                merged_headers.append(f"{top}{bottom}")
            else:
                merged_headers.append(top or bottom)
        headers = merged_headers
    elif header_idx + 1 < len(rows) and is_secondary_header(rows[header_idx + 1]):
        secondary = [norm(c) for c in rows[header_idx + 1]]
        merged_headers: list[str] = []
        for idx in range(max(len(headers), len(secondary))):
            top = headers[idx] if idx < len(headers) else ""
            bottom = secondary[idx] if idx < len(secondary) else ""
            if top and bottom and bottom not in top:
                merged_headers.append(f"{top}{bottom}")
            else:
                merged_headers.append(top or bottom)
        headers = merged_headers
        data_start_idx = header_idx + 2

    def find_col(candidates: list[str]) -> int | None:
        for i, h in enumerate(headers):
            if any(k in h for k in candidates):
                return i
        return None

    name_col = find_col(["근로자", "성명", "이름", "name"])
    birth_col = find_col(["생년월일", "출생", "dob", "birth"])
    phone_col = find_col(["휴대전화", "전화번호", "핸드폰", "연락처", "phone", "mobile"])
    kind_col = find_col(["의견종류", "의견유형", "제안유형", "의견수렴경로", "type"])
    opinion_col = find_col(["근로자의견", "의견내용", "건의내용", "제안내용", "의견", "건의", "제안", "내용"])
    if opinion_col is not None and kind_col is not None and opinion_col == kind_col:
        for i, h in enumerate(headers):
            if any(k in h for k in ["의견내용", "근로자의견", "건의내용", "제안내용"]):
                opinion_col = i
                break
    if opinion_col is None:
        opinion_col = 0

    def normalize_kind(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        compact = text.replace(" ", "").lower()
        if "아차" in text or "near" in compact:
            return "아차사고"
        if "유해" in text or "위험" in text or "hazard" in compact:
            return "유해위험요인발굴"
        return text

    out: list[dict] = []
    for idx, row in enumerate(rows[data_start_idx:], start=1):
        opinion = str(row[opinion_col]).strip() if opinion_col < len(row) and row[opinion_col] is not None else ""
        if not opinion:
            continue
        worker_name = str(row[name_col]).strip() if name_col is not None and name_col < len(row) and row[name_col] is not None else None
        worker_birth_date = (
            str(row[birth_col]).strip() if birth_col is not None and birth_col < len(row) and row[birth_col] is not None else None
        )
        worker_phone_number = (
            str(row[phone_col]).strip() if phone_col is not None and phone_col < len(row) and row[phone_col] is not None else None
        )
        opinion_kind = normalize_kind(row[kind_col]) if kind_col is not None and kind_col < len(row) else None
        out.append(
            {
                "row_no": idx,
                "worker_name": worker_name,
                "worker_birth_date": worker_birth_date,
                "worker_phone_number": worker_phone_number,
                "opinion_kind": opinion_kind,
                "opinion_text": opinion,
            }
        )
    return out


def _extract_worker_voice_rows_from_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader]
    if not rows:
        return []
    return _extract_worker_voice_rows_from_rows(rows)


@router.post("/worker-voice/upload")
async def upload_worker_voice_ledger(
    db: DbDep,
    current_user: CurrentUserDep,
    title: str | None = Form(None),
    site_id: int | None = Form(None),
    file: UploadFile = File(...),
):
    if current_user.role == Role.SITE:
        site_id = current_user.site_id
    if site_id is not None and db.query(Site.id).filter(Site.id == site_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    clean_title = (title or "").strip() or "근로자 의견청취 관리대장"
    content = await file.read()
    if len(content) > settings.document_upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="file too large")
    ext = Path(file.filename or "ledger.xlsx").suffix or ".xlsx"
    filename = f"worker_voice_{int(utc_now().timestamp())}{ext}"
    stored = _ensure_documents_dir() / filename
    stored.write_bytes(content)
    ledger = WorkerVoiceLedger(
        site_id=site_id,
        title=clean_title,
        file_path=str(stored.relative_to(settings.storage_root)),
        file_name=file.filename or filename,
        file_size=len(content),
        uploaded_by_user_id=current_user.id,
        uploaded_at=utc_now(),
    )
    db.add(ledger)
    db.flush()
    suffix = ext.lower()
    if suffix == ".csv":
        parsed_rows = _extract_worker_voice_rows_from_csv(content)
    else:
        parsed_rows = _extract_worker_voice_rows(content)
    for row in parsed_rows:
        db.add(
            WorkerVoiceItem(
                ledger_id=ledger.id,
                row_no=row["row_no"],
                worker_name=row["worker_name"],
                worker_birth_date=row["worker_birth_date"],
                worker_phone_number=row["worker_phone_number"],
                opinion_kind=row["opinion_kind"],
                opinion_text=row["opinion_text"],
            )
        )
    db.commit()
    db.refresh(ledger)
    return {"id": ledger.id}


@router.get("/worker-voice/items")
def list_worker_voice_items(db: DbDep, current_user: CurrentUserDep):
    q = db.query(WorkerVoiceItem, WorkerVoiceLedger).join(WorkerVoiceLedger, WorkerVoiceLedger.id == WorkerVoiceItem.ledger_id)
    if current_user.role == Role.SITE:
        q = q.filter(WorkerVoiceLedger.site_id == current_user.site_id)
    rows = q.order_by(WorkerVoiceLedger.uploaded_at.desc(), WorkerVoiceItem.row_no.asc(), WorkerVoiceItem.id.asc()).all()
    item_ids = [row[0].id for row in rows]
    comments = (
        db.query(WorkerVoiceComment)
        .filter(WorkerVoiceComment.item_id.in_(item_ids))
        .order_by(WorkerVoiceComment.created_at.asc(), WorkerVoiceComment.id.asc())
        .all()
        if item_ids
        else []
    )
    user_ids = {c.created_by_user_id for c in comments}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    name_map = {u.id: u.name for u in users}
    comment_map: dict[int, list[dict]] = {}
    for c in comments:
        comment_map.setdefault(c.item_id, []).append(
            {"id": c.id, "body": c.body, "created_at": c.created_at, "created_by_name": name_map.get(c.created_by_user_id)}
        )
    return {
        "items": [
            {
                "id": item.id,
                "ledger_title": ledger.title,
                "worker_name": item.worker_name,
                "worker_birth_date": item.worker_birth_date,
                "worker_phone_number": item.worker_phone_number,
                "opinion_kind": item.opinion_kind,
                "opinion_text": item.opinion_text,
                "site_approved": item.site_approved,
                "hq_checked": item.hq_checked,
                "reward_candidate": item.reward_candidate,
                "comments": comment_map.get(item.id, []),
            }
            for item, ledger in rows
        ]
    }


@router.post("/worker-voice/items/{item_id}/site-approve")
def site_approve_worker_voice(item_id: int, db: DbDep, current_user: CurrentUserDep):
    item = db.query(WorkerVoiceItem).filter(WorkerVoiceItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    ledger = db.query(WorkerVoiceLedger).filter(WorkerVoiceLedger.id == item.ledger_id).first()
    _assert_site_access(current_user, ledger.site_id if ledger else None)
    if _role_value(current_user) != Role.SITE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only SITE can approve first")
    item.site_approved = True
    item.site_approved_by_user_id = current_user.id
    item.site_approved_at = utc_now()
    db.add(item)
    db.commit()
    return {"ok": True}


@router.post("/worker-voice/items/{item_id}/hq-check")
def hq_check_worker_voice(item_id: int, db: DbDep, current_user: CurrentUserDep):
    item = db.query(WorkerVoiceItem).filter(WorkerVoiceItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if not item.site_approved:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SITE approval required first")
    if _role_value(current_user) not in {Role.HQ_SAFE.value, Role.HQ_SAFE_ADMIN.value, Role.SUPER_ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only HQ can check")
    item.hq_checked = True
    item.hq_checked_by_user_id = current_user.id
    item.hq_checked_at = utc_now()
    db.add(item)
    db.commit()
    return {"ok": True}


@router.post("/worker-voice/items/{item_id}/reward-candidate")
def promote_worker_voice_reward_candidate(item_id: int, db: DbDep, current_user: CurrentUserDep):
    item = db.query(WorkerVoiceItem).filter(WorkerVoiceItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if not item.site_approved:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SITE approval required first")
    if not item.hq_checked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="HQ check required first")
    if _role_value(current_user) not in {Role.HQ_SAFE.value, Role.HQ_SAFE_ADMIN.value, Role.SUPER_ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only HQ can select reward candidates")
    item.reward_candidate = True
    item.reward_candidate_by_user_id = current_user.id
    item.reward_candidate_at = utc_now()
    db.add(item)
    db.commit()
    return {"ok": True}


@router.post("/worker-voice/items/{item_id}/comments")
def add_worker_voice_comment(
    item_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    body: str = Form(...),
):
    item = db.query(WorkerVoiceItem).filter(WorkerVoiceItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    ledger = db.query(WorkerVoiceLedger).filter(WorkerVoiceLedger.id == item.ledger_id).first()
    _assert_site_access(current_user, ledger.site_id if ledger else None)
    text = (body or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body is required")
    comment = WorkerVoiceComment(
        item_id=item_id,
        body=text,
        created_by_user_id=current_user.id,
        created_at=utc_now(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id}


@router.post("/nonconformities/upload")
async def upload_nonconformity_ledger(
    db: DbDep,
    current_user: CurrentUserDep,
    title: str | None = Form(None),
    site_id: int | None = Form(None),
    file: UploadFile = File(...),
):
    if current_user.role == Role.SITE:
        site_id = current_user.site_id
    if site_id is not None and db.query(Site.id).filter(Site.id == site_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    clean_title = (title or "").strip() or "부적합사항관리대장"
    content = await file.read()
    if len(content) > settings.document_upload_max_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="file too large")
    ext = Path(file.filename or "ledger.xlsx").suffix or ".xlsx"
    filename = f"nonconformity_{int(utc_now().timestamp())}{ext}"
    stored = _ensure_documents_dir() / filename
    stored.write_bytes(content)

    ledger = NonconformityLedger(
        site_id=site_id,
        title=clean_title,
        file_path=str(stored.relative_to(settings.storage_root)),
        file_name=file.filename or filename,
        file_size=len(content),
        uploaded_by_user_id=current_user.id,
        uploaded_at=utc_now(),
    )
    db.add(ledger)
    db.flush()

    rows = _extract_ledger_rows(content)
    for r in rows:
        db.add(
            NonconformityItem(
                ledger_id=ledger.id,
                row_no=r["row_no"],
                issue_text=r["issue_text"],
                improvement_action=r["improvement_action"],
                improvement_owner=r["improvement_owner"],
            )
        )
    db.commit()
    db.refresh(ledger)
    return {"id": ledger.id}


@router.get("/nonconformities")
def list_nonconformity_ledgers(db: DbDep, current_user: CurrentUserDep):
    q = db.query(NonconformityLedger)
    if current_user.role == Role.SITE:
        q = q.filter(NonconformityLedger.site_id == current_user.site_id)
    ledgers = q.order_by(NonconformityLedger.uploaded_at.desc(), NonconformityLedger.id.desc()).all()
    return {
        "items": [
            {
                "id": l.id,
                "title": l.title,
                "uploaded_at": l.uploaded_at,
                "file_name": l.file_name,
                "download_url": f"/safety-features/file/nonconformity/{l.id}",
                "pdf_view_url": f"/safety-features/nonconformities/{l.id}/pdf",
            }
            for l in ledgers
        ]
    }


@router.get("/nonconformities/{ledger_id}")
def get_nonconformity_ledger_detail(ledger_id: int, db: DbDep, current_user: CurrentUserDep):
    ledger = db.query(NonconformityLedger).filter(NonconformityLedger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")
    _assert_site_access(current_user, ledger.site_id)
    items = (
        db.query(NonconformityItem)
        .filter(NonconformityItem.ledger_id == ledger_id)
        .order_by(NonconformityItem.row_no.asc(), NonconformityItem.id.asc())
        .all()
    )
    return {
        "ledger": {
            "id": ledger.id,
            "title": ledger.title,
            "uploaded_at": ledger.uploaded_at,
            "file_name": ledger.file_name,
        },
        "items": [
            {
                "id": i.id,
                "row_no": i.row_no,
                "issue_text": i.issue_text,
                "improvement_action": i.improvement_action,
                "improvement_date": i.improvement_date,
                "improvement_owner": i.improvement_owner,
                "improvement_photo_url": (f"/safety-features/nonconformities/items/{i.id}/photo" if i.improvement_photo_path else None),
            }
            for i in items
        ],
    }


@router.post("/nonconformities/items/{item_id}")
def update_nonconformity_item(
    item_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    improvement_action: str | None = Form(None),
    improvement_date: str | None = Form(None),
    improvement_owner: str | None = Form(None),
):
    item = db.query(NonconformityItem).filter(NonconformityItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    ledger = db.query(NonconformityLedger).filter(NonconformityLedger.id == item.ledger_id).first()
    _assert_site_access(current_user, ledger.site_id if ledger else None)
    item.improvement_action = (improvement_action or "").strip() or None
    item.improvement_owner = (improvement_owner or "").strip() or None
    if improvement_date:
        from datetime import date

        item.improvement_date = date.fromisoformat(improvement_date)
    elif improvement_date == "":
        item.improvement_date = None
    db.add(item)
    db.commit()
    return {"ok": True}


@router.post("/nonconformities/items/{item_id}/photo")
async def upload_nonconformity_item_photo(
    item_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    file: UploadFile = File(...),
):
    item = db.query(NonconformityItem).filter(NonconformityItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    ledger = db.query(NonconformityLedger).filter(NonconformityLedger.id == item.ledger_id).first()
    _assert_site_access(current_user, ledger.site_id if ledger else None)
    from PIL import Image

    content = await file.read()
    img = Image.open(io.BytesIO(content))
    max_px = 1280
    if img.width > max_px or img.height > max_px:
        img.thumbnail((max_px, max_px))
    if img.mode not in {"RGB", "L"}:
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=75, optimize=True)
    photo_name = f"nonconf_item_{item.id}_{int(utc_now().timestamp())}.jpg"
    photo_path = _ensure_documents_dir() / photo_name
    photo_path.write_bytes(out.getvalue())
    item.improvement_photo_path = str(photo_path.relative_to(settings.storage_root))
    db.add(item)
    db.commit()
    return {"ok": True}


@router.get("/nonconformities/items/{item_id}/photo")
def view_nonconformity_item_photo(item_id: int, db: DbDep, current_user: CurrentUserDep):
    item = db.query(NonconformityItem).filter(NonconformityItem.id == item_id).first()
    if item is None or not item.improvement_photo_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    ledger = db.query(NonconformityLedger).filter(NonconformityLedger.id == item.ledger_id).first()
    _assert_site_access(current_user, ledger.site_id if ledger else None)
    path = settings.storage_root / item.improvement_photo_path
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return FileResponse(path=path, media_type="image/jpeg", filename=path.name)


@router.get("/nonconformities/{ledger_id}/pdf")
def render_nonconformity_ledger_pdf(ledger_id: int, db: DbDep, current_user: CurrentUserDep):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    ledger = db.query(NonconformityLedger).filter(NonconformityLedger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ledger not found")
    _assert_site_access(current_user, ledger.site_id)
    items = (
        db.query(NonconformityItem)
        .filter(NonconformityItem.ledger_id == ledger_id)
        .order_by(NonconformityItem.row_no.asc(), NonconformityItem.id.asc())
        .all()
    )
    pdfmetrics.registerFont(UnicodeCIDFont("HYGothic-Medium"))
    buff = io.BytesIO()
    p = canvas.Canvas(buff, pagesize=A4)
    p.setFont("HYGothic-Medium", 12)
    y = 800
    p.drawString(40, y, f"부적합사항관리대장: {ledger.title}")
    y -= 24
    for idx, i in enumerate(items, start=1):
        line = f"{idx}. {i.issue_text} / 조치:{i.improvement_action or '-'} / 일자:{i.improvement_date or '-'} / 담당:{i.improvement_owner or '-'}"
        p.drawString(40, y, line[:110])
        y -= 18
        if y < 60:
            p.showPage()
            p.setFont("HYGothic-Medium", 12)
            y = 800
    p.save()
    return Response(
        content=buff.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote((ledger.title or 'nonconformity') + '.pdf')}"},
    )


@router.get("/file/{file_type}/{entity_id}")
def download_feature_file(file_type: str, entity_id: int, db: DbDep, current_user: CurrentUserDep):
    if file_type == "education":
        row = db.query(SafetyEducationMaterial).filter(SafetyEducationMaterial.id == entity_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        _assert_site_access(current_user, row.site_id)
        file_path = settings.storage_root / row.file_path
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        resp = FileResponse(path=file_path, media_type=media_type, filename=row.file_name)
        resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(row.file_name)}"
        return resp
    if file_type == "nonconformity":
        row = db.query(NonconformityLedger).filter(NonconformityLedger.id == entity_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        _assert_site_access(current_user, row.site_id)
        file_path = settings.storage_root / row.file_path
        if not file_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        media_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        resp = FileResponse(path=file_path, media_type=media_type, filename=row.file_name)
        resp.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(row.file_name)}"
        return resp
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown file type")
