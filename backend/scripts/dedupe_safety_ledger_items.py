from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal
from app.modules.safety_features import risk_gates as rg
from app.modules.safety_features.models import (
    NonconformityItem,
    NonconformityLedger,
    WorkerVoiceComment,
    WorkerVoiceItem,
    WorkerVoiceLedger,
)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _wv_key(item: WorkerVoiceItem) -> str:
    return "|".join(
        [
            _norm(item.worker_name),
            _norm(item.worker_birth_date),
            _norm(item.worker_phone_number),
            _norm(item.opinion_text),
        ]
    )


def _nc_key(item: NonconformityItem) -> str:
    return "|".join([_norm(item.issue_text), _norm(item.improvement_action)])


def _dt(value: datetime | None) -> datetime:
    return value or datetime.min


def _wv_rank(item: WorkerVoiceItem) -> tuple:
    hq_ok = rg.risk_db_hq_status_effective(item) == rg.RISK_DB_HQ_APPROVED
    return (
        1 if hq_ok else 0,
        1 if getattr(item, "reward_candidate", False) else 0,
        1 if getattr(item, "site_approved", False) else 0,
        _dt(getattr(item, "updated_at", None)),
        int(getattr(item, "id", 0)),
    )


def _nc_rank(item: NonconformityItem) -> tuple:
    hq_ok = rg.risk_db_hq_status_effective(item) == rg.RISK_DB_HQ_APPROVED
    return (
        1 if hq_ok else 0,
        1 if getattr(item, "reward_candidate", False) else 0,
        1 if getattr(item, "site_approved", False) else 0,
        _dt(getattr(item, "updated_at", None)),
        int(getattr(item, "id", 0)),
    )


def _merge_wv_fields(winner: WorkerVoiceItem, loser: WorkerVoiceItem) -> None:
    # Keep richer text/media/state information if winner lacks it.
    for attr in [
        "action_before",
        "action_after",
        "action_status",
        "action_owner",
        "before_photo_path",
        "after_photo_path",
        "site_action_comment",
        "hq_review_comment",
        "site_reject_note",
    ]:
        if not getattr(winner, attr, None) and getattr(loser, attr, None):
            setattr(winner, attr, getattr(loser, attr))


def _merge_nc_fields(winner: NonconformityItem, loser: NonconformityItem) -> None:
    for attr in [
        "action_before",
        "improvement_action",
        "action_status",
        "improvement_owner",
        "before_photo_path",
        "after_photo_path",
        "improvement_photo_path",
        "site_action_comment",
        "hq_review_comment",
        "site_reject_note",
    ]:
        if not getattr(winner, attr, None) and getattr(loser, attr, None):
            setattr(winner, attr, getattr(loser, attr))


def dedupe_worker_voice(db) -> tuple[int, int]:
    rows = (
        db.query(WorkerVoiceItem, WorkerVoiceLedger)
        .join(WorkerVoiceLedger, WorkerVoiceLedger.id == WorkerVoiceItem.ledger_id)
        .all()
    )
    groups: dict[tuple[int | None, str], list[WorkerVoiceItem]] = defaultdict(list)
    for item, ledger in rows:
        groups[(ledger.site_id, _wv_key(item))].append(item)

    removed = 0
    touched = 0
    for _group_key, items in groups.items():
        if len(items) <= 1:
            continue
        winner = max(items, key=_wv_rank)
        touched += 1
        for loser in items:
            if loser.id == winner.id:
                continue
            _merge_wv_fields(winner, loser)
            # Preserve comment history.
            db.query(WorkerVoiceComment).filter(WorkerVoiceComment.item_id == loser.id).update(
                {"item_id": winner.id},
                synchronize_session=False,
            )
            db.delete(loser)
            removed += 1
        db.add(winner)
    return touched, removed


def dedupe_nonconformity(db) -> tuple[int, int]:
    rows = (
        db.query(NonconformityItem, NonconformityLedger)
        .join(NonconformityLedger, NonconformityLedger.id == NonconformityItem.ledger_id)
        .all()
    )
    groups: dict[tuple[int | None, str], list[NonconformityItem]] = defaultdict(list)
    for item, ledger in rows:
        groups[(ledger.site_id, _nc_key(item))].append(item)

    removed = 0
    touched = 0
    for _group_key, items in groups.items():
        if len(items) <= 1:
            continue
        winner = max(items, key=_nc_rank)
        touched += 1
        for loser in items:
            if loser.id == winner.id:
                continue
            _merge_nc_fields(winner, loser)
            db.delete(loser)
            removed += 1
        db.add(winner)
    return touched, removed


def main() -> None:
    db = SessionLocal()
    try:
        wv_groups, wv_removed = dedupe_worker_voice(db)
        nc_groups, nc_removed = dedupe_nonconformity(db)
        db.commit()
        print(
            "dedupe-complete",
            {
                "worker_voice_groups_touched": wv_groups,
                "worker_voice_rows_removed": wv_removed,
                "nonconformity_groups_touched": nc_groups,
                "nonconformity_rows_removed": nc_removed,
            },
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
