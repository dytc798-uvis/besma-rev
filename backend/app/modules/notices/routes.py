from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.core.auth import DbDep
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.notices.models import Notice, NoticeComment
from app.modules.users.models import User

router = APIRouter(prefix="/notices", tags=["notices"])


class NoticeCreateBody(BaseModel):
    title: str
    body: str


class NoticeCommentCreateBody(BaseModel):
    body: str


def _serialize_notice_item(row: Notice, user_name_map: dict[int, str]) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "created_by_user_id": row.created_by_user_id,
        "created_by_name": user_name_map.get(row.created_by_user_id),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("")
def list_notices(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(default=30, ge=1, le=100),
):
    rows = db.query(Notice).order_by(Notice.created_at.desc(), Notice.id.desc()).limit(limit).all()
    user_ids = {int(r.created_by_user_id) for r in rows}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all() if user_ids else []
    user_name_map = {u.id: u.name for u in users}
    return {"items": [_serialize_notice_item(r, user_name_map) for r in rows]}


@router.get("/latest")
def list_latest_notice_titles(
    db: DbDep,
    current_user: CurrentUserDep,
    limit: int = Query(default=2, ge=1, le=5),
):
    rows = db.query(Notice).order_by(Notice.created_at.desc(), Notice.id.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "created_at": r.created_at,
            }
            for r in rows
        ]
    }


@router.post("")
def create_notice(
    body: NoticeCreateBody,
    db: DbDep,
    current_user: CurrentUserDep,
):
    if current_user.role not in {
        Role.HQ_SAFE.value,
        Role.HQ_SAFE_ADMIN.value,
        Role.SUPER_ADMIN.value,
        Role.SITE.value,
        Role.HQ_OTHER.value,
    }:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    title = (body.title or "").strip()
    content = (body.body or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title is required")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body is required")
    notice = Notice(title=title, body=content, created_by_user_id=current_user.id)
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return {"id": notice.id}


@router.get("/{notice_id}")
def get_notice_detail(
    notice_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    comments = (
        db.query(NoticeComment)
        .filter(NoticeComment.notice_id == notice_id)
        .order_by(NoticeComment.created_at.asc(), NoticeComment.id.asc())
        .all()
    )
    user_ids = {notice.created_by_user_id} | {int(c.created_by_user_id) for c in comments}
    users = db.query(User).filter(User.id.in_(list(user_ids))).all()
    user_name_map = {u.id: u.name for u in users}
    return {
        "notice": _serialize_notice_item(notice, user_name_map),
        "comments": [
            {
                "id": c.id,
                "notice_id": c.notice_id,
                "body": c.body,
                "created_by_user_id": c.created_by_user_id,
                "created_by_name": user_name_map.get(c.created_by_user_id),
                "created_at": c.created_at,
            }
            for c in comments
        ],
    }


@router.post("/{notice_id}/comments")
def create_notice_comment(
    notice_id: int,
    body: NoticeCommentCreateBody,
    db: DbDep,
    current_user: CurrentUserDep,
):
    notice = db.query(Notice).filter(Notice.id == notice_id).first()
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    text = (body.body or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="comment body is required")
    comment = NoticeComment(
        notice_id=notice_id,
        body=text,
        created_by_user_id=current_user.id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id}
