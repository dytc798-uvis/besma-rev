from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import case

from app.core.auth import DbDep
from app.core.permissions import CurrentUserDep, Role, require_roles
from app.modules.sites.models import Site
from app.modules.sites.ordering import site_list_priority_order
from app.modules.sites.service import ImportResult, import_sites_from_workbook, upsert_site_from_row
from app.modules.documents.models import Document
from app.modules.workers.models import Employment, Person
from app.schemas.sites import (
    SiteCreateRequest,
    SiteImportResult,
    SiteManagementSummaryResponse,
    SiteManagerResolved,
    SiteResponse,
    SiteSearchResponse,
    SiteUpdateRequest,
    SiteWorkerResponse,
)


router = APIRouter(prefix="/sites", tags=["sites"])


POSITION_ROLE_LABELS: dict[str, str] = {
    "9": "현장소장",
    "10": "공무대리",
    "11": "공무과장",
    "12": "공무차장",
    "13": "공무부장",
    "22": "안전관리자",
}


RequireSiteAdmin = Annotated[
    CurrentUserDep,
    Depends(require_roles(Role.HQ_SAFE, Role.HQ_OTHER)),
]


def _uploaded_document_site_ids(db: DbDep) -> set[int]:
    rows = (
        db.query(Document.site_id)
        .filter(Document.site_id.isnot(None), Document.file_path.isnot(None))
        .group_by(Document.site_id)
        .all()
    )
    return {int(site_id) for (site_id,) in rows if site_id is not None}


def _preferred_site(rows: list[Site], uploaded_site_ids: set[int]) -> Site | None:
    if not rows:
        return None
    return sorted(
        rows,
        key=lambda s: (
            0 if s.id in uploaded_site_ids else 1,
            0 if (s.address or "").strip() else 1,
            0 if s.site_code == "SITE002" else 1,
            s.id,
        ),
    )[0]


@router.get("", response_model=list[SiteResponse])
def list_sites(db: DbDep, current_user: CurrentUserDep):
    query = db.query(Site)
    if current_user.role == Role.SITE:
        if current_user.site_id:
            query = query.filter(Site.id == current_user.site_id)
        else:
            query = query.filter(False)
    rows = query.order_by(site_list_priority_order(), Site.id.asc()).all()
    if current_user.role == Role.SITE:
        return rows

    uploaded_site_ids = _uploaded_document_site_ids(db)

    # 운영 고정 노출:
    # 1) C18(실업로드 대상) 1개만 유지
    # 2) 그 외 현장은 샘플 1개만 유지
    c18_candidates = [s for s in rows if ("C18BL" in (s.site_name or "")) or ("청라C18" in (s.site_name or ""))]
    chosen_c18 = _preferred_site(c18_candidates, uploaded_site_ids)

    non_c18 = [s for s in rows if chosen_c18 is None or s.id != chosen_c18.id]
    # 나머지는 샘플 1개만 노출
    sample_other = next((s for s in non_c18 if (s.site_name or "") and ("C18BL" not in s.site_name and "청라C18" not in s.site_name)), None)

    filtered: list[Site] = []
    if chosen_c18 is not None:
        filtered.append(chosen_c18)
    if sample_other is not None:
        filtered.append(sample_other)
    return filtered or rows[:1]


@router.get("/search", response_model=list[SiteSearchResponse])
def search_sites(db: DbDep, current_user: CurrentUserDep):
    rows = (
        db.query(Site)
        .filter(Site.address.isnot(None), Site.address != "")
        .order_by(site_list_priority_order(), Site.id.asc())
        .all()
    )
    if current_user.role == Role.SITE:
        visible = rows
    else:
        uploaded_site_ids = _uploaded_document_site_ids(db)
        c18_rows = [s for s in rows if ("C18BL" in (s.site_name or "")) or ("청라C18" in (s.site_name or ""))]
        chosen_c18 = _preferred_site(c18_rows, uploaded_site_ids)
        sample_other = next((s for s in rows if chosen_c18 is None or (s.id != chosen_c18.id and "C18BL" not in (s.site_name or "") and "청라C18" not in (s.site_name or ""))), None)
        visible = [r for r in [chosen_c18, sample_other] if r is not None] or rows[:1]
    return [
        SiteSearchResponse(
            id=site.id,
            name=site.site_name,
            address=site.address,
        )
        for site in visible
    ]


@router.get("/{site_id}", response_model=SiteResponse)
def get_site(site_id: int, db: DbDep, current_user: CurrentUserDep):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    if current_user.role == Role.SITE and current_user.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return site


@router.get("/{site_id}/workers", response_model=list[SiteWorkerResponse])
def list_site_workers(
    site_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    target_date: date_type = Query(default=None),
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    td = target_date or date_type.today()
    rows = (
        db.query(Employment, Person)
        .join(Person, Person.id == Employment.person_id)
        .filter(
            Employment.is_active.is_(True),
            Employment.site_code == site.site_code,
            (Employment.termination_date.is_(None) | (Employment.termination_date >= td)),
            (Employment.hire_date.is_(None) | (Employment.hire_date <= td)),
        )
        .all()
    )
    return [
        SiteWorkerResponse(
            person_id=emp.person_id,
            employment_id=emp.id,
            name=person.name,
            department_name=emp.department_name,
            position_name=emp.position_name,
            site_code=emp.site_code,
        )
        for emp, person in rows
    ]


def _resolve_manager_by_name(
    db: DbDep,
    *,
    source_name: str | None,
    site_code: str,
    manager_type: str,
) -> SiteManagerResolved:
    if not source_name or not source_name.strip():
        return SiteManagerResolved(
            manager_type=manager_type,
            source_name=source_name,
            resolve_status="UNLINKED",
        )

    resolved_name = source_name.strip()
    row = (
        db.query(Person, Employment)
        .join(Employment, Employment.person_id == Person.id)
        .filter(Person.name == resolved_name)
        .order_by(
            case((Employment.site_code == site_code, 0), else_=1),
            case((Employment.is_active.is_(True), 0), else_=1),
            Employment.id.desc(),
        )
        .first()
    )
    if row is None:
        return SiteManagerResolved(
            manager_type=manager_type,
            source_name=resolved_name,
            resolve_status="UNMATCHED",
        )

    person, emp = row
    position_code = str(emp.position_code).strip() if emp.position_code is not None else None
    return SiteManagerResolved(
        manager_type=manager_type,
        source_name=resolved_name,
        person_id=person.id,
        employment_id=emp.id,
        position_code=position_code,
        role_label=POSITION_ROLE_LABELS.get(position_code) if position_code else None,
        resolve_status="MATCHED",
    )


def _resolve_safety_manager(
    db: DbDep,
    *,
    site_code: str,
) -> SiteManagerResolved:
    row = (
        db.query(Person, Employment)
        .join(Employment, Employment.person_id == Person.id)
        .filter(
            Employment.site_code == site_code,
            Employment.position_code == "22",
            Employment.is_active.is_(True),
        )
        .order_by(Employment.id.desc())
        .first()
    )
    if row is None:
        return SiteManagerResolved(
            manager_type="safety_manager",
            resolve_status="UNMATCHED",
        )
    person, emp = row
    return SiteManagerResolved(
        manager_type="safety_manager",
        source_name=person.name,
        person_id=person.id,
        employment_id=emp.id,
        position_code="22",
        role_label=POSITION_ROLE_LABELS["22"],
        resolve_status="MATCHED",
    )


@router.get("/{site_id}/management-summary", response_model=SiteManagementSummaryResponse)
def get_site_management_summary(
    site_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    if current_user.role == Role.SITE and current_user.site_id != site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    project_manager = _resolve_manager_by_name(
        db,
        source_name=site.project_manager,
        site_code=site.site_code,
        manager_type="project_manager",
    )
    site_manager = _resolve_manager_by_name(
        db,
        source_name=site.site_manager,
        site_code=site.site_code,
        manager_type="site_manager",
    )
    safety_manager = _resolve_safety_manager(db, site_code=site.site_code)

    return SiteManagementSummaryResponse(
        site_id=site.id,
        site_code=site.site_code,
        project_manager=project_manager,
        site_manager=site_manager,
        safety_manager=safety_manager,
    )


@router.post("", response_model=SiteResponse, status_code=status.HTTP_201_CREATED)
def create_site(
    payload: SiteCreateRequest,
    db: DbDep,
    current_user: RequireSiteAdmin,
):
    existing = db.query(Site).filter(Site.site_code == payload.site_code).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_code already exists")

    data = payload.model_dump()
    # ERP 업로드와 동일한 정제 규칙을 재사용하기 위해 내부 upsert 함수를 활용
    site, created = upsert_site_from_row(db, {**data}, current_user)
    if not created:
        # 이 경우는 이론상 발생하지 않지만 방어적으로 처리
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Failed to create site")
    db.commit()
    db.refresh(site)
    return site


@router.patch("/{site_id}", response_model=SiteResponse)
def update_site(
    site_id: int,
    payload: SiteUpdateRequest,
    db: DbDep,
    current_user: RequireSiteAdmin,
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(site, k, v)
    site.updated_by_user_id = current_user.id
    db.add(site)
    db.commit()
    db.refresh(site)
    return site


@router.post("/import", response_model=SiteImportResult)
async def import_sites(
    db: DbDep,
    current_user: RequireSiteAdmin,
    file: UploadFile = File(...),
):
    result: ImportResult = await import_sites_from_workbook(db, file, current_user)
    return SiteImportResult(
        total_rows=result.total_rows,
        created_rows=result.created_rows,
        updated_rows=result.updated_rows,
        failed_rows=result.failed_rows,
        errors=[{"row_index": e["row_index"], "error": e["error"]} for e in result.errors],
        batch_id=result.batch.id,
        original_filename=result.batch.original_filename,
        stored_path=result.batch.stored_path,
    )
