from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.documents.models import DocumentInstanceFeedbackLoop, DocumentStatus


class FeedbackLoopStatus:
    NONE = "NONE"
    IMPROVEMENT_REQUESTED = "IMPROVEMENT_REQUESTED"
    SITE_REUPLOADED = "SITE_REUPLOADED"
    HQ_REVIEWING = "HQ_REVIEWING"
    CLOSED_APPROVED = "CLOSED_APPROVED"


STATUS_LABEL_KO: dict[str, str] = {
    FeedbackLoopStatus.NONE: "—",
    FeedbackLoopStatus.IMPROVEMENT_REQUESTED: "개선요청",
    FeedbackLoopStatus.SITE_REUPLOADED: "재업로드",
    FeedbackLoopStatus.HQ_REVIEWING: "재검토",
    FeedbackLoopStatus.CLOSED_APPROVED: "완료",
}


def feedback_loop_label_ko(status: str | None) -> str:
    if not status:
        return STATUS_LABEL_KO[FeedbackLoopStatus.NONE]
    return STATUS_LABEL_KO.get(status, status)


def get_or_create_feedback_loop(db: Session, *, instance_id: int) -> DocumentInstanceFeedbackLoop:
    row = (
        db.query(DocumentInstanceFeedbackLoop)
        .filter(DocumentInstanceFeedbackLoop.instance_id == int(instance_id))
        .first()
    )
    if row is None:
        row = DocumentInstanceFeedbackLoop(
            instance_id=int(instance_id),
            status=FeedbackLoopStatus.NONE,
        )
        db.add(row)
        db.flush()
    return row


def _touch_loop(row: DocumentInstanceFeedbackLoop, *, now: datetime) -> None:
    row.updated_at = now


def sync_feedback_loop_from_workflow(
    db: Session,
    *,
    inst: DocumentInstance,
    doc_status: str | None,
    triggering_user_id: int | None = None,
) -> DocumentInstanceFeedbackLoop | None:
    """
    DocumentInstance.workflow_status + Document.current_status 변화에 맞춰 루프 상태를 갱신한다.
    - 반려/개선 요청 코멘트 흐름은 sync_feedback_loop_after_hq_comment에서 별도 처리.
    """
    now = utc_now()
    loop = get_or_create_feedback_loop(db, instance_id=inst.id)
    wf = inst.workflow_status

    if wf == WorkflowStatus.REJECTED:
        if loop.status not in {FeedbackLoopStatus.IMPROVEMENT_REQUESTED, FeedbackLoopStatus.NONE}:
            loop.status = FeedbackLoopStatus.IMPROVEMENT_REQUESTED
            loop.improvement_requested_at = loop.improvement_requested_at or now
            if triggering_user_id is not None:
                loop.improvement_requested_by_user_id = int(triggering_user_id)
        _touch_loop(loop, now=now)
        return loop

    if wf == WorkflowStatus.SUBMITTED and doc_status == DocumentStatus.SUBMITTED:
        if loop.status == FeedbackLoopStatus.IMPROVEMENT_REQUESTED:
            loop.status = FeedbackLoopStatus.SITE_REUPLOADED
            loop.site_reuploaded_at = now
        _touch_loop(loop, now=now)
        return loop

    if wf == WorkflowStatus.UNDER_REVIEW:
        if loop.status == FeedbackLoopStatus.SITE_REUPLOADED:
            loop.status = FeedbackLoopStatus.HQ_REVIEWING
            loop.hq_reviewing_at = now
        _touch_loop(loop, now=now)
        return loop

    if wf == WorkflowStatus.APPROVED:
        if loop.status in {
            FeedbackLoopStatus.IMPROVEMENT_REQUESTED,
            FeedbackLoopStatus.SITE_REUPLOADED,
            FeedbackLoopStatus.HQ_REVIEWING,
        }:
            loop.status = FeedbackLoopStatus.CLOSED_APPROVED
            loop.closed_at = now
        elif loop.status == FeedbackLoopStatus.NONE:
            # 승인만 있고 개선 루프가 없었던 경우: 레코드는 남기되 상태는 NONE 유지
            pass
        _touch_loop(loop, now=now)
        return loop

    if wf == WorkflowStatus.NOT_SUBMITTED:
        _touch_loop(loop, now=now)
        return loop

    _touch_loop(loop, now=now)
    return loop


def sync_feedback_loop_after_hq_comment(
    db: Session,
    *,
    inst: DocumentInstance | None,
    comment_author_role: str,
    triggering_user_id: int,
) -> DocumentInstanceFeedbackLoop | None:
    """
    본사(HQ)가 문서에 코멘트를 남기면 개선 요청으로 간주한다(운영 단순화).
    """
    if inst is None:
        return None
    role = (comment_author_role or "").strip().upper()
    if role not in {"HQ_SAFE", "HQ_OTHER", "HQ_SAFE_ADMIN", "SUPER_ADMIN", "ACCIDENT_ADMIN"}:
        return None
    now = utc_now()
    loop = get_or_create_feedback_loop(db, instance_id=inst.id)
    if loop.status == FeedbackLoopStatus.CLOSED_APPROVED:
        loop.status = FeedbackLoopStatus.IMPROVEMENT_REQUESTED
    elif loop.status == FeedbackLoopStatus.NONE:
        loop.status = FeedbackLoopStatus.IMPROVEMENT_REQUESTED
    elif loop.status in {FeedbackLoopStatus.SITE_REUPLOADED, FeedbackLoopStatus.HQ_REVIEWING}:
        loop.status = FeedbackLoopStatus.IMPROVEMENT_REQUESTED
    loop.improvement_requested_at = now
    loop.improvement_requested_by_user_id = int(triggering_user_id)
    _touch_loop(loop, now=now)
    return loop


def feedback_loop_public_dict(row: DocumentInstanceFeedbackLoop | None) -> dict:
    if row is None:
        return {
            "instance_id": None,
            "loop_status": FeedbackLoopStatus.NONE,
            "loop_status_label": feedback_loop_label_ko(FeedbackLoopStatus.NONE),
            "improvement_due_date": None,
            "assignee_user_id": None,
            "improvement_note": None,
            "improvement_requested_at": None,
            "site_reuploaded_at": None,
            "hq_reviewing_at": None,
            "closed_at": None,
        }
    return {
        "instance_id": int(row.instance_id),
        "loop_status": row.status,
        "loop_status_label": feedback_loop_label_ko(row.status),
        "improvement_due_date": row.improvement_due_date.isoformat() if row.improvement_due_date else None,
        "assignee_user_id": int(row.assignee_user_id) if row.assignee_user_id is not None else None,
        "improvement_note": row.improvement_note,
        "improvement_requested_at": row.improvement_requested_at.isoformat() if row.improvement_requested_at else None,
        "site_reuploaded_at": row.site_reuploaded_at.isoformat() if row.site_reuploaded_at else None,
        "hq_reviewing_at": row.hq_reviewing_at.isoformat() if row.hq_reviewing_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


def load_feedback_loops_map(db: Session, instance_ids: list[int]) -> dict[int, DocumentInstanceFeedbackLoop]:
    ids = sorted({int(i) for i in instance_ids if i is not None})
    if not ids:
        return {}
    rows = (
        db.query(DocumentInstanceFeedbackLoop)
        .filter(DocumentInstanceFeedbackLoop.instance_id.in_(ids))
        .all()
    )
    return {int(r.instance_id): r for r in rows}


def apply_feedback_loop_patch(
    db: Session,
    *,
    instance_id: int,
    due_date: date | None = None,
    assignee_user_id: int | None = None,
    note: str | None = None,
    clear_due_date: bool = False,
    clear_assignee: bool = False,
    clear_note: bool = False,
) -> DocumentInstanceFeedbackLoop:
    loop = get_or_create_feedback_loop(db, instance_id=instance_id)
    if clear_due_date:
        loop.improvement_due_date = None
    elif due_date is not None:
        loop.improvement_due_date = due_date
    if clear_assignee:
        loop.assignee_user_id = None
    elif assignee_user_id is not None:
        loop.assignee_user_id = int(assignee_user_id)
    if clear_note:
        loop.improvement_note = None
    elif note is not None:
        stripped = note.strip()
        loop.improvement_note = stripped or None
    _touch_loop(loop, now=utc_now())
    db.add(loop)
    return loop
