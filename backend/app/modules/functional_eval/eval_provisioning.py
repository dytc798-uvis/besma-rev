"""월별현장별집계 + 출역일보 기반 기능인제 계정·근로자 자동 반영."""

from __future__ import annotations

import re
import secrets
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config.security import get_password_hash
from app.core.enums import Role, UIType
from app.core.datetime_utils import utc_now
from app.modules.functional_eval.attendance import ParsedAttendanceRow, parse_attendance_report
from app.modules.functional_eval.models import (
    FunctionalEvalAttendanceEntry,
    FunctionalEvalAttendanceImportBatch,
    FunctionalEvalConsent,
    FunctionalEvalPeriod,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import hash_rrn, mask_rrn
from app.modules.functional_eval.site_aggregate import parse_monthly_site_aggregate
from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD
from app.modules.functional_eval.import_diff import entry_tuple, row_tuple, worker_needs_attendance_update
from app.modules.functional_eval.rep_name import is_person_rep_name, resolve_team_rep_name
from app.modules.functional_eval.site_alias import build_eval_login_id, derive_site_alias
from app.modules.sites.models import Site
from app.modules.users.models import User


def _evaluation_batch_for_new_worker(db: Session, period_id: int, site_code: str) -> int:
    from app.modules.functional_eval import additional_rounds
    from app.modules.functional_eval.signature_ops import assign_evaluation_batch_for_new_worker

    if additional_rounds.schema_ready(db):
        return additional_rounds.next_batch(db, period_id, site_code)
    return assign_evaluation_batch_for_new_worker(db, period_id, site_code)


def _rrn_front_password(rrn_raw: str) -> str | None:
    digits = re.sub(r"\D", "", rrn_raw)
    if len(digits) >= 6:
        return digits[:6]
    return None


def _lookup_rep_rrn(
    db: Session,
    period_id: int,
    site_code: str,
    rep_name: str,
    name_rrn: dict[str, str],
) -> str:
    """팀장 RRN: 당일 출역 명단 우선, 없으면 기능인제 로스터(참조 명단)에서 조회."""
    key = rep_name.strip()
    if not key:
        return ""
    if key in name_rrn and name_rrn[key]:
        return name_rrn[key]
    worker = (
        db.query(FunctionalEvalWorker)
        .filter(
            FunctionalEvalWorker.period_id == period_id,
            FunctionalEvalWorker.site_code == site_code,
            FunctionalEvalWorker.name == key,
            FunctionalEvalWorker.is_active.is_(True),
        )
        .order_by(FunctionalEvalWorker.is_on_reference_roster.desc(), FunctionalEvalWorker.id.asc())
        .first()
    )
    if worker and worker.rrn_masked:
        return worker.rrn_masked
    return ""


def _period_is_closed(period: FunctionalEvalPeriod) -> bool:
    return utc_now().date() > period.deadline_date


def assert_period_editable(period: FunctionalEvalPeriod) -> None:
    if _period_is_closed(period):
        raise ValueError("PERIOD_CLOSED")


def _next_row_no(db: Session, period_id: int, site_code: str) -> int:
    last = (
        db.query(FunctionalEvalWorker)
        .filter(FunctionalEvalWorker.period_id == period_id, FunctionalEvalWorker.site_code == site_code)
        .order_by(FunctionalEvalWorker.row_no.desc())
        .first()
    )
    return (last.row_no + 1) if last else 1


def normalize_erp_site_label(label: str | None) -> str:
    text = (label or "").strip()
    if text.startswith("현장명:"):
        text = text.replace("현장명:", "", 1).strip()
    return text


def _ensure_unique_aliases(rows: list) -> dict[str, str]:
    """site_code -> site_alias (충돌 시 코드 접미사)."""
    alias_to_code: dict[str, str] = {}
    result: dict[str, str] = {}
    for row in rows:
        base = derive_site_alias(row.erp_site_name)
        alias = base
        if alias in alias_to_code and alias_to_code[alias] != row.site_code:
            alias = f"{base}{row.site_code[-2:]}"
        alias_to_code[alias] = row.site_code
        result[row.site_code] = alias
    return result


def apply_monthly_site_aggregate_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    original_filename: str,
) -> dict[str, Any]:
    assert_period_editable(period)
    parsed = parse_monthly_site_aggregate(file_path)
    aliases = _ensure_unique_aliases(parsed)
    sites_added = 0
    sites_updated = 0
    sites_unchanged = 0
    registry_added = 0
    registry_updated = 0
    registry_unchanged = 0
    account_rows: list[dict[str, Any]] = []

    for row in parsed:
        site_alias = aliases[row.site_code]
        manager_login_id = build_eval_login_id(site_alias, row.manager_name)
        erp_label = normalize_erp_site_label(row.erp_site_name)
        site_name = row.erp_site_name[:200]

        site = db.query(Site).filter(Site.site_code == row.site_code).first()
        if site is None:
            site = Site(
                site_code=row.site_code,
                site_name=site_name,
                manager_name=row.manager_name,
            )
            db.add(site)
            sites_added += 1
        else:
            if site.site_name != site_name or site.manager_name != row.manager_name:
                site.site_name = site_name
                site.manager_name = row.manager_name
                db.add(site)
                sites_updated += 1
            else:
                sites_unchanged += 1

        reg = db.query(FunctionalEvalSiteRegistry).filter(FunctionalEvalSiteRegistry.site_code == row.site_code).first()
        if reg is None:
            reg = FunctionalEvalSiteRegistry(
                site_code=row.site_code,
                erp_site_label=erp_label,
                site_alias=site_alias,
                manager_name=row.manager_name,
                manager_login_id=manager_login_id,
                erp_headcount=row.erp_headcount,
                erp_man_days=row.erp_man_days,
                erp_work_days=row.erp_work_days,
            )
            db.add(reg)
            registry_added += 1
        else:
            changed = (
                reg.erp_site_label != erp_label
                or reg.site_alias != site_alias
                or reg.manager_name != row.manager_name
                or reg.manager_login_id != manager_login_id
                or reg.erp_headcount != row.erp_headcount
                or reg.erp_man_days != row.erp_man_days
                or reg.erp_work_days != row.erp_work_days
            )
            if changed:
                reg.erp_site_label = erp_label
                reg.site_alias = site_alias
                reg.manager_name = row.manager_name
                reg.manager_login_id = manager_login_id
                reg.erp_headcount = row.erp_headcount
                reg.erp_man_days = row.erp_man_days
                reg.erp_work_days = row.erp_work_days
                db.add(reg)
                registry_updated += 1
            else:
                registry_unchanged += 1

        account_rows.append(
            {
                "site_code": row.site_code,
                "site_alias": site_alias,
                "manager_name": row.manager_name,
                "login_id": manager_login_id,
                "initial_password": "(출역일보 반영 시 주민번호 앞 6자리)",
            }
        )

    db.commit()
    account_rows.sort(key=lambda x: x["site_code"])
    erp_headcount_total = sum(int(r.erp_headcount or 0) for r in parsed)
    from app.modules.functional_eval import grade_stats_cache

    grade_stats_cache.rebuild_and_persist(db, period)
    return {
        "sites_added": sites_added,
        "sites_updated": sites_updated,
        "sites_unchanged": sites_unchanged,
        "registry_added": registry_added,
        "registry_updated": registry_updated,
        "registry_unchanged": registry_unchanged,
        "sites_upserted": sites_added + sites_updated,
        "registry_upserted": registry_added + registry_updated,
        "site_count": len(parsed),
        "erp_headcount_total": erp_headcount_total,
        "account_rows": account_rows,
    }


def _registry_map(db: Session) -> dict[str, FunctionalEvalSiteRegistry]:
    rows = db.query(FunctionalEvalSiteRegistry).all()
    out: dict[str, FunctionalEvalSiteRegistry] = {}
    for reg in rows:
        key = normalize_erp_site_label(reg.erp_site_label)
        if key:
            out[key] = reg
    return out


def _upsert_eval_user(
    db: Session,
    *,
    login_id: str,
    name: str,
    password_plain: str,
    site: Site,
    period_id: int | None = None,
) -> User:
    user = db.query(User).filter(User.login_id == login_id).first()
    if user is None:
        user = User(
            name=name,
            login_id=login_id,
            password_hash=get_password_hash(password_plain),
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site.id,
            must_change_password=True,
            temporary_password_expires_at=utc_now() + timedelta(hours=24),
        )
        db.add(user)
    else:
        from . import service, site_evaluator_access
        role = getattr(user.role, 'value', user.role)
        try:
            linked_code = service._site_code_for_user(user, db)
        except ValueError:
            linked_code = None
        if (not user.is_active or role not in {'SITE', 'SITE_FUNCTIONAL_EVAL'}
                or getattr(user.ui_type, 'value', user.ui_type) != 'SITE' or linked_code != site.site_code):
            raise ValueError('EVALUATOR_ACCOUNT_SCOPE_MISMATCH')
        if role == 'SITE' and not site_evaluator_access.is_linked_site_manager(db, user, site.site_code):
            assigned = db.query(FunctionalEvalWorker.id).filter_by(period_id=period_id,
                site_code=site.site_code, assigned_evaluator_login_id=user.login_id, is_active=True).first() if period_id else None
            if assigned is None:
                raise ValueError('EVALUATOR_ACCOUNT_SCOPE_MISMATCH')
        # Data refresh is not a password reset, account rename or role change.
        # Existing expiry/password-change requirements remain intact.
    return user


def _protected_attendance_worker_ids(db, period_id):
    from . import additional_rounds
    from .models import FunctionalEvalAssessment, FunctionalEvalSignature
    assessed = {ident for ident, in db.query(FunctionalEvalAssessment.worker_id).join(
        FunctionalEvalWorker, FunctionalEvalWorker.id == FunctionalEvalAssessment.worker_id).filter(
            FunctionalEvalWorker.period_id == period_id)}
    sealed = {(r.site_code, getattr(r, 'evaluation_batch', 0) or 0)
              for r in additional_rounds.all_approvals(db, period_id)
              if r.evaluation_completed_at or r.site_submitted_at or r.status not in {'IN_PROGRESS', 'REJECTED'}}
    sealed.update((code, batch or 0) for code, batch in db.query(
        FunctionalEvalSignature.site_code, FunctionalEvalSignature.evaluation_batch).filter(
            FunctionalEvalSignature.period_id == period_id))
    return assessed | {ident for ident, code, batch in db.query(FunctionalEvalWorker.id,
        FunctionalEvalWorker.site_code, FunctionalEvalWorker.evaluation_batch).filter(
            FunctionalEvalWorker.period_id == period_id) if (code, batch or 0) in sealed}


def _resolve_site_for_row(
    db: Session,
    row: ParsedAttendanceRow,
    reg_map: dict[str, FunctionalEvalSiteRegistry],
) -> FunctionalEvalSiteRegistry | None:
    key = normalize_erp_site_label(row.erp_site_label)
    return reg_map.get(key)


def apply_attendance_report_diff(
    db: Session,
    period: FunctionalEvalPeriod,
    parsed_rows: list[ParsedAttendanceRow],
    *,
    original_filename: str,
    stored_path: str,
) -> dict[str, Any]:
    assert_period_editable(period)
    reg_map = _registry_map(db)
    if not reg_map:
        raise ValueError("SITE_REGISTRY_REQUIRED")

    work_dates = {r.work_date for r in parsed_rows}
    if len(work_dates) != 1:
        raise ValueError("MULTIPLE_WORK_DATES")
    work_date = next(iter(work_dates))

    existing_entries = (
        db.query(FunctionalEvalAttendanceEntry)
        .filter(
            FunctionalEvalAttendanceEntry.period_id == period.id,
            FunctionalEvalAttendanceEntry.work_date == work_date,
        )
        .all()
    )
    existing_by_hash = {e.rrn_hash: e for e in existing_entries if e.rrn_hash}

    existing_workers = (
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all()
    )
    by_hash = {w.rrn_hash: w for w in existing_workers if w.rrn_hash}
    protected_workers = _protected_attendance_worker_ids(db, period.id)
    # Validate sensitive changes before creating workers, attendance or accounts.
    new_round_scopes: set[tuple[str, int]] = set()
    for row in parsed_rows:
        old = by_hash.get(row.rrn_hash)
        reg = _resolve_site_for_row(db, row, reg_map)
        if old is None or reg is None:
            continue
        if not old.is_active or old.removed_at is not None:
            raise ValueError('ATTENDANCE_EXCLUDED_WORKER_REVIEW_REQUIRED')
        manager = (row.job_name or '').strip() == '소장' or row.name.strip() == reg.manager_name.strip()
        if old.id in protected_workers and (old.site_code != reg.site_code or old.is_site_manager != manager):
            raise ValueError('ATTENDANCE_PROTECTED_WORKER_SCOPE_CHANGED')
    now = utc_now()
    linked = 0
    skipped = 0
    added = 0
    updated = 0
    unchanged = 0
    removed = 0
    site_rows: dict[str, list[ParsedAttendanceRow]] = defaultdict(list)
    incoming_hashes: set[str] = set()
    touched_sites: set[str] = set()
    matched_existing_batch_ids: set[int] = set()
    matched_without_batch = False

    batch = FunctionalEvalAttendanceImportBatch(
        period_id=period.id,
        work_date=work_date,
        original_filename=original_filename,
        stored_path=stored_path,
        total_rows=0,
    )
    # Repeated unchanged input must not create another import batch. Preserve
    # the original provisioning path; create a batch only for changed entries.
    def ensure_batch():
        if batch.id is None:
            db.add(batch)
            db.flush()
        return batch.id

    for row in parsed_rows:
        reg = _resolve_site_for_row(db, row, reg_map)
        if reg is None:
            skipped += 1
            continue

        site_code = reg.site_code
        site_name = reg.erp_site_label[:300]
        site_rows[site_code].append(row)
        manager_login = (reg.manager_login_id or "").strip() or site_code
        is_manager = (row.job_name or "").strip() == "소장" or row.name.strip() == reg.manager_name.strip()
        incoming_hashes.add(row.rrn_hash)

        worker = by_hash.get(row.rrn_hash)
        if worker is None:
            worker = FunctionalEvalWorker(
                period_id=period.id,
                site_code=site_code,
                site_name=site_name,
                row_no=_next_row_no(db, period.id, site_code),
                name=row.name,
                rrn_hash=row.rrn_hash,
                rrn_masked=row.rrn_masked,
                job_name=row.job_name,
                assigned_evaluator_login_id=manager_login,
                is_site_manager=is_manager,
                is_active=True,
                is_on_reference_roster=False,
                removed_at=None,
                evaluation_batch=_evaluation_batch_for_new_worker(db, period.id, site_code),
            )
            db.add(worker)
            db.flush()
            by_hash[row.rrn_hash] = worker
            if not is_manager and worker.evaluation_batch > 0:
                new_round_scopes.add((site_code, worker.evaluation_batch))
            touched_sites.add(site_code)
        elif worker.id not in protected_workers and worker_needs_attendance_update(
            worker, row, site_code=site_code, site_name=site_name, is_manager=is_manager
        ):
            if worker.site_code != site_code:
                worker.row_no = _next_row_no(db, period.id, site_code)
            worker.site_code = site_code
            worker.site_name = site_name
            worker.name = row.name
            worker.job_name = row.job_name
            worker.rrn_masked = row.rrn_masked or worker.rrn_masked
            worker.is_site_manager = is_manager
            worker.is_active = True
            worker.removed_at = None
            worker.updated_at = now
            db.add(worker)
            touched_sites.add(site_code)
        elif worker.id not in protected_workers and (not worker.is_active or worker.removed_at is not None):
            worker.is_active = True
            worker.removed_at = None
            worker.updated_at = now
            db.add(worker)
            touched_sites.add(site_code)

        new_fields = row_tuple(row, site_code)
        existing_entry = existing_by_hash.get(row.rrn_hash)
        if existing_entry is None:
            db.add(
                FunctionalEvalAttendanceEntry(
                    period_id=period.id,
                    work_date=work_date,
                    worker_id=worker.id,
                    site_code=site_code,
                    rrn_hash=row.rrn_hash,
                    name=row.name,
                    job_name=row.job_name,
                    rep_name=row.rep_name,
                    erp_site_label=row.erp_site_label,
                    batch_id=ensure_batch(),
                )
            )
            added += 1
            touched_sites.add(site_code)
        elif entry_tuple(existing_entry) != new_fields:
            existing_entry.worker_id = worker.id
            existing_entry.site_code = site_code
            existing_entry.name = row.name
            existing_entry.job_name = row.job_name
            existing_entry.rep_name = row.rep_name
            existing_entry.erp_site_label = row.erp_site_label
            existing_entry.batch_id = ensure_batch()
            db.add(existing_entry)
            updated += 1
            touched_sites.add(site_code)
        else:
            unchanged += 1
            if existing_entry.batch_id is None:
                matched_without_batch = True
            else:
                matched_existing_batch_ids.add(existing_entry.batch_id)

        linked += 1

    # A manually supplied report has no independent full-coverage proof. A
    # missing row (including another site's row) is not a deletion instruction.
    # Corrections to rows actually present remain normal upserts.
    retained_missing_rows = sum(1 for rrn_hash in existing_by_hash if rrn_hash not in incoming_hashes)

    db.flush()
    from . import additional_rounds
    for site_code, evaluation_batch in sorted(new_round_scopes):
        additional_rounds.get_approval(db, period.id, site_code, batch=evaluation_batch, create=True)

    provision_stats = _provision_evaluators_from_attendance(
        db, period, work_date, site_rows=site_rows, reg_map=reg_map, protected_worker_ids=protected_workers
    )

    # New/moved rows receive the next row number above. Preserve the row
    # numbers of existing completed workers rather than resequencing the site.

    batch_created = batch.id is not None
    if batch_created:
        batch.total_rows = linked
        batch.linked_workers = linked
        batch.skipped_no_roster = skipped
    period.last_attendance_date = max(period.last_attendance_date or work_date, work_date)
    db.add(period)
    if batch_created:
        db.add(batch)
    db.commit()

    from app.modules.functional_eval import grade_stats_cache

    grade_stats_cache.rebuild_and_persist(db, period)

    # Unchanged input identifies only the batches of its successfully matched
    # rows, never another site's later batch from the same work date.
    if batch_created:
        result_batch_id = batch.id
        batch_match_status = "CREATED"
    elif linked == 0:
        result_batch_id = None
        batch_match_status = "NO_MATCHED_ROWS"
    elif matched_without_batch or not matched_existing_batch_ids:
        result_batch_id = None
        batch_match_status = "EXISTING_UNIDENTIFIED"
    elif len(matched_existing_batch_ids) == 1:
        result_batch_id = next(iter(matched_existing_batch_ids))
        batch_match_status = "EXISTING_SINGLE"
    else:
        result_batch_id = None
        batch_match_status = "EXISTING_MULTIPLE"
    # Attendance import IDs and evaluation rounds have different meanings.
    # Reuse the same target/enrollment ledger as the evaluation detail endpoint.
    from . import additional_rounds
    from .models import FunctionalEvalTargetEnrollment
    from .service import _evaluation_target_workers
    rounds = {}
    if additional_rounds.schema_ready(db):
        rounds = dict(db.query(FunctionalEvalTargetEnrollment.worker_id,
                               FunctionalEvalTargetEnrollment.evaluation_batch)
                      .filter(FunctionalEvalTargetEnrollment.period_id == period.id).all())
    evaluation_links = sorted({(worker.site_code, rounds.get(worker.id, worker.evaluation_batch or 0))
                               for worker in _evaluation_target_workers(db, period)
                               if worker.rrn_hash in incoming_hashes and worker.site_code in site_rows})
    return {
        "batch_id": result_batch_id,
        "batch_created": batch_created,
        "batch_match_status": batch_match_status,
        "coverage_status": "UNKNOWN_UPSERT_ONLY",
        "retained_missing_rows": retained_missing_rows,
        "work_date": work_date.isoformat(),
        "total_rows": len(parsed_rows),
        "linked_workers": linked,
        "skipped_no_registry": skipped,
        "site_count": len(site_rows),
        "site_codes": sorted(site_rows),
        "evaluation_links": [{"site_code": code, "evaluation_batch": batch}
                             for code, batch in evaluation_links],
        "diff_added": added,
        "diff_updated": updated,
        "diff_unchanged": unchanged,
        "diff_removed": removed,
        **provision_stats,
    }



def _provision_evaluators_from_attendance(
    db: Session,
    period: FunctionalEvalPeriod,
    work_date: date,
    *,
    site_rows: dict[str, list[ParsedAttendanceRow]],
    reg_map: dict[str, FunctionalEvalSiteRegistry],
    protected_worker_ids: set[int] | None = None,
) -> dict[str, Any]:
    protected_worker_ids = protected_worker_ids if protected_worker_ids is not None else _protected_attendance_worker_ids(db, period.id)
    created_accounts = 0
    assigned_workers = 0
    account_rows: list[dict[str, Any]] = []

    code_to_reg = {r.site_code: r for r in reg_map.values()}

    for site_code, rows in site_rows.items():
        reg = code_to_reg.get(site_code)
        if reg is None:
            continue
        site = db.query(Site).filter(Site.site_code == site_code).first()
        if site is None:
            continue

        name_rrn: dict[str, str] = {}
        for row in rows:
            name_rrn[row.name.strip()] = row.rrn_raw

        manager_name = reg.manager_name.strip()
        manager_login = (reg.manager_login_id or "").strip() or build_eval_login_id(reg.site_alias, manager_name)
        reg.manager_login_id = manager_login
        db.add(reg)

        manager_rrn = name_rrn.get(manager_name)
        if not manager_rrn:
            for row in rows:
                if (row.job_name or "").strip() == "소장":
                    manager_rrn = row.rrn_raw
                    break
        manager_identity_confirmed = _rrn_front_password(manager_rrn or "")
        if manager_identity_confirmed:
            manager_pw = secrets.token_urlsafe(12)
            account = _upsert_eval_user(
                db,
                login_id=manager_login,
                name=manager_name,
                password_plain=manager_pw,
                site=site,
                period_id=period.id,
            )
            if account in db.new:
                created_accounts += 1
                account_rows.append(
                {
                    "site_code": site_code,
                    "site_alias": reg.site_alias,
                    "role": "소장",
                    "login_id": manager_login,
                    "initial_password": manager_pw,
                }
            )

        workers_today = [r for r in rows if (r.job_name or "").strip() != "소장" and r.name.strip() != manager_name]
        worker_count = len(workers_today)

        if worker_count <= TEAM_LEADER_SPLIT_THRESHOLD:
            for row in workers_today:
                worker = (
                    db.query(FunctionalEvalWorker)
                    .filter(
                        FunctionalEvalWorker.period_id == period.id,
                        FunctionalEvalWorker.rrn_hash == row.rrn_hash,
                    )
                    .first()
                )
                if worker and worker.id not in protected_worker_ids:
                    worker.assigned_evaluator_login_id = manager_login
                    db.add(worker)
                    assigned_workers += 1
            continue

        by_rep: dict[str, list[ParsedAttendanceRow]] = defaultdict(list)
        for row in workers_today:
            rep = resolve_team_rep_name(row.rep_name, manager_name)
            by_rep[rep].append(row)

        for rep_name, team_rows in by_rep.items():
            if rep_name == manager_name:
                evaluator_login = manager_login
                role = "직영"
            elif len(team_rows) < 2:
                # 팀장·팀원 합쳐 1명뿐이면 소장이 평가
                evaluator_login = manager_login
                role = "직영"
            else:
                role = "팀장"
                evaluator_login = build_eval_login_id(reg.site_alias, rep_name)
                rep_rrn = _lookup_rep_rrn(db, period.id, site_code, rep_name, name_rrn)
                rep_identity_confirmed = _rrn_front_password(rep_rrn or "")
                if rep_identity_confirmed and evaluator_login and is_person_rep_name(rep_name):
                    rep_pw = secrets.token_urlsafe(12)
                    account = _upsert_eval_user(
                        db,
                        login_id=evaluator_login,
                        name=rep_name,
                        password_plain=rep_pw,
                        site=site,
                        period_id=period.id,
                    )
                    if account in db.new:
                        created_accounts += 1
                        account_rows.append(
                        {
                            "site_code": site_code,
                            "site_alias": reg.site_alias,
                            "role": role,
                            "login_id": evaluator_login,
                            "initial_password": rep_pw,
                            "team_worker_count": len(team_rows),
                        }
                    )
                else:
                    evaluator_login = manager_login

            for row in team_rows:
                worker = (
                    db.query(FunctionalEvalWorker)
                    .filter(
                        FunctionalEvalWorker.period_id == period.id,
                        FunctionalEvalWorker.rrn_hash == row.rrn_hash,
                    )
                    .first()
                )
                if worker and worker.id not in protected_worker_ids:
                    if role == "팀장" and (row.name or "").strip() == rep_name.strip():
                        worker.assigned_evaluator_login_id = manager_login
                    else:
                        worker.assigned_evaluator_login_id = evaluator_login
                    db.add(worker)
                    assigned_workers += 1

        # This import assigns only its unprotected rows above. A site-wide
        # reconciliation would also rewrite completed workers' assignments.

    return {
        "created_accounts": created_accounts,
        "assigned_workers": assigned_workers,
        "account_rows": account_rows,
        "split_threshold": TEAM_LEADER_SPLIT_THRESHOLD,
    }


def apply_attendance_report_file(
    db: Session,
    period: FunctionalEvalPeriod,
    file_path: Path,
    *,
    original_filename: str,
) -> dict[str, Any]:
    parsed = parse_attendance_report(file_path)
    return apply_attendance_report_diff(
        db,
        period,
        parsed,
        original_filename=original_filename,
        stored_path=str(file_path),
    )
