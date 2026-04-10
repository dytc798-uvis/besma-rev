from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.document_settings.models import (
    ContractorDocumentBundleItem,
    DynamicMenuBoardComment,
    DynamicMenuBoardPost,
    DynamicMenuConfig,
    DynamicMenuTableRow,
    UIMenuOrderConfig,
    DocumentRequirement,
    DocumentTypeMaster,
    SubmissionCycle,
)
from app.modules.sites.models import Site
from app.schemas.document_cycles import (
    ContractorBundleItemRead,
    DocumentRequirementRead,
    DocumentRequirementUpsert,
    DocumentTypeMasterCreate,
    DocumentTypeMasterRead,
    DocumentTypeMasterUpdate,
    SubmissionCycleRead,
    ContractorBundleItemUpsert,
)


router = APIRouter(prefix="/settings/document-cycles", tags=["document-cycles"])

_PILOT_SITE_CODE = "SITE002"  # MVP: 파일럿 = 청라 C18BL(대우건설) 시드 현장
_GROUP_KEY_SAMSUNG = "SAMSUNG"
_GROUP_KEY_GENERAL = "GENERAL"
_USER_GUIDE_SHOTS_ROOT = settings.storage_root / "user_guide_shots"


def _normalize_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9\-]+", "-", (text or "").strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:80] or "menu"


def _parse_menu_config(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _parse_menu_order_keys(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, list):
            return []
        keys: list[str] = []
        for item in parsed:
            text = str(item or "").strip()
            if text:
                keys.append(text)
        return keys
    except Exception:
        return []


def _normalize_ui_type(value: str) -> str:
    v = (value or "").strip().upper()
    if v not in {"SITE", "HQ_SAFE"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ui_type must be SITE or HQ_SAFE")
    return v


def _sanitize_path_segment(value: str, *, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\-_]+", "_", (value or "").strip())
    cleaned = cleaned.strip("_")
    return (cleaned[:80] or fallback)


def require_cycle_admin(user: CurrentUserDep):
    if user.role not in {Role.HQ_SAFE.value, Role.SUPER_ADMIN.value, Role.HQ_SAFE_ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions for document-cycle settings",
        )
    return user


@router.get("/cycles", response_model=list[SubmissionCycleRead])
def list_cycles(db: DbDep):
    return db.query(SubmissionCycle).order_by(SubmissionCycle.sort_order.asc()).all()


@router.get("/document-types", response_model=list[DocumentTypeMasterRead])
def list_document_types(db: DbDep):
    return db.query(DocumentTypeMaster).order_by(DocumentTypeMaster.sort_order.asc()).all()


@router.post("/document-types", response_model=DocumentTypeMasterRead)
def create_document_type(
    payload: DocumentTypeMasterCreate,
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    obj = DocumentTypeMaster(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/document-types/{document_type_id}", response_model=DocumentTypeMasterRead)
def update_document_type(
    document_type_id: int,
    payload: DocumentTypeMasterUpdate,
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    obj = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.id == document_type_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DocumentType not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/document-types/{document_type_id}")
def delete_document_type(
    document_type_id: int,
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    obj = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.id == document_type_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DocumentType not found")

    # 하드 삭제 대신 비활성화 처리하여 기존 이력/참조를 보존한다.
    obj.is_active = False
    db.commit()
    return {"ok": True, "document_type_id": document_type_id}


@router.get("/sites/{site_id}/requirements", response_model=list[DocumentRequirementRead])
def list_site_requirements(site_id: int, db: DbDep, __=Depends(require_cycle_admin)):
    return (
        db.query(DocumentRequirement)
        .filter(DocumentRequirement.site_id == site_id)
        .order_by(DocumentRequirement.document_type_id.asc())
        .all()
    )


def _periods_overlap(a_from: date | None, a_to: date | None, b_from: date | None, b_to: date | None) -> bool:
    a_start = a_from or date.min
    a_end = a_to or date.max
    b_start = b_from or date.min
    b_end = b_to or date.max
    return a_start <= b_end and b_start <= a_end


@router.put("/sites/{site_id}/requirements", response_model=list[DocumentRequirementRead])
def upsert_site_requirements(
    site_id: int,
    payloads: list[DocumentRequirementUpsert],
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    """
    MVP upsert 규칙:
    - 키: (site_id, document_type_id, effective_from, effective_to)
    - enabled끼리 기간 중복은 금지(409)
    - disabled는 기간 겹침 허용(특정 기간 생성 금지 규칙 표현)
    """
    results: list[DocumentRequirement] = []

    for p in payloads:
        doc_type = db.query(DocumentTypeMaster).filter(DocumentTypeMaster.id == p.document_type_id).first()
        if doc_type is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document_type_id")
        req_code = p.code or doc_type.code
        req_title = p.title or doc_type.name

        existing_rules = (
            db.query(DocumentRequirement)
            .filter(
                DocumentRequirement.site_id == site_id,
                DocumentRequirement.document_type_id == p.document_type_id,
            )
            .all()
        )
        for e in existing_rules:
            if _periods_overlap(e.effective_from, e.effective_to, p.effective_from, p.effective_to):
                same_key = (
                    e.document_type_id == p.document_type_id
                    and e.effective_from == p.effective_from
                    and e.effective_to == p.effective_to
                )
                if not same_key and (e.is_enabled is True and p.is_enabled is True):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Overlapping enabled requirement exists for this site/document_type",
                    )

        obj = (
            db.query(DocumentRequirement)
            .filter(
                DocumentRequirement.site_id == site_id,
                DocumentRequirement.document_type_id == p.document_type_id,
                DocumentRequirement.effective_from == p.effective_from,
                DocumentRequirement.effective_to == p.effective_to,
            )
            .first()
        )

        if obj:
            obj.is_enabled = p.is_enabled
            obj.code = req_code
            obj.title = req_title
            obj.frequency = p.frequency
            obj.is_required = p.is_required
            obj.display_order = p.display_order
            obj.due_rule_text = p.due_rule_text
            obj.note = p.note
            obj.override_cycle_id = p.override_cycle_id
            obj.override_generation_rule = p.override_generation_rule
            obj.override_generation_value = p.override_generation_value
            obj.override_due_offset_days = p.override_due_offset_days
        else:
            obj = DocumentRequirement(
                site_id=site_id,
                document_type_id=p.document_type_id,
                is_enabled=p.is_enabled,
                code=req_code,
                title=req_title,
                frequency=p.frequency,
                is_required=p.is_required,
                display_order=p.display_order,
                due_rule_text=p.due_rule_text,
                note=p.note,
                override_cycle_id=p.override_cycle_id,
                override_generation_rule=p.override_generation_rule,
                override_generation_value=p.override_generation_value,
                override_due_offset_days=p.override_due_offset_days,
                effective_from=p.effective_from,
                effective_to=p.effective_to,
            )
            db.add(obj)

        results.append(obj)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


def _get_representative_site_id(db: DbDep, group_key: str) -> int:
    # MVP: 삼성 전용 그룹은 파일럿현장을 대표로 사용
    # 일반 그룹은 (파일럿 제외) 첫 현장을 대표로 사용
    pilot = db.query(Site).filter(Site.site_code == _PILOT_SITE_CODE).first()
    if group_key == _GROUP_KEY_SAMSUNG:
        if not pilot:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pilot site not found")
        return pilot.id

    non_pilot = db.query(Site).filter(Site.site_code != _PILOT_SITE_CODE).order_by(Site.id.asc()).first()
    if not non_pilot:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Non-pilot site not found")
    return non_pilot.id


def _validate_group_key(group_key: str) -> str:
    if group_key not in {_GROUP_KEY_SAMSUNG, _GROUP_KEY_GENERAL}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid group_key")
    return group_key


@router.get("/contractor-bundles/{group_key}/items", response_model=list[ContractorBundleItemRead])
def list_contractor_bundle_items(
    group_key: str,
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    group_key = _validate_group_key(group_key)
    rep_site_id = _get_representative_site_id(db, group_key)

    base_reqs = (
        db.query(DocumentRequirement)
        .filter(DocumentRequirement.site_id == rep_site_id)
        .order_by(DocumentRequirement.document_type_id.asc(), DocumentRequirement.display_order.asc())
        .all()
    )

    overrides = (
        db.query(ContractorDocumentBundleItem)
        .filter(ContractorDocumentBundleItem.group_key == group_key)
        .all()
    )
    override_map = {o.document_type_id: o for o in overrides}

    items: list[ContractorBundleItemRead] = []
    for req in base_reqs:
        o = override_map.get(req.document_type_id)
        items.append(
            ContractorBundleItemRead(
                base_is_enabled=req.is_enabled,
                base_is_required=req.is_required,
                base_frequency=req.frequency,
                base_display_order=req.display_order,
                base_due_rule_text=req.due_rule_text,
                base_note=req.note,
                document_type_id=req.document_type_id,
                code=req.code,
                title=req.title,
                is_enabled=o.is_enabled if o else req.is_enabled,
                is_required=o.is_required if o else req.is_required,
                frequency=o.frequency if o else req.frequency,
                display_order=o.display_order if o else req.display_order,
                due_rule_text=o.due_rule_text if o else req.due_rule_text,
                note=o.note if o else req.note,
                has_override=o is not None,
            )
        )

    # UI 정렬(실효 display_order 기준)
    items.sort(key=lambda x: (x.display_order, x.document_type_id))
    return items


@router.put("/contractor-bundles/{group_key}/items", response_model=list[ContractorBundleItemRead])
def upsert_contractor_bundle_items(
    group_key: str,
    payloads: list[ContractorBundleItemUpsert],
    db: DbDep,
    __=Depends(require_cycle_admin),
):
    """
    MVP upsert 규칙:
    - 대표 site의 base 요구사항과 완전히 동일하면 override row 삭제(기본으로 회귀)
    - 다르면 override row upsert
    """
    group_key = _validate_group_key(group_key)
    rep_site_id = _get_representative_site_id(db, group_key)

    base_reqs = (
        db.query(DocumentRequirement)
        .filter(DocumentRequirement.site_id == rep_site_id)
        .all()
    )
    base_map = {r.document_type_id: r for r in base_reqs}

    # payload는 document_type_id 키로만 업데이트
    updated_items: list[ContractorBundleItemRead] = []
    for p in payloads:
        base = base_map.get(p.document_type_id)
        if not base:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document_type_id")

        same_as_base = (
            p.is_enabled == base.is_enabled
            and p.is_required == base.is_required
            and p.frequency == base.frequency
            and p.display_order == base.display_order
            and p.due_rule_text == base.due_rule_text
            and p.note == base.note
        )

        existing = (
            db.query(ContractorDocumentBundleItem)
            .filter(
                ContractorDocumentBundleItem.group_key == group_key,
                ContractorDocumentBundleItem.document_type_id == p.document_type_id,
            )
            .first()
        )

        if same_as_base:
            if existing:
                db.delete(existing)
            continue

        if existing:
            existing.is_enabled = p.is_enabled
            existing.is_required = p.is_required
            existing.frequency = p.frequency
            existing.display_order = p.display_order
            existing.due_rule_text = p.due_rule_text
            existing.note = p.note
        else:
            existing = ContractorDocumentBundleItem(
                group_key=group_key,
                document_type_id=p.document_type_id,
                is_enabled=p.is_enabled,
                is_required=p.is_required,
                frequency=p.frequency,
                display_order=p.display_order,
                due_rule_text=p.due_rule_text,
                note=p.note,
            )
            db.add(existing)

        updated_items.append(
            ContractorBundleItemRead(
                base_is_enabled=base.is_enabled,
                base_is_required=base.is_required,
                base_frequency=base.frequency,
                base_display_order=base.display_order,
                base_due_rule_text=base.due_rule_text,
                base_note=base.note,
                document_type_id=p.document_type_id,
                code=base.code,
                title=base.title,
                is_enabled=existing.is_enabled,
                is_required=existing.is_required,
                frequency=existing.frequency,
                display_order=existing.display_order,
                due_rule_text=existing.due_rule_text,
                note=existing.note,
                has_override=existing is not None,
            )
        )

    db.commit()
    # 클라이언트는 GET으로 전체를 다시 로드하는 패턴이 안전하지만,
    # MVP에서는 response_model로 간단히 업데이트된 payload만 반환합니다.
    return updated_items


@router.get("/dynamic-menus")
def list_dynamic_menus(db: DbDep, __=Depends(require_cycle_admin)):
    rows = db.query(DynamicMenuConfig).order_by(DynamicMenuConfig.sort_order.asc(), DynamicMenuConfig.id.asc()).all()
    return {
        "items": [
            {
                "id": r.id,
                "slug": r.slug,
                "title": r.title,
                "menu_type": r.menu_type,
                "target_ui_type": r.target_ui_type,
                "sort_order": r.sort_order,
                "is_active": r.is_active,
                "custom_config": _parse_menu_config(r.custom_config),
            }
            for r in rows
        ]
    }


@router.post("/dynamic-menus")
def create_dynamic_menu(payload: dict, db: DbDep, current_user: CurrentUserDep, __=Depends(require_cycle_admin)):
    title = str(payload.get("title") or "").strip()
    menu_type = str(payload.get("menu_type") or "").strip().upper()
    target_ui_type = str(payload.get("target_ui_type") or "SITE").strip().upper()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title is required")
    if menu_type not in {"BOARD", "TABLE"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="menu_type must be BOARD or TABLE")
    if target_ui_type not in {"SITE", "HQ_SAFE", "BOTH"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_ui_type must be SITE/HQ_SAFE/BOTH")
    slug = _normalize_slug(str(payload.get("slug") or title))
    suffix = 1
    while db.query(DynamicMenuConfig.id).filter(DynamicMenuConfig.slug == slug).first() is not None:
        suffix += 1
        slug = f"{_normalize_slug(str(payload.get('slug') or title))}-{suffix}"
    max_order = db.query(DynamicMenuConfig).order_by(DynamicMenuConfig.sort_order.desc()).first()
    config = payload.get("custom_config") if isinstance(payload.get("custom_config"), dict) else {}
    row = DynamicMenuConfig(
        slug=slug,
        title=title,
        menu_type=menu_type,
        target_ui_type=target_ui_type,
        sort_order=(max_order.sort_order + 1) if max_order else 1,
        is_active=bool(payload.get("is_active", True)),
        custom_config=json.dumps(config, ensure_ascii=False),
        created_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "slug": row.slug}


@router.put("/dynamic-menus/{menu_id}")
def update_dynamic_menu(menu_id: int, payload: dict, db: DbDep, __=Depends(require_cycle_admin)):
    row = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.id == menu_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    if "title" in payload:
        row.title = str(payload.get("title") or "").strip() or row.title
    if "menu_type" in payload:
        mt = str(payload.get("menu_type") or "").strip().upper()
        if mt not in {"BOARD", "TABLE"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="menu_type must be BOARD or TABLE")
        row.menu_type = mt
    if "target_ui_type" in payload:
        tui = str(payload.get("target_ui_type") or "").strip().upper()
        if tui not in {"SITE", "HQ_SAFE", "BOTH"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_ui_type must be SITE/HQ_SAFE/BOTH")
        row.target_ui_type = tui
    if "is_active" in payload:
        row.is_active = bool(payload.get("is_active"))
    if "custom_config" in payload and isinstance(payload.get("custom_config"), dict):
        row.custom_config = json.dumps(payload["custom_config"], ensure_ascii=False)
    db.add(row)
    db.commit()
    return {"ok": True}


@router.post("/dynamic-menus/reorder")
def reorder_dynamic_menus(payload: dict, db: DbDep, __=Depends(require_cycle_admin)):
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="items is required")
    for idx, it in enumerate(items, start=1):
        menu_id = int(it.get("id"))
        row = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.id == menu_id).first()
        if row is None:
            continue
        row.sort_order = idx
        db.add(row)
    db.commit()
    return {"ok": True}


@router.get("/menu-orders/{ui_type}")
def get_menu_order_config(ui_type: str, db: DbDep, __=Depends(require_cycle_admin)):
    normalized_ui_type = _normalize_ui_type(ui_type)
    row = db.query(UIMenuOrderConfig).filter(UIMenuOrderConfig.ui_type == normalized_ui_type).first()
    return {"ui_type": normalized_ui_type, "ordered_keys": _parse_menu_order_keys(row.ordered_keys if row else "[]")}


@router.put("/menu-orders/{ui_type}")
def upsert_menu_order_config(
    ui_type: str,
    payload: dict,
    db: DbDep,
    current_user: CurrentUserDep,
    __=Depends(require_cycle_admin),
):
    normalized_ui_type = _normalize_ui_type(ui_type)
    keys_raw = payload.get("ordered_keys")
    if not isinstance(keys_raw, list):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ordered_keys must be list")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in keys_raw:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    row = db.query(UIMenuOrderConfig).filter(UIMenuOrderConfig.ui_type == normalized_ui_type).first()
    if row is None:
        row = UIMenuOrderConfig(
            ui_type=normalized_ui_type,
            ordered_keys=json.dumps(deduped, ensure_ascii=False),
            updated_by_user_id=current_user.id,
        )
    else:
        row.ordered_keys = json.dumps(deduped, ensure_ascii=False)
        row.updated_by_user_id = current_user.id
    db.add(row)
    db.commit()
    return {"ok": True}


@router.delete("/dynamic-menus/{menu_id}")
def delete_dynamic_menu(menu_id: int, db: DbDep, __=Depends(require_cycle_admin)):
    row = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.id == menu_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    db.query(DynamicMenuTableRow).filter(DynamicMenuTableRow.menu_id == menu_id).delete()
    posts = db.query(DynamicMenuBoardPost).filter(DynamicMenuBoardPost.menu_id == menu_id).all()
    post_ids = [p.id for p in posts]
    if post_ids:
        db.query(DynamicMenuBoardComment).filter(DynamicMenuBoardComment.post_id.in_(post_ids)).delete(synchronize_session=False)
        db.query(DynamicMenuBoardPost).filter(DynamicMenuBoardPost.id.in_(post_ids)).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/user-guide-shots/upload")
async def upload_user_guide_shot(
    section: str = Form(...),
    label: str | None = Form(None),
    file: UploadFile = File(...),
    current_user: CurrentUserDep = Depends(require_cycle_admin),
):
    section_text = (section or "").strip()
    if not section_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="section is required")
    upload_bytes = await file.read()
    if not upload_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")
    if len(upload_bytes) > settings.document_upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"파일 크기는 {settings.document_upload_max_bytes // (1024 * 1024)}MB 이하만 업로드할 수 있습니다.",
        )
    source_name = file.filename or "guide-shot.png"
    ext = (Path(source_name).suffix or ".png").lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="이미지 파일만 업로드할 수 있습니다.")

    section_dir_name = _sanitize_path_segment(section_text, fallback="section")
    section_dir = _USER_GUIDE_SHOTS_ROOT / section_dir_name
    section_dir.mkdir(parents=True, exist_ok=True)
    label_text = (label or Path(source_name).stem or "image").strip()
    safe_label = _sanitize_path_segment(label_text, fallback="image")
    stored_name = f"{safe_label}_{current_user.id}_{int(date.today().strftime('%Y%m%d'))}{ext}"
    stored_path = section_dir / stored_name
    suffix = 1
    while stored_path.exists():
        stored_name = f"{safe_label}_{current_user.id}_{int(date.today().strftime('%Y%m%d'))}_{suffix}{ext}"
        stored_path = section_dir / stored_name
        suffix += 1
    stored_path.write_bytes(upload_bytes)
    return {
        "ok": True,
        "section": section_text,
        "label": label_text,
        "file_url": f"/user-guide-shots/file/{quote(section_dir_name)}/{quote(stored_name)}",
    }


public_router = APIRouter(prefix="/dynamic-menus", tags=["dynamic-menus"])
user_guide_shots_router = APIRouter(prefix="/user-guide-shots", tags=["user-guide-shots"])


def _check_menu_access(current_user: CurrentUserDep, menu: DynamicMenuConfig) -> None:
    user_ui = str(getattr(current_user, "ui_type", "") or "")
    if menu.target_ui_type not in {"BOTH", user_ui}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")


@public_router.get("/sidebar")
def list_sidebar_dynamic_menus(ui_type: str, db: DbDep, current_user: CurrentUserDep):
    req_ui = (ui_type or "").upper()
    if req_ui not in {"SITE", "HQ_SAFE"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ui_type must be SITE or HQ_SAFE")
    if str(getattr(current_user, "ui_type", "") or "") != req_ui:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    rows = (
        db.query(DynamicMenuConfig)
        .filter(
            DynamicMenuConfig.is_active.is_(True),
            DynamicMenuConfig.target_ui_type.in_([req_ui, "BOTH"]),
        )
        .order_by(DynamicMenuConfig.sort_order.asc(), DynamicMenuConfig.id.asc())
        .all()
    )
    return {"items": [{"id": r.id, "slug": r.slug, "title": r.title, "menu_type": r.menu_type} for r in rows]}


@public_router.get("/menu-order/{ui_type}")
def get_sidebar_menu_order(ui_type: str, db: DbDep, current_user: CurrentUserDep):
    req_ui = _normalize_ui_type(ui_type)
    if str(getattr(current_user, "ui_type", "") or "") != req_ui:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    row = db.query(UIMenuOrderConfig).filter(UIMenuOrderConfig.ui_type == req_ui).first()
    return {"ui_type": req_ui, "ordered_keys": _parse_menu_order_keys(row.ordered_keys if row else "[]")}


@user_guide_shots_router.get("/list")
def list_user_guide_shots(section: str):
    section_text = (section or "").strip()
    if not section_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="section is required")
    section_dir_name = _sanitize_path_segment(section_text, fallback="section")
    section_dir = _USER_GUIDE_SHOTS_ROOT / section_dir_name
    if not section_dir.exists():
        return {"items": []}
    files = [p for p in section_dir.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    items = [
        {
            "src": f"/user-guide-shots/file/{quote(section_dir_name)}/{quote(f.name)}",
            "label": Path(f.name).stem,
        }
        for f in files
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    ]
    return {"items": items}


@user_guide_shots_router.get("/file/{section_dir}/{file_name}")
def open_user_guide_shot_file(section_dir: str, file_name: str):
    safe_section = _sanitize_path_segment(section_dir, fallback="section")
    safe_file = Path(file_name).name
    target = _USER_GUIDE_SHOTS_ROOT / safe_section / safe_file
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    response = FileResponse(path=target, filename=safe_file)
    response.headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(safe_file)}"
    return response


@public_router.get("/{slug}")
def get_dynamic_menu_detail(slug: str, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu not found")
    _check_menu_access(current_user, menu)
    return {
        "menu": {
            "id": menu.id,
            "slug": menu.slug,
            "title": menu.title,
            "menu_type": menu.menu_type,
            "target_ui_type": menu.target_ui_type,
            "custom_config": _parse_menu_config(menu.custom_config),
        }
    }


@public_router.get("/{slug}/board-posts")
def list_dynamic_menu_board_posts(slug: str, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "BOARD":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board menu not found")
    _check_menu_access(current_user, menu)
    posts = (
        db.query(DynamicMenuBoardPost)
        .filter(DynamicMenuBoardPost.menu_id == menu.id)
        .order_by(DynamicMenuBoardPost.created_at.desc(), DynamicMenuBoardPost.id.desc())
        .all()
    )
    post_ids = [p.id for p in posts]
    comments = (
        db.query(DynamicMenuBoardComment)
        .filter(DynamicMenuBoardComment.post_id.in_(post_ids))
        .order_by(DynamicMenuBoardComment.created_at.asc(), DynamicMenuBoardComment.id.asc())
        .all()
        if post_ids
        else []
    )
    user_ids = {p.created_by_user_id for p in posts} | {c.created_by_user_id for c in comments}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    name_map = {u.id: u.name for u in users}
    comment_map: dict[int, list[dict]] = {}
    for c in comments:
        comment_map.setdefault(c.post_id, []).append(
            {"id": c.id, "body": c.body, "created_by_name": name_map.get(c.created_by_user_id), "created_at": c.created_at}
        )
    return {
        "items": [
            {
                "id": p.id,
                "title": p.title,
                "body": p.body,
                "created_by_name": name_map.get(p.created_by_user_id),
                "created_at": p.created_at,
                "comments": comment_map.get(p.id, []),
            }
            for p in posts
        ]
    }


@public_router.post("/{slug}/board-posts")
def create_dynamic_menu_board_post(slug: str, payload: dict, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "BOARD":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board menu not found")
    _check_menu_access(current_user, menu)
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    if not title or not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title and body are required")
    row = DynamicMenuBoardPost(menu_id=menu.id, title=title, body=body, created_by_user_id=current_user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@public_router.post("/{slug}/board-posts/{post_id}/comments")
def create_dynamic_menu_board_comment(slug: str, post_id: int, payload: dict, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "BOARD":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board menu not found")
    _check_menu_access(current_user, menu)
    post = db.query(DynamicMenuBoardPost).filter(DynamicMenuBoardPost.id == post_id, DynamicMenuBoardPost.menu_id == menu.id).first()
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body is required")
    row = DynamicMenuBoardComment(post_id=post_id, body=body, created_by_user_id=current_user.id)
    db.add(row)
    db.commit()
    return {"ok": True}


@public_router.get("/{slug}/table-rows")
def list_dynamic_menu_table_rows(slug: str, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "TABLE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table menu not found")
    _check_menu_access(current_user, menu)
    rows = (
        db.query(DynamicMenuTableRow)
        .filter(DynamicMenuTableRow.menu_id == menu.id)
        .order_by(DynamicMenuTableRow.created_at.desc(), DynamicMenuTableRow.id.desc())
        .all()
    )
    return {"items": [{"id": r.id, "row_data": _parse_menu_config(r.row_data), "created_at": r.created_at} for r in rows]}


@public_router.post("/{slug}/table-rows")
def create_dynamic_menu_table_row(slug: str, payload: dict, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "TABLE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table menu not found")
    _check_menu_access(current_user, menu)
    data = payload.get("row_data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="row_data must be object")
    row = DynamicMenuTableRow(menu_id=menu.id, row_data=json.dumps(data, ensure_ascii=False), created_by_user_id=current_user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@public_router.put("/{slug}/table-rows/{row_id}")
def update_dynamic_menu_table_row(slug: str, row_id: int, payload: dict, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "TABLE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table menu not found")
    _check_menu_access(current_user, menu)
    row = db.query(DynamicMenuTableRow).filter(DynamicMenuTableRow.id == row_id, DynamicMenuTableRow.menu_id == menu.id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Row not found")
    data = payload.get("row_data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="row_data must be object")
    row.row_data = json.dumps(data, ensure_ascii=False)
    db.add(row)
    db.commit()
    return {"ok": True}


@public_router.delete("/{slug}/table-rows/{row_id}")
def delete_dynamic_menu_table_row(slug: str, row_id: int, db: DbDep, current_user: CurrentUserDep):
    menu = db.query(DynamicMenuConfig).filter(DynamicMenuConfig.slug == slug, DynamicMenuConfig.is_active.is_(True)).first()
    if menu is None or menu.menu_type != "TABLE":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table menu not found")
    _check_menu_access(current_user, menu)
    row = db.query(DynamicMenuTableRow).filter(DynamicMenuTableRow.id == row_id, DynamicMenuTableRow.menu_id == menu.id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Row not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
