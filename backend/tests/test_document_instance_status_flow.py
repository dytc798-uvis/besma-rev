from __future__ import annotations

import pytest

from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_submissions.service import transition_instance_workflow_status


def _inst(status: str) -> DocumentInstance:
    # ORM 객체 생성만(세션 flush 없음)으로 상태 전이 규칙만 테스트
    di = DocumentInstance(  # type: ignore[call-arg]
        site_id=1,
        document_type_code="DAILY_DOC",
        period_start=None,  # type: ignore[arg-type]
        period_end=None,  # type: ignore[arg-type]
        status="PENDING",
        status_reason="MASTER_DEFAULT",
        selected_requirement_id=None,
        period_basis="CYCLE",
        rule_is_required=True,
    )
    di.workflow_status = status
    return di


def test_upload_transition_allows_not_submitted_rejected():
    for s in (WorkflowStatus.NOT_SUBMITTED, WorkflowStatus.REJECTED):
        inst = _inst(s)
        r = transition_instance_workflow_status(inst, action="upload")
        assert r.to_status == WorkflowStatus.SUBMITTED


def test_review_transition_contract():
    inst = _inst(WorkflowStatus.SUBMITTED)
    transition_instance_workflow_status(inst, action="start_review")
    assert inst.workflow_status == WorkflowStatus.UNDER_REVIEW

    transition_instance_workflow_status(inst, action="approve")
    assert inst.workflow_status == WorkflowStatus.APPROVED


def test_reject_transition_contract():
    inst = _inst(WorkflowStatus.SUBMITTED)
    transition_instance_workflow_status(inst, action="start_review")
    transition_instance_workflow_status(inst, action="reject")
    assert inst.workflow_status == WorkflowStatus.REJECTED


def test_invalid_transition_raises():
    inst = _inst(WorkflowStatus.NOT_SUBMITTED)
    with pytest.raises(ValueError):
        transition_instance_workflow_status(inst, action="approve")

