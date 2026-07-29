from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import DbDep, get_current_user
from app.core.enums import Role
from app.modules.account_requests.models import AccountAccessRequest
from app.modules.account_requests.schemas import (
    AccountRequestCreateResponse,
    AccountRequestDecision,
    AccountRequestDecisionResponse,
    AccountRequestItem,
    ExistingAccessRequestCreate,
    PublicAccountRequestCreate,
)
from app.modules.account_requests.service import (
    APPROVER_ROLES,
    OPEN_STATUSES,
    create_request,
    decide_request,
    item_from_model,
)
from app.modules.users.models import User

router = APIRouter(prefix="/account-requests", tags=["account-requests"])


@router.post("/public", response_model=AccountRequestCreateResponse, status_code=201)
def submit_public_request(payload: PublicAccountRequestCreate, db: DbDep):
    req = create_request(db, payload=payload, applicant=None, request_type="NEW_ACCOUNT")
    return AccountRequestCreateResponse(
        request_no=req.request_no,
        status=req.status,
        message="신청이 접수되었습니다. 승인 전에는 계정이나 권한이 부여되지 않습니다.",
    )


@router.post("/me", response_model=AccountRequestCreateResponse, status_code=201)
def submit_my_request(
    payload: ExistingAccessRequestCreate,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    req = create_request(
        db,
        payload=payload,
        applicant=current_user,
        request_type=payload.request_type,
    )
    return AccountRequestCreateResponse(
        request_no=req.request_no,
        status=req.status,
        message="권한 변경 신청이 접수되었습니다.",
    )


@router.get("/me", response_model=list[AccountRequestItem])
def list_my_requests(db: DbDep, current_user: User = Depends(get_current_user)):
    rows = (
        db.query(AccountAccessRequest)
        .filter(AccountAccessRequest.applicant_user_id == current_user.id)
        .order_by(AccountAccessRequest.id.desc())
        .all()
    )
    return [item_from_model(row) for row in rows]


def _assert_approver(current_user: User) -> None:
    if current_user.role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="APPROVER_REQUIRED")


@router.get("/admin", response_model=list[AccountRequestItem])
def list_admin_requests(
    db: DbDep,
    current_user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
):
    _assert_approver(current_user)
    query = db.query(AccountAccessRequest)
    if status_filter:
        query = query.filter(AccountAccessRequest.status == status_filter.strip().upper())
    return [item_from_model(row) for row in query.order_by(AccountAccessRequest.id.desc()).all()]


@router.patch("/admin/{request_id}", response_model=AccountRequestDecisionResponse)
def handle_admin_request(
    request_id: int,
    payload: AccountRequestDecision,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    _assert_approver(current_user)
    req = db.query(AccountAccessRequest).filter(AccountAccessRequest.id == request_id).first()
    if req is None:
        raise HTTPException(status_code=404, detail="REQUEST_NOT_FOUND")
    req, temporary_password, temporary_expires = decide_request(
        db, req=req, payload=payload, actor=current_user
    )
    target = db.query(User).filter(User.id == req.existing_user_id).first() if req.existing_user_id else None
    return AccountRequestDecisionResponse(
        item=item_from_model(req),
        temporary_login_id=target.login_id if temporary_password and target else None,
        temporary_password=temporary_password,
        temporary_password_expires_at=temporary_expires,
    )
