from fastapi import APIRouter, HTTPException, status

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.opinions.models import Opinion, OpinionStatus
from app.modules.sites.models import Site
from app.schemas.opinions import OpinionCreate, OpinionUpdate


router = APIRouter(prefix="/opinions", tags=["opinions"])


def _is_opinion_admin(role: Role | str | None) -> bool:
    if role is None:
        return False
    value = role.value if isinstance(role, Role) else str(role)
    return value in {Role.HQ_SAFE_ADMIN.value, Role.SUPER_ADMIN.value}


@router.get("")
def list_opinions(
    db: DbDep,
    current_user: CurrentUserDep,
    status_filter: str | None = None,
    site_id: int | None = None,
    keyword: str | None = None,
):
    query = db.query(Opinion)

    if current_user.role == Role.SITE and current_user.site_id:
        query = query.filter(Opinion.site_id == current_user.site_id)

    if status_filter:
        query = query.filter(Opinion.status == status_filter)
    if site_id:
        query = query.filter(Opinion.site_id == site_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(Opinion.content.ilike(like))

    return query.order_by(Opinion.created_at.desc()).all()


@router.get("/{opinion_id}")
def get_opinion(opinion_id: int, db: DbDep, current_user: CurrentUserDep):
    opinion = db.query(Opinion).filter(Opinion.id == opinion_id).first()
    if not opinion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opinion not found")
    if current_user.role == Role.SITE and current_user.site_id != opinion.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    return opinion


@router.post("")
def create_opinion(
    db: DbDep,
    current_user: CurrentUserDep,
    body: OpinionCreate,
):
    site_id = body.site_id
    if current_user.role == Role.SITE and current_user.site_id:
        site_id = current_user.site_id
    if not site_id and current_user.site_id:
        site_id = current_user.site_id
    if not site_id:
        pilot_site = db.query(Site).filter(Site.site_code == "SITE002").order_by(Site.id.asc()).first()
        if pilot_site is not None:
            site_id = pilot_site.id
    if not site_id:
        first_site = db.query(Site).order_by(Site.id.asc()).first()
        if first_site is not None:
            site_id = first_site.id
    if not site_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required")

    opinion = Opinion(
        site_id=site_id,
        category=body.category,
        content=body.content,
        reporter_type=body.reporter_type,
        status=OpinionStatus.RECEIVED,
        created_by_user_id=int(current_user.id),
    )
    db.add(opinion)
    db.commit()
    db.refresh(opinion)
    return opinion


@router.put("/{opinion_id}")
def update_opinion(
    opinion_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
    body: OpinionUpdate,
):
    opinion = db.query(Opinion).filter(Opinion.id == opinion_id).first()
    if not opinion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opinion not found")

    if current_user.role == Role.SITE and current_user.site_id != opinion.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    if body.status:
        opinion.status = body.status
    if body.score_appropriateness is not None:
        opinion.score_appropriateness = body.score_appropriateness
    if body.score_actionability is not None:
        opinion.score_actionability = body.score_actionability
    if body.action_result is not None:
        opinion.action_result = body.action_result
    if body.assigned_user_id is not None:
        opinion.assigned_user_id = body.assigned_user_id

    db.commit()
    db.refresh(opinion)
    return opinion


@router.delete("/{opinion_id}")
def delete_opinion(
    opinion_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    opinion = db.query(Opinion).filter(Opinion.id == opinion_id).first()
    if opinion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opinion not found")

    if current_user.role == Role.SITE and current_user.site_id != opinion.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    is_admin = _is_opinion_admin(current_user.role)
    author_id = opinion.created_by_user_id
    is_author = author_id is not None and int(author_id) == int(current_user.id)
    if not is_admin and not is_author:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    db.delete(opinion)
    db.commit()
    return {"ok": True}

