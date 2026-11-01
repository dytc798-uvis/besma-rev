"""Authenticated site round selection. Reads existing targets; never creates targets."""
from __future__ import annotations

from . import additional_rounds, approval_workflow, signature_revisions


def workers(db, period, site_code, batch):
    from . import service
    return [row for row in service._site_attendance_workers(db, period, site_code)
            if additional_rounds.worker_approval_batch(db, row) == batch]


def choices(db, user, period):
    from . import service, signature_ops
    site_code = service._site_code_for_user(user, db)
    manager = service._is_primary_site_evaluator(db, user, site_code)
    rows = service._site_attendance_workers(db, period, site_code)
    batches = sorted({additional_rounds.worker_approval_batch(db, row) for row in rows})
    result = []
    for batch in batches:
        group = [row for row in rows if additional_rounds.worker_approval_batch(db, row) == batch]
        mine = service.list_workers_for_user(db, user, period, batch=batch)
        if not manager and not mine:
            continue
        approval = additional_rounds.get_approval(db, period.id, site_code, batch=batch)
        status = approval.status if approval is not None else 'IN_PROGRESS'
        incomplete = sum(not service._is_fully_evaluated(row) for row in mine)
        own_signature = next((row for row in signature_revisions.all_records(db, period.id, site_code=site_code, batch=batch, signer_id=user.id)
                              if row.stage == (signature_ops.STAGE_SITE if manager else signature_ops.STAGE_TEAM_LEADER) and not signature_revisions.is_revoked(db, row)), None)
        editable = approval_workflow.is_site_evaluation_editable(status)
        mapping_required = any((row.evaluation_batch or 0) != batch for row in group)
        # Only the actor's actionable scope can make a round the initial selection.
        actionable = editable and (incomplete > 0 or own_signature is None)
        result.append({'evaluation_batch': batch, 'label': signature_ops.batch_label(batch),
                       'status': status, 'status_label': approval_workflow.serialize_site_approval(approval)['status_label'],
                       'target_count': len(group) if manager else len(mine),
                       'my_target_count': len(mine), 'my_incomplete_count': incomplete,
                       'actionable': actionable and not mapping_required,
                       'mapping_required': mapping_required})
    return result


def select(db, user, period, requested=None, expected_period=None):
    if expected_period is not None and period.id != expected_period:
        raise ValueError('PERIOD_SCOPE_CHANGED')
    available = choices(db, user, period)
    if requested is not None:
        match = next((row for row in available if row['evaluation_batch'] == requested), None)
        if match is None:
            raise ValueError('EVALUATION_ROUND_NOT_FOUND')
    else:
        match = next((row for row in available if row['actionable']), None)
        if match is None:
            match = next((row for row in reversed(available) if not row['mapping_required']), None)
        if match is None and available:
            match = available[-1]
    if match and match['mapping_required']:
        raise ValueError('LEGACY_ROUND_MAPPING_REQUIRED')
    return (match['evaluation_batch'] if match else 0), available
