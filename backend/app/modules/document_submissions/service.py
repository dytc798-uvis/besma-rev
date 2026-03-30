from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_submissions.models import DocumentReviewHistory, ReviewAction


@dataclass(frozen=True)
class TransitionResult:
    from_status: str
    to_status: str


def transition_instance_workflow_status(
    inst: DocumentInstance,
    *,
    action: str,
) -> TransitionResult:
    """
    업무 워크플로우 상태 전이 규칙 (MVP 고정).
    - 오케스트레이션 status/status_reason는 건드리지 않는다.
    """
    cur = inst.workflow_status

    if action == "upload":
        if cur not in {WorkflowStatus.NOT_SUBMITTED, WorkflowStatus.REJECTED}:
            raise ValueError(f"invalid transition: {cur} -> SUBMITTED (upload)")
        inst.workflow_status = WorkflowStatus.SUBMITTED
        return TransitionResult(from_status=cur, to_status=inst.workflow_status)

    if action == "start_review":
        if cur != WorkflowStatus.SUBMITTED:
            raise ValueError(f"invalid transition: {cur} -> UNDER_REVIEW (start_review)")
        inst.workflow_status = WorkflowStatus.UNDER_REVIEW
        return TransitionResult(from_status=cur, to_status=inst.workflow_status)

    if action == "approve":
        if cur not in {WorkflowStatus.SUBMITTED, WorkflowStatus.UNDER_REVIEW}:
            raise ValueError(f"invalid transition: {cur} -> APPROVED (approve)")
        inst.workflow_status = WorkflowStatus.APPROVED
        return TransitionResult(from_status=cur, to_status=inst.workflow_status)

    if action == "reject":
        if cur not in {WorkflowStatus.SUBMITTED, WorkflowStatus.UNDER_REVIEW}:
            raise ValueError(f"invalid transition: {cur} -> REJECTED (reject)")
        inst.workflow_status = WorkflowStatus.REJECTED
        return TransitionResult(from_status=cur, to_status=inst.workflow_status)

    raise ValueError(f"unknown action: {action}")


def add_review_history(
    db: Session,
    *,
    inst: DocumentInstance,
    document_id: int,
    action_type: str,
    action_by_user_id: int,
    comment: str | None,
    from_workflow_status: str | None,
    to_workflow_status: str | None,
) -> None:
    db.add(
        DocumentReviewHistory(
            instance_id=inst.id,
            document_id=document_id,
            action_type=action_type,
            action_by_user_id=action_by_user_id,
            comment=comment,
            from_workflow_status=from_workflow_status,
            to_workflow_status=to_workflow_status,
            action_at=utc_now(),
        )
    )


def get_instance_or_404(db: Session, instance_id: int) -> DocumentInstance:
    inst = db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
    if not inst:
        raise LookupError("DocumentInstance not found")
    return inst


def map_action_to_history_type(action: str) -> str:
    if action == "upload":
        return ReviewAction.UPLOAD
    if action == "start_review":
        return ReviewAction.START_REVIEW
    if action == "approve":
        return ReviewAction.APPROVE
    if action == "reject":
        return ReviewAction.REJECT
    raise ValueError(f"unknown action: {action}")

