from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.document_settings.models import (
    ContractorDocumentBundleItem,
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
