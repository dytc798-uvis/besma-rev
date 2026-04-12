from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import DbDep, get_current_user, oauth2_scheme_optional
from app.core.enums import Role
from app.core.permissions import CurrentUserDep
from app.modules.risk_library.models import DailyWorkPlanItem
from app.modules.risk_library.service import (
    adopt_risks_for_plan_item_by_revision_ids,
    assemble_daily_work_plan_document,
    confirm_daily_work_plan,
    create_reassignment_distribution,
    create_daily_work_plan,
    create_daily_work_plan_item,
    create_worker_feedback,
    distribute_daily_work_plan,
    get_assembled_document_for_day,
    get_daily_work_plan,
    get_distribution_detail,
    get_worker_safety_record,
    get_worker_distribution_detail,
    list_plan_confirmations,
    list_recent_distributions_for_site,
    list_distribution_workers,
    list_feedbacks_for_distribution,
    list_risk_library_entries,
    list_risk_refs_for_plan_item,
    list_worker_visible_distributions,
    hq_finalize_risk_ref,
    ping_site_admin_presence,
    promote_feedback_candidate,
    review_worker_feedback,
    run_recommendation_for_plan_item,
    site_approve_risk_ref,
    start_distribution_tbm,
    sign_worker_daily_work_plan,
    sign_worker_daily_work_plan_end,
)
from app.modules.risk_library.models import DailyWorkPlanItemRiskRef
from app.modules.sites.models import Site
from app.schemas.daily_work_plans import (
    AdoptRisksRequest,
    AdoptRisksResponse,
    AssembleDailyWorkPlanDocumentRequest,
    AssembleDailyWorkPlanDocumentResponse,
    GetAssembledDailyWorkPlanDocumentResponse,
    DailyWorkPlanConfirmResponse,
    DailyWorkPlanConfirmationResponse,
    DailyWorkPlanCreateRequest,
    DailyWorkPlanItemCreateRequest,
    DailyWorkPlanItemRiskRefResponse,
    DailyWorkPlanItemResponse,
    DailyWorkPlanResponse,
    RecommendRisksRequest,
    RecommendRisksResponse,
    DailyWorkPlanDistributeRequest,
    DailyWorkPlanDistributionDetailResponse,
    DailyWorkPlanDistributionResponse,
    DistributionReassignWorkersRequest,
    DistributionReassignWorkersResponse,
    FeedbackPromoteCandidateResponse,
    FeedbackReviewRequest,
    FeedbackReviewResponse,
    SiteAdminPresencePingRequest,
    SiteAdminPresencePingResponse,
    StartTbmDistributionResponse,
    WorkerFeedbackCreateRequest,
    WorkerFeedbackResponse,
    WorkerMyDailyWorkPlanDetailResponse,
    WorkerMyDailyWorkPlanListItem,
    WorkerSafetyRecordResponse,
    WorkerSignEndDailyWorkPlanRequest,
    WorkerSignDailyWorkPlanRequest,
    WorkerSignDailyWorkPlanResponse,
)
from app.schemas.risk_library_read import RiskLibraryReadResponse


router = APIRouter(tags=["daily-work-plans"])

RISK_LIBRARY_ALLOWED_ROLES = {
    Role.SUPER_ADMIN.value,
    Role.HQ_SAFE_ADMIN.value,
    Role.HQ_SAFE.value,
    Role.SITE.value,
    Role.HQ_OTHER.value,
}


def _get_optional_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    db: DbDep,
):
    if not token:
        return None
    return get_current_user(token=token, db=db)


def _resolve_worker_person_id(
    current_user,
) -> int | None:
    if current_user is None:
        return None
    person_id = getattr(current_user, "person_id", None)
    if person_id is None:
        return None
    return int(person_id)


def _assert_risk_library_access(current_user) -> None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    if role_value not in RISK_LIBRARY_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Risk library access is allowed for HQ/SITE users only",
        )


def _resolve_role_value(current_user) -> str | None:
    role_value = getattr(current_user, "role", None)
    if hasattr(role_value, "value"):
        role_value = role_value.value
    return role_value


def _get_risk_ref_or_404(db, ref_id: int) -> DailyWorkPlanItemRiskRef:
    ref = db.query(DailyWorkPlanItemRiskRef).filter(DailyWorkPlanItemRiskRef.id == ref_id).first()
    if ref is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk ref not found")
    return ref


@router.get("/risk-library", response_model=RiskLibraryReadResponse)
def get_risk_library(
    db: DbDep,
    current_user: CurrentUserDep,
    keyword: str | None = None,
    work_category: str | None = None,
    process: str | None = None,
    risk_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    _assert_risk_library_access(current_user)
    result = list_risk_library_entries(
        db,
        keyword=keyword,
        work_category=work_category,
        process=process,
        risk_type=risk_type,
        limit=min(max(limit, 1), 1000),
        offset=max(offset, 0),
    )
    return RiskLibraryReadResponse(**result)


@router.post(
    "/daily-work-plans",
    response_model=DailyWorkPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    payload: DailyWorkPlanCreateRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    site = db.query(Site).filter(Site.id == payload.site_id).first()
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")

    plan = create_daily_work_plan(
        db,
        site_id=payload.site_id,
        work_date=payload.work_date,
        author_user_id=current_user.id,
    )
    return plan


@router.get("/daily-work-plans/{plan_id:int}", response_model=DailyWorkPlanResponse)
def get_plan(plan_id: int, db: DbDep, current_user: CurrentUserDep):
    plan = get_daily_work_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
    return plan


@router.post(
    "/daily-work-plans/{plan_id:int}/items",
    response_model=DailyWorkPlanItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_plan_item(
    plan_id: int,
    payload: DailyWorkPlanItemCreateRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    plan = get_daily_work_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
    return create_daily_work_plan_item(
        db,
        plan_id=plan_id,
        work_name=payload.work_name,
        work_description=payload.work_description,
        team_label=payload.team_label,
        leader_person_id=payload.leader_person_id,
    )


@router.post(
    "/daily-work-plan-items/{item_id:int}/recommend-risks",
    response_model=RecommendRisksResponse,
)
def recommend_risks(
    item_id: int,
    payload: RecommendRisksRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = run_recommendation_for_plan_item(
            db,
            plan_item_id=item_id,
            top_n=payload.top_n,
        )
    except ValueError as exc:
        if str(exc) == "plan_item_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DailyWorkPlanItem not found",
            )
        raise
    return RecommendRisksResponse(
        plan_item_id=item_id,
        recommended_count=result["recommended_count"],
        upserted_count=result["upserted_count"],
    )


@router.get(
    "/daily-work-plan-items/{item_id:int}/risk-refs",
)
def get_plan_item_risk_refs(item_id: int, db: DbDep, current_user: CurrentUserDep):
    item = db.query(DailyWorkPlanItem).filter(DailyWorkPlanItem.id == item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlanItem not found")
    return list_risk_refs_for_plan_item(db, plan_item_id=item_id)


@router.post(
    "/daily-work-plan-items/{item_id:int}/adopt-risks",
    response_model=AdoptRisksResponse,
)
def adopt_risks(
    item_id: int,
    payload: AdoptRisksRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = adopt_risks_for_plan_item_by_revision_ids(
            db,
            plan_item_id=item_id,
            risk_revision_ids=payload.risk_revision_ids,
        )
    except ValueError as exc:
        if str(exc) == "plan_item_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DailyWorkPlanItem not found",
            )
        raise
    return AdoptRisksResponse(
        plan_item_id=item_id,
        requested_count=result["requested_count"],
        adopted_count=result["adopted_count"],
    )


@router.post(
    "/daily-work-plan-item-risk-refs/{ref_id:int}/site-approve",
    response_model=DailyWorkPlanItemRiskRefResponse,
)
def approve_risk_ref_by_site(
    ref_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    ref = _get_risk_ref_or_404(db, ref_id)
    role_value = _resolve_role_value(current_user)
    if role_value != Role.SITE.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SITE approval is allowed for site users only")
    item = db.query(DailyWorkPlanItem).filter(DailyWorkPlanItem.id == ref.plan_item_id).first()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlanItem not found")
    plan = get_daily_work_plan(db, item.plan_id)
    if plan is None or plan.site_id != current_user.site_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")
    try:
        result = site_approve_risk_ref(db, ref_id=ref_id, approved_by_user_id=current_user.id)
    except ValueError as exc:
        if str(exc) == "risk_ref_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk ref not found")
        if str(exc) == "risk_ref_not_selected":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected adopted risk only can be approved")
        raise
    return DailyWorkPlanItemRiskRefResponse(**result)


@router.post(
    "/daily-work-plan-item-risk-refs/{ref_id:int}/hq-final-approve",
    response_model=DailyWorkPlanItemRiskRefResponse,
)
def finalize_risk_ref_by_hq(
    ref_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    role_value = _resolve_role_value(current_user)
    if role_value not in {Role.HQ_SAFE.value, Role.HQ_SAFE_ADMIN.value, Role.SUPER_ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="HQ final approval is allowed for HQ users only")
    _get_risk_ref_or_404(db, ref_id)
    try:
        result = hq_finalize_risk_ref(db, ref_id=ref_id, approved_by_user_id=current_user.id)
    except ValueError as exc:
        if str(exc) == "risk_ref_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Risk ref not found")
        if str(exc) == "risk_ref_not_selected":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected adopted risk only can be approved")
        if str(exc) == "site_approval_required":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SITE approval is required before HQ final approval")
        raise
    return DailyWorkPlanItemRiskRefResponse(**result)


@router.post("/daily-work-plans/{plan_id:int}/confirm", response_model=DailyWorkPlanConfirmResponse)
def confirm_plan(plan_id: int, db: DbDep, current_user: CurrentUserDep):
    plan = get_daily_work_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
    confirmation, created = confirm_daily_work_plan(
        db,
        plan_id=plan_id,
        confirmed_by_user_id=current_user.id,
    )
    return DailyWorkPlanConfirmResponse(
        plan_id=plan_id,
        confirmation_id=confirmation.id,
        created=created,
    )


@router.get(
    "/daily-work-plans/{plan_id:int}/confirmations",
    response_model=list[DailyWorkPlanConfirmationResponse],
)
def get_plan_confirmations(plan_id: int, db: DbDep, current_user: CurrentUserDep):
    plan = get_daily_work_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
    return list_plan_confirmations(db, plan_id=plan_id)


@router.post(
    "/daily-work-plans/assemble-document",
    response_model=AssembleDailyWorkPlanDocumentResponse,
)
def assemble_work_plan_document(
    payload: AssembleDailyWorkPlanDocumentRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        assembled = assemble_daily_work_plan_document(
            db,
            site_id=payload.site_id,
            work_date=payload.work_date,
            assembled_by_user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "daily_work_plan_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DailyWorkPlan not found for site/work_date",
            )
        raise
    return AssembleDailyWorkPlanDocumentResponse(**assembled)


@router.get(
    "/daily-work-plans/assembled-document",
    response_model=GetAssembledDailyWorkPlanDocumentResponse,
)
def get_assembled_work_plan_document(
    site_id: int,
    work_date: date,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        assembled = get_assembled_document_for_day(
            db,
            site_id=site_id,
            work_date=work_date,
        )
    except ValueError as exc:
        if str(exc) == "assembled_document_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assembled document not found for site/work_date",
            )
        raise
    return GetAssembledDailyWorkPlanDocumentResponse(**assembled)


@router.post(
    "/daily-work-plans/distributions",
    response_model=DailyWorkPlanDistributionResponse,
    status_code=status.HTTP_201_CREATED,
)
def distribute_plan(
    payload: DailyWorkPlanDistributeRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = distribute_daily_work_plan(
            db,
            plan_id=payload.plan_id,
            target_date=payload.target_date,
            visible_from=payload.visible_from,
            distributed_by_user_id=current_user.id,
            person_ids=payload.person_ids,
        )
    except ValueError as exc:
        if str(exc) == "daily_work_plan_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
        if str(exc) == "site_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
        raise
    return DailyWorkPlanDistributionResponse(**result)


@router.get(
    "/daily-work-plans/distributions",
    response_model=list[DailyWorkPlanDistributionResponse],
)
def list_recent_distributions(
    db: DbDep,
    current_user: CurrentUserDep,
    site_id: int | None = None,
    limit: int = 10,
):
    resolved_site_id = current_user.site_id if current_user.site_id else site_id
    if not resolved_site_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="site_id is required")
    items = list_recent_distributions_for_site(
        db,
        site_id=resolved_site_id,
        limit=min(max(limit, 1), 20),
    )
    return [DailyWorkPlanDistributionResponse(**item) for item in items]


@router.get(
    "/daily-work-plans/distributions/{distribution_id:int}",
    response_model=DailyWorkPlanDistributionDetailResponse,
)
def get_distribution(
    distribution_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    distribution = get_distribution_detail(db, distribution_id=distribution_id)
    if distribution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found")
    workers = list_distribution_workers(db, distribution_id=distribution_id)
    return DailyWorkPlanDistributionDetailResponse(
        id=distribution.id,
        plan_id=distribution.plan_id,
        site_id=distribution.site_id,
        target_date=distribution.target_date,
        visible_from=distribution.visible_from,
        distributed_by_user_id=distribution.distributed_by_user_id,
        distributed_at=distribution.distributed_at,
        status=distribution.status,
        tbm_started_at=distribution.tbm_started_at,
        tbm_started_by_user_id=distribution.tbm_started_by_user_id,
        parent_distribution_id=distribution.parent_distribution_id,
        is_reassignment=distribution.is_reassignment,
        reassignment_reason=distribution.reassignment_reason,
        reassigned_by_user_id=distribution.reassigned_by_user_id,
        reassigned_at=distribution.reassigned_at,
        is_tbm_active=distribution.tbm_started_at is not None,
        workers=workers,
    )


@router.get(
    "/daily-work-plans/distributions/{distribution_id:int}/feedbacks",
    response_model=list[WorkerFeedbackResponse],
)
def get_distribution_feedbacks(
    distribution_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    distribution = get_distribution_detail(db, distribution_id=distribution_id)
    if distribution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found")
    return [WorkerFeedbackResponse(**row) for row in list_feedbacks_for_distribution(db, distribution_id=distribution_id)]


@router.post(
    "/daily-work-plans/distributions/{distribution_id:int}/reassign-workers",
    response_model=DistributionReassignWorkersResponse,
)
def reassign_distribution_workers(
    distribution_id: int,
    payload: DistributionReassignWorkersRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = create_reassignment_distribution(
            db,
            distribution_id=distribution_id,
            person_ids=payload.person_ids,
            new_work_name=payload.new_work_name,
            new_work_description=payload.new_work_description,
            team_label=payload.team_label,
            selected_risk_revision_ids=payload.selected_risk_revision_ids,
            reason=payload.reason,
            reassigned_by_user_id=current_user.id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "distribution_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found")
        if code == "daily_work_plan_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
        if code in {"person_ids_required", "distribution_workers_not_found"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=code)
        raise
    return DistributionReassignWorkersResponse(**result)


@router.post(
    "/daily-work-plans/distributions/{distribution_id:int}/start-tbm",
    response_model=StartTbmDistributionResponse,
)
def start_tbm_for_distribution(
    distribution_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = start_distribution_tbm(
            db,
            distribution_id=distribution_id,
            started_by_user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "distribution_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found")
        raise
    return StartTbmDistributionResponse(**result)


@router.post(
    "/daily-work-plans/admin-presence/ping",
    response_model=SiteAdminPresencePingResponse,
)
def ping_admin_presence(
    payload: SiteAdminPresencePingRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        presence = ping_site_admin_presence(
            db,
            user_id=current_user.id,
            site_id=payload.site_id,
            lat=payload.lat,
            lng=payload.lng,
        )
    except ValueError as exc:
        if str(exc) == "user_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if str(exc) == "user_not_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        raise
    return SiteAdminPresencePingResponse(
        site_id=presence.site_id,
        user_id=presence.user_id,
        last_seen_at=presence.last_seen_at,
    )


@router.get(
    "/worker/my-daily-work-plans",
    response_model=list[WorkerMyDailyWorkPlanListItem],
)
def list_my_daily_work_plans(
    db: DbDep,
    access_token: str | None = None,
    current_user=Depends(_get_optional_current_user),
):
    person_id = _resolve_worker_person_id(current_user)
    site_id = getattr(current_user, "site_id", None) if person_id is not None else None
    if not access_token and person_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker login or access_token is required",
        )
    rows = list_worker_visible_distributions(
        db,
        access_token=access_token,
        person_id=person_id,
        site_id=site_id,
    )
    return [WorkerMyDailyWorkPlanListItem(**row) for row in rows]


@router.get(
    "/worker/my-daily-work-plans/{distribution_id:int}",
    response_model=WorkerMyDailyWorkPlanDetailResponse,
)
def get_my_daily_work_plan_detail(
    distribution_id: int,
    db: DbDep,
    access_token: str | None = None,
    current_user=Depends(_get_optional_current_user),
):
    person_id = _resolve_worker_person_id(current_user)
    site_id = getattr(current_user, "site_id", None) if person_id is not None else None
    if not access_token and person_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker login or access_token is required",
        )
    try:
        detail = get_worker_distribution_detail(
            db,
            distribution_id=distribution_id,
            access_token=access_token,
            person_id=person_id,
            site_id=site_id,
        )
    except ValueError as exc:
        if str(exc) == "distribution_worker_not_found":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid distribution/token")
        if str(exc) == "distribution_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found")
        if str(exc) == "distribution_not_visible_yet":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Distribution not visible yet")
        if str(exc) == "daily_work_plan_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DailyWorkPlan not found")
        raise
    return WorkerMyDailyWorkPlanDetailResponse(**detail)


@router.post(
    "/worker/my-daily-work-plans/{distribution_id:int}/feedback",
    response_model=WorkerFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_feedback(
    distribution_id: int,
    payload: WorkerFeedbackCreateRequest,
    db: DbDep,
    current_user=Depends(_get_optional_current_user),
):
    person_id = _resolve_worker_person_id(current_user)
    if not payload.access_token and person_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker login or access_token is required",
        )
    try:
        result = create_worker_feedback(
            db,
            distribution_id=distribution_id,
            access_token=payload.access_token,
            person_id=person_id,
            feedback_type=payload.feedback_type,
            content=payload.content,
            plan_item_id=payload.plan_item_id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "distribution_worker_not_found":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid distribution/token")
        if code == "distribution_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Distribution not found")
        if code == "plan_item_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan item not found")
        raise
    return WorkerFeedbackResponse(**result)


@router.post("/feedbacks/{feedback_id:int}/review", response_model=FeedbackReviewResponse)
def review_feedback(
    feedback_id: int,
    payload: FeedbackReviewRequest,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = review_worker_feedback(
            db,
            feedback_id=feedback_id,
            status=payload.status,
            review_note=payload.review_note,
            reviewed_by_user_id=current_user.id,
        )
    except ValueError as exc:
        code = str(exc)
        if code == "feedback_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
        if code == "invalid_feedback_status":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid feedback status")
        raise
    return FeedbackReviewResponse(**result)


@router.post(
    "/feedbacks/{feedback_id:int}/promote-candidate",
    response_model=FeedbackPromoteCandidateResponse,
)
def promote_feedback(
    feedback_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        result = promote_feedback_candidate(
            db,
            feedback_id=feedback_id,
            approved_by_user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "feedback_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
        raise
    return FeedbackPromoteCandidateResponse(**result)


@router.post(
    "/worker/my-daily-work-plans/{distribution_id:int}/sign",
    response_model=WorkerSignDailyWorkPlanResponse,
)
def sign_my_daily_work_plan(
    distribution_id: int,
    payload: WorkerSignDailyWorkPlanRequest,
    db: DbDep,
    current_user=Depends(_get_optional_current_user),
):
    person_id = _resolve_worker_person_id(current_user)
    if not payload.access_token and person_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker login or access_token is required",
        )
    try:
        result = sign_worker_daily_work_plan(
            db,
            distribution_id=distribution_id,
            access_token=payload.access_token,
            person_id=person_id,
            signature_data=payload.signature_data,
            signature_mime=payload.signature_mime,
            lat=payload.lat,
            lng=payload.lng,
        )
    except ValueError as exc:
        code = str(exc)
        detail_message = code
        if code == "tbm_not_started":
            detail_message = "아직 TBM이 시작되지 않았습니다. 관리자 안내 후 서명하세요."
        elif code == "worker_out_of_site_radius":
            detail_message = "관리자가 있는 TBM장소로 이동하여 서명하세요."
        if code in {
            "distribution_worker_not_found",
            "distribution_not_visible_yet",
            "already_signed",
            "already_end_signed",
            "start_signature_required",
            "tbm_not_started",
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_message)
        if code in {
            "invalid_signature_mime",
            "invalid_signature_prefix",
            "invalid_signature_base64",
            "signature_too_small",
            "signature_too_large",
            "site_location_not_configured",
            "invalid_end_status",
        }:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail_message)
        if code in {"worker_out_of_site_radius", "active_admin_presence_not_found"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_message)
        if code in {"distribution_not_found", "site_not_found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail_message)
        raise
    return WorkerSignDailyWorkPlanResponse(**result)


@router.post(
    "/worker/my-daily-work-plans/{distribution_id:int}/sign-start",
    response_model=WorkerSignDailyWorkPlanResponse,
)
def sign_my_daily_work_plan_start(
    distribution_id: int,
    payload: WorkerSignDailyWorkPlanRequest,
    db: DbDep,
    current_user=Depends(_get_optional_current_user),
):
    return sign_my_daily_work_plan(
        distribution_id=distribution_id,
        payload=payload,
        current_user=current_user,
        db=db,
    )


@router.post(
    "/worker/my-daily-work-plans/{distribution_id:int}/sign-end",
    response_model=WorkerSignDailyWorkPlanResponse,
)
def sign_my_daily_work_plan_end(
    distribution_id: int,
    payload: WorkerSignEndDailyWorkPlanRequest,
    db: DbDep,
    current_user=Depends(_get_optional_current_user),
):
    person_id = _resolve_worker_person_id(current_user)
    if not payload.access_token and person_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Worker login or access_token is required",
        )
    try:
        result = sign_worker_daily_work_plan_end(
            db,
            distribution_id=distribution_id,
            access_token=payload.access_token,
            person_id=person_id,
            end_status=payload.end_status,
            signature_data=payload.signature_data,
            signature_mime=payload.signature_mime,
            lat=payload.lat,
            lng=payload.lng,
        )
    except ValueError as exc:
        code = str(exc)
        detail_message = code
        if code == "tbm_not_started":
            detail_message = "아직 TBM이 시작되지 않았습니다. 관리자 안내 후 서명하세요."
        elif code == "worker_out_of_site_radius":
            detail_message = "관리자가 있는 TBM장소로 이동하여 서명하세요."
        if code in {
            "distribution_worker_not_found",
            "distribution_not_visible_yet",
            "already_end_signed",
            "start_signature_required",
            "tbm_not_started",
        }:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_message)
        if code in {
            "invalid_signature_mime",
            "invalid_signature_prefix",
            "invalid_signature_base64",
            "signature_too_small",
            "signature_too_large",
            "site_location_not_configured",
            "invalid_end_status",
        }:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail_message)
        if code in {"worker_out_of_site_radius", "active_admin_presence_not_found"}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail_message)
        if code in {"distribution_not_found", "site_not_found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail_message)
        raise
    return WorkerSignDailyWorkPlanResponse(**result)


@router.get(
    "/hq-safe/workers/{person_id:int}/safety-record",
    response_model=WorkerSafetyRecordResponse,
)
def get_hq_worker_safety_record(
    person_id: int,
    db: DbDep,
    current_user: CurrentUserDep,
):
    try:
        record = get_worker_safety_record(db, person_id=person_id)
    except ValueError as exc:
        if str(exc) == "person_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
        raise
    return WorkerSafetyRecordResponse(**record)
