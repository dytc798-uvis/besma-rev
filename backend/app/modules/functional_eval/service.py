from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.enums import Role, UIType
from app.core.datetime_utils import utc_now
from app.modules.functional_eval.models import (
    FunctionalEvalPeriod,
    FunctionalEvalRosterImportBatch,
    FunctionalEvalSanction,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import (
    ParsedRosterRow,
    RosterDiffItem,
    RosterDiffResult,
    parse_daily_roster_xlsx,
)
from app.modules.functional_eval.sanctions import (
    SANCTION_RESULT_LABELS,
    VIOLATION_BY_CODE,
    VIOLATION_CATALOG,
    is_permanent_sanction,
    resolve_sanction,
    worker_status_from_sanctions,
)
from app.modules.sites.models import Site
from app.modules.users.models import User

DEFAULT_PERIOD_TITLE = "기능인제 인사고과"
DEFAULT_DEADLINE = date(2026, 6, 15)


def _rrn_front_password(rrn_raw: str) -> str | None:
    digits = re.sub(r"\D", "", rrn_raw)
    if len(digits) >= 6:
        return digits[:6]
    return None


def _birth_sort_key(rrn_raw: str) -> tuple[int, int, int]:
    digits = re.sub(r"\D", "", rrn_raw)
    if len(digits) < 7:
        return (9999, 12, 31)
    yy = int(digits[0:2])
    mm = int(digits[2:4])
    dd = int(digits[4:6])
    century = 1900 if digits[6] in "1256" else 2000
    if digits[6] in "34":
        century = 2000
    return (century + yy, mm, dd)


def get_or_create_active_period(db: Session) -> FunctionalEvalPeriod:
    period = (
        db.query(FunctionalEvalPeriod)
        .filter(FunctionalEvalPeriod.is_active.is_(True))
        .order_by(FunctionalEvalPeriod.id.desc())
        .first()
    )
    if period is not None:
        return period
    period = FunctionalEvalPeriod(
        title=DEFAULT_PERIOD_TITLE,
        deadline_date=DEFAULT_DEADLINE,
        is_active=True,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def period_is_closed(period: FunctionalEvalPeriod, *, today: date | None = None) -> bool:
    ref = today or utc_now().date()
    return ref > period.deadline_date


def assert_period_editable(period: FunctionalEvalPeriod) -> None:
    if period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")


def serialize_period(period: FunctionalEvalPeriod) -> dict[str, Any]:
    return {
        "id": period.id,
        "title": period.title,
        "deadline_date": period.deadline_date,
        "is_active": period.is_active,
        "is_closed": period_is_closed(period),
        "created_at": period.created_at,
        "updated_at": period.updated_at,
    }


def violation_catalog_public() -> list[dict[str, Any]]:
    return [
        {
            "code": v.code,
            "category": v.category,
            "category_label": v.category_label,
            "label": v.label,
            "sanction_rule": v.sanction_rule,
            "sort_order": v.sort_order,
        }
        for v in VIOLATION_CATALOG
    ]


def _serialize_sanction(row: FunctionalEvalSanction, worker_name: str) -> dict[str, Any]:
    item = VIOLATION_BY_CODE.get(row.violation_code)
    return {
        "id": row.id,
        "period_id": row.period_id,
        "worker_id": row.worker_id,
        "site_code": row.site_code,
        "worker_name": worker_name,
        "violation_code": row.violation_code,
        "violation_label": item.label if item else row.violation_code,
        "violation_category": row.violation_category,
        "violation_category_label": item.category_label if item else row.violation_category,
        "strike_number": row.strike_number,
        "sanction_result": row.sanction_result,
        "sanction_result_label": SANCTION_RESULT_LABELS.get(row.sanction_result, row.sanction_result),
        "note": row.note,
        "reported_by_user_id": row.reported_by_user_id,
        "created_at": row.created_at,
    }


def _worker_sanction_rows(db: Session, worker_id: int) -> list[FunctionalEvalSanction]:
    return (
        db.query(FunctionalEvalSanction)
        .filter(FunctionalEvalSanction.worker_id == worker_id)
        .order_by(FunctionalEvalSanction.created_at.desc(), FunctionalEvalSanction.id.desc())
        .all()
    )


def _worker_is_permanently_expelled(db: Session, worker_id: int) -> bool:
    rows = _worker_sanction_rows(db, worker_id)
    return any(is_permanent_sanction(r.sanction_result) for r in rows)


def _worker_sanction_status(db: Session, worker_id: int) -> tuple[str, str, int, FunctionalEvalSanction | None]:
    rows = _worker_sanction_rows(db, worker_id)
    if not rows:
        return "NONE", "해당 없음", 0, None
    results = [r.sanction_result for r in rows]
    status = worker_status_from_sanctions(results)
    label = SANCTION_RESULT_LABELS.get(status, status if status != "NONE" else "해당 없음")
    return status, label, len(rows), rows[0]


def serialize_worker(db: Session, worker: FunctionalEvalWorker) -> dict[str, Any]:
    status, status_label, count, latest = _worker_sanction_status(db, worker.id)
    permanent = _worker_is_permanently_expelled(db, worker.id)
    payload: dict[str, Any] = {
        "id": worker.id,
        "period_id": worker.period_id,
        "site_code": worker.site_code,
        "site_name": worker.site_name,
        "row_no": worker.row_no,
        "name": worker.name,
        "age_label": worker.age_label,
        "position_name": worker.position_name,
        "job_name": worker.job_name,
        "rrn_masked": worker.rrn_masked,
        "is_site_manager": worker.is_site_manager,
        "is_active": worker.is_active,
        "sanction_status": status,
        "sanction_status_label": status_label if status != "NONE" else "해당 없음",
        "sanction_count": count,
        "is_permanently_expelled": permanent,
        "history_visible": not permanent,
        "latest_sanction": _serialize_sanction(latest, worker.name) if latest and not permanent else None,
        "mileage": serialize_mileage_placeholder(worker),
    }
    return payload


def serialize_mileage_placeholder(worker: FunctionalEvalWorker) -> dict[str, Any]:
    return {
        "status": "PREPARED",
        "points": worker.mileage_points,
        "note": worker.mileage_note,
        "message": "우수 의견 마일리지 제도 운영 준비 중입니다.",
    }


def _site_code_for_user(user: User) -> str:
    return (user.login_id or "").strip()


def _assert_worker_access(user: User, worker: FunctionalEvalWorker) -> None:
    if user.role == Role.SITE_FUNCTIONAL_EVAL and _site_code_for_user(user) != worker.site_code:
        raise ValueError("SITE_MISMATCH")


def list_workers_for_user(db: Session, user: User, period: FunctionalEvalPeriod) -> list[dict[str, Any]]:
    site_code = _site_code_for_user(user)
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_site_manager.is_(False),
        FunctionalEvalWorker.is_active.is_(True),
    )
    if user.role == Role.SITE_FUNCTIONAL_EVAL:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    rows = q.order_by(FunctionalEvalWorker.row_no.asc(), FunctionalEvalWorker.id.asc()).all()
    return [serialize_worker(db, row) for row in rows]


def get_worker_history(db: Session, user: User, worker_id: int) -> dict[str, Any]:
    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None:
        raise ValueError("WORKER_NOT_FOUND")
    _assert_worker_access(user, worker)

    permanent = _worker_is_permanently_expelled(db, worker.id)
    worker_payload = serialize_worker(db, worker)

    if permanent:
        latest = _worker_sanction_rows(db, worker.id)
        summary = _serialize_sanction(latest[0], worker.name) if latest else None
        return {
            "worker": worker_payload,
            "history_visible": False,
            "sanctions": [],
            "summary": summary,
            "message": "영구 퇴출 대상은 상세 이력을 표시하지 않습니다.",
        }

    current = (
        db.query(FunctionalEvalSanction)
        .filter(FunctionalEvalSanction.worker_id == worker.id)
        .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
        .all()
    )
    prior_workers = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.rrn_hash == worker.rrn_hash,
            FunctionalEvalWorker.id != worker.id,
        )
        .order_by(FunctionalEvalWorker.period_id.desc())
        .all()
    )
    prior_sanctions: list[dict[str, Any]] = []
    for pw in prior_workers:
        rows = (
            db.query(FunctionalEvalSanction)
            .filter(FunctionalEvalSanction.worker_id == pw.id)
            .order_by(FunctionalEvalSanction.created_at.asc())
            .all()
        )
        for row in rows:
            item = _serialize_sanction(row, pw.name)
            item["period_id"] = pw.period_id
            item["from_prior_period"] = True
            prior_sanctions.append(item)

    return {
        "worker": worker_payload,
        "history_visible": True,
        "sanctions": [_serialize_sanction(s, worker.name) for s in current],
        "prior_sanctions": prior_sanctions,
        "mileage": serialize_mileage_placeholder(worker),
    }


def record_sanction(
    db: Session,
    *,
    period: FunctionalEvalPeriod,
    user: User,
    worker_id: int,
    violation_code: str,
    note: str | None,
) -> dict[str, Any]:
    assert_period_editable(period)
    if violation_code not in VIOLATION_BY_CODE:
        raise ValueError("UNKNOWN_VIOLATION")

    worker = db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id == worker_id).first()
    if worker is None or worker.period_id != period.id:
        raise ValueError("WORKER_NOT_FOUND")
    if worker.is_site_manager:
        raise ValueError("CANNOT_SANCTION_SITE_MANAGER")
    if not worker.is_active:
        raise ValueError("WORKER_INACTIVE")

    _assert_worker_access(user, worker)

    prior_count = (
        db.query(FunctionalEvalSanction)
        .filter(
            FunctionalEvalSanction.period_id == period.id,
            FunctionalEvalSanction.worker_id == worker.id,
            FunctionalEvalSanction.violation_code == violation_code,
        )
        .count()
    )
    sanction_result, strike = resolve_sanction(violation_code, prior_count)
    item = VIOLATION_BY_CODE[violation_code]

    row = FunctionalEvalSanction(
        period_id=period.id,
        worker_id=worker.id,
        site_code=worker.site_code,
        violation_code=violation_code,
        violation_category=item.category,
        strike_number=strike,
        sanction_result=sanction_result,
        note=(note or "").strip() or None,
        reported_by_user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_sanction(row, worker.name)


def list_hq_summary(
    db: Session,
    period: FunctionalEvalPeriod,
    *,
    sort_by: str = "site_code",
    sort_dir: str = "asc",
    site_code: str | None = None,
    sanction_status: str | None = None,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    q = db.query(FunctionalEvalWorker).filter(
        FunctionalEvalWorker.period_id == period.id,
        FunctionalEvalWorker.is_site_manager.is_(False),
    )
    if not include_inactive:
        q = q.filter(FunctionalEvalWorker.is_active.is_(True))
    if site_code:
        q = q.filter(FunctionalEvalWorker.site_code == site_code)
    workers = q.all()
    items: list[dict[str, Any]] = []
    for worker in workers:
        worker_payload = serialize_worker(db, worker)
        if sanction_status and worker_payload["sanction_status"] != sanction_status:
            continue
        sanctions = (
            db.query(FunctionalEvalSanction)
            .filter(FunctionalEvalSanction.worker_id == worker.id)
            .order_by(FunctionalEvalSanction.created_at.asc(), FunctionalEvalSanction.id.asc())
            .all()
        )
        visible_sanctions = sanctions
        if worker_payload["is_permanently_expelled"]:
            visible_sanctions = sanctions[-1:] if sanctions else []
        items.append(
            {
                "worker": worker_payload,
                "sanctions": [_serialize_sanction(s, worker.name) for s in visible_sanctions],
                "sanction_count_total": len(sanctions),
            }
        )

    reverse = sort_dir.lower() == "desc"

    def _key(item: dict[str, Any]) -> Any:
        w = item["worker"]
        if sort_by == "sanction_status":
            return w.get("sanction_status") or ""
        if sort_by == "name":
            return w.get("name") or ""
        if sort_by == "sanction_count":
            return w.get("sanction_count") or 0
        return w.get("site_code") or ""

    items.sort(key=_key, reverse=reverse)
    return items


def _diff_row(existing: FunctionalEvalWorker | None, row: ParsedRosterRow) -> RosterDiffItem:
    if existing is None:
        return RosterDiffItem(
            type="NEW",
            rrn_hash=row.rrn_hash,
            name=row.name,
            site_code=row.site_code,
        )
    changes: dict[str, tuple[Any, Any]] = {}
    if existing.name != row.name:
        changes["name"] = (existing.name, row.name)
    if existing.site_code != row.site_code:
        changes["site_code"] = (existing.site_code, row.site_code)
    if existing.job_code != row.job_code:
        changes["job_code"] = (existing.job_code, row.job_code)
    if not existing.is_active:
        changes["is_active"] = (False, True)
    diff_type = "UPDATED" if changes else "UNCHANGED"
    return RosterDiffItem(
        type=diff_type,
        rrn_hash=row.rrn_hash,
        name=row.name,
        site_code=row.site_code,
        worker_id=existing.id,
        changes=changes or None,
    )


def diff_daily_roster(
    db: Session,
    period: FunctionalEvalPeriod,
    parsed_rows: list[ParsedRosterRow],
) -> RosterDiffResult:
    existing_all = (
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all()
    )
    by_hash = {w.rrn_hash: w for w in existing_all if w.rrn_hash}
    incoming_hashes = {r.rrn_hash for r in parsed_rows}

    items: list[RosterDiffItem] = []
    for row in parsed_rows:
        items.append(_diff_row(by_hash.get(row.rrn_hash), row))

    for rrn_hash, worker in by_hash.items():
        if rrn_hash in incoming_hashes:
            continue
        if not worker.is_active:
            continue
        items.append(
            RosterDiffItem(
                type="REMOVED",
                rrn_hash=rrn_hash,
                name=worker.name,
                site_code=worker.site_code,
                worker_id=worker.id,
            )
        )
    return RosterDiffResult(items=items)


def _next_row_no(db: Session, period_id: int, site_code: str) -> int:
    last = (
        db.query(FunctionalEvalWorker)
        .filter(FunctionalEvalWorker.period_id == period_id, FunctionalEvalWorker.site_code == site_code)
        .order_by(FunctionalEvalWorker.row_no.desc())
        .first()
    )
    return (last.row_no + 1) if last else 1


def _provision_site_managers(db: Session, parsed_rows: list[ParsedRosterRow]) -> dict[str, int]:
    managers_by_site: dict[str, list[tuple[tuple[int, int, int], str, str]]] = {}
    for row in parsed_rows:
        if row.is_site_manager:
            managers_by_site.setdefault(row.site_code, []).append(
                (_birth_sort_key(row.rrn_raw), row.site_code, row.rrn_raw)
            )

    sites_created = 0
    managers_created = 0
    for site_code, managers in managers_by_site.items():
        if not managers:
            continue
        managers.sort(key=lambda x: x[0])
        rrn_raw = managers[0][2]
        pw = _rrn_front_password(rrn_raw)
        if not pw:
            continue

        site = db.query(Site).filter(Site.site_code == site_code).first()
        if site is None:
            site = Site(site_code=site_code, site_name=f"현장 {site_code}")
            db.add(site)
            db.flush()
            sites_created += 1

        user = db.query(User).filter(User.login_id == site_code).first()
        if user is None:
            user = User(
                name=f"{site_code} 소장",
                login_id=site_code,
                password_hash=get_password_hash(pw),
                role=Role.SITE_FUNCTIONAL_EVAL,
                ui_type=UIType.SITE,
                site_id=site.id,
                must_change_password=False,
            )
            db.add(user)
            managers_created += 1
        else:
            user.role = Role.SITE_FUNCTIONAL_EVAL
            user.ui_type = UIType.SITE
            user.site_id = site.id
            user.password_hash = get_password_hash(pw)
            user.must_change_password = False
            db.add(user)

    db.commit()
    return {"sites_created": sites_created, "managers_created": managers_created}


def apply_daily_roster_diff(
    db: Session,
    period: FunctionalEvalPeriod,
    parsed_rows: list[ParsedRosterRow],
    *,
    original_filename: str,
    stored_path: str,
) -> dict[str, Any]:
    diff = diff_daily_roster(db, period, parsed_rows)
    existing_all = (
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all()
    )
    by_hash = {w.rrn_hash: w for w in existing_all}
    incoming_hashes = {r.rrn_hash for r in parsed_rows}
    now = utc_now()

    for row in parsed_rows:
        worker = by_hash.get(row.rrn_hash)
        if worker is None:
            worker = FunctionalEvalWorker(
                period_id=period.id,
                site_code=row.site_code,
                row_no=_next_row_no(db, period.id, row.site_code),
                name=row.name,
                rrn_hash=row.rrn_hash,
                rrn_masked=row.rrn_masked,
                job_code=row.job_code,
                phone_mobile=row.phone,
                is_site_manager=row.is_site_manager,
                is_active=True,
            )
            db.add(worker)
        else:
            if worker.site_code != row.site_code:
                worker.row_no = _next_row_no(db, period.id, row.site_code)
            worker.site_code = row.site_code
            worker.name = row.name
            worker.job_code = row.job_code
            worker.phone_mobile = row.phone
            worker.rrn_masked = row.rrn_masked
            worker.is_site_manager = row.is_site_manager
            worker.is_active = True
            worker.removed_at = None
            worker.updated_at = now
            db.add(worker)

    for rrn_hash, worker in by_hash.items():
        if rrn_hash in incoming_hashes:
            continue
        if not worker.is_active:
            continue
        worker.is_active = False
        worker.removed_at = now
        db.add(worker)

    db.flush()
    manager_stats = _provision_site_managers(db, parsed_rows)

    batch = FunctionalEvalRosterImportBatch(
        period_id=period.id,
        original_filename=original_filename,
        stored_path=stored_path,
        total_rows=len(parsed_rows),
        new_count=diff.new_count,
        updated_count=diff.updated_count,
        unchanged_count=diff.unchanged_count,
        removed_count=diff.removed_count,
    )
    db.add(batch)
    db.commit()

    return {
        "batch_id": batch.id,
        "total_rows": len(parsed_rows),
        "new_count": diff.new_count,
        "updated_count": diff.updated_count,
        "unchanged_count": diff.unchanged_count,
        "removed_count": diff.removed_count,
        "site_count": len({r.site_code for r in parsed_rows}),
        **manager_stats,
    }


def serialize_roster_diff(diff: RosterDiffResult) -> dict[str, Any]:
    return {
        "total": len(diff.items),
        "new_count": diff.new_count,
        "updated_count": diff.updated_count,
        "unchanged_count": diff.unchanged_count,
        "removed_count": diff.removed_count,
        "items": [
            {
                "type": item.type,
                "rrn_hash": item.rrn_hash,
                "name": item.name,
                "site_code": item.site_code,
                "worker_id": item.worker_id,
                "changes": item.changes,
            }
            for item in diff.items
        ],
    }


def diff_daily_roster_file(db: Session, period: FunctionalEvalPeriod, file_path: Path) -> dict[str, Any]:
    parsed = parse_daily_roster_xlsx(file_path)
    diff = diff_daily_roster(db, period, parsed)
    return {**serialize_roster_diff(diff), "parsed_rows": len(parsed)}


def apply_daily_roster_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    original_filename: str,
) -> dict[str, Any]:
    parsed = parse_daily_roster_xlsx(file_path)
    return apply_daily_roster_diff(
        db,
        period,
        parsed,
        original_filename=original_filename,
        stored_path=str(file_path),
    )
