"""월별현장별집계 + 출역일보 기반 기능인제 계정·근로자 자동 반영."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
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
    FunctionalEvalPeriod,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import hash_rrn, mask_rrn
from app.modules.functional_eval.site_aggregate import parse_monthly_site_aggregate
from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD
from app.modules.functional_eval.site_alias import build_eval_login_id, derive_site_alias
from app.modules.sites.models import Site
from app.modules.users.models import User


def _rrn_front_password(rrn_raw: str) -> str | None:
    digits = re.sub(r"\D", "", rrn_raw)
    if len(digits) >= 6:
        return digits[:6]
    return None


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
    sites_upserted = 0
    registry_upserted = 0
    account_rows: list[dict[str, Any]] = []

    for row in parsed:
        site_alias = aliases[row.site_code]
        manager_login_id = build_eval_login_id(site_alias, row.manager_name)
        erp_label = normalize_erp_site_label(row.erp_site_name)

        site = db.query(Site).filter(Site.site_code == row.site_code).first()
        if site is None:
            site = Site(
                site_code=row.site_code,
                site_name=row.erp_site_name[:200],
                manager_name=row.manager_name,
            )
            db.add(site)
            sites_upserted += 1
        else:
            site.site_name = row.erp_site_name[:200]
            site.manager_name = row.manager_name
            db.add(site)

        reg = db.query(FunctionalEvalSiteRegistry).filter(FunctionalEvalSiteRegistry.site_code == row.site_code).first()
        if reg is None:
            reg = FunctionalEvalSiteRegistry(
                site_code=row.site_code,
                erp_site_label=erp_label,
                site_alias=site_alias,
                manager_name=row.manager_name,
                manager_login_id=manager_login_id,
            )
            db.add(reg)
            registry_upserted += 1
        else:
            reg.erp_site_label = erp_label
            reg.site_alias = site_alias
            reg.manager_name = row.manager_name
            reg.manager_login_id = manager_login_id
            db.add(reg)

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
    return {
        "sites_upserted": sites_upserted,
        "registry_upserted": registry_upserted,
        "site_count": len(parsed),
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
            must_change_password=False,
        )
        db.add(user)
    else:
        user.name = name
        user.role = Role.SITE_FUNCTIONAL_EVAL
        user.ui_type = UIType.SITE
        user.site_id = site.id
        user.password_hash = get_password_hash(password_plain)
        user.must_change_password = False
        db.add(user)
    return user


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

    db.query(FunctionalEvalAttendanceEntry).filter(
        FunctionalEvalAttendanceEntry.period_id == period.id,
        FunctionalEvalAttendanceEntry.work_date == work_date,
    ).delete(synchronize_session=False)

    existing = (
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.period_id == period.id).all()
    )
    by_hash = {w.rrn_hash: w for w in existing if w.rrn_hash}
    now = utc_now()
    linked = 0
    skipped = 0
    row_counters: dict[str, int] = {}
    site_rows: dict[str, list[ParsedAttendanceRow]] = defaultdict(list)

    batch = FunctionalEvalAttendanceImportBatch(
        period_id=period.id,
        work_date=work_date,
        original_filename=original_filename,
        stored_path=stored_path,
        total_rows=0,
    )
    db.add(batch)
    db.flush()

    for row in parsed_rows:
        reg = _resolve_site_for_row(db, row, reg_map)
        if reg is None:
            skipped += 1
            continue

        site_code = reg.site_code
        site_rows[site_code].append(row)
        manager_login = (reg.manager_login_id or "").strip() or site_code
        is_manager = (row.job_name or "").strip() == "소장" or row.name.strip() == reg.manager_name.strip()

        worker = by_hash.get(row.rrn_hash)
        if worker is None:
            worker = FunctionalEvalWorker(
                period_id=period.id,
                site_code=site_code,
                site_name=reg.erp_site_label[:300],
                row_no=_next_row_no(db, period.id, site_code),
                name=row.name,
                rrn_hash=row.rrn_hash,
                rrn_masked=row.rrn_masked,
                job_name=row.job_name,
                assigned_evaluator_login_id=manager_login,
                is_site_manager=is_manager,
                is_active=True,
                is_on_reference_roster=False,
            )
            db.add(worker)
            db.flush()
            by_hash[row.rrn_hash] = worker
        else:
            if worker.site_code != site_code:
                worker.row_no = _next_row_no(db, period.id, site_code)
            worker.site_code = site_code
            worker.site_name = reg.erp_site_label[:300]
            worker.name = row.name
            worker.job_name = row.job_name
            worker.rrn_masked = row.rrn_masked or worker.rrn_masked
            worker.is_site_manager = is_manager
            worker.is_active = True
            worker.updated_at = now
            db.add(worker)

        if site_code not in row_counters:
            row_counters[site_code] = _next_row_no(db, period.id, site_code) - 1
        row_counters[site_code] += 1
        worker.row_no = row_counters[site_code]

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
                batch_id=batch.id,
            )
        )
        linked += 1

    provision_stats = _provision_evaluators_from_attendance(
        db, period, work_date, site_rows=site_rows, reg_map=reg_map
    )

    batch.total_rows = linked
    batch.linked_workers = linked
    batch.skipped_no_roster = skipped
    period.last_attendance_date = work_date
    db.add(period)
    db.add(batch)
    db.commit()

    return {
        "batch_id": batch.id,
        "work_date": work_date.isoformat(),
        "total_rows": len(parsed_rows),
        "linked_workers": linked,
        "skipped_no_registry": skipped,
        "site_count": len(site_rows),
        **provision_stats,
    }


def _provision_evaluators_from_attendance(
    db: Session,
    period: FunctionalEvalPeriod,
    work_date: date,
    *,
    site_rows: dict[str, list[ParsedAttendanceRow]],
    reg_map: dict[str, FunctionalEvalSiteRegistry],
) -> dict[str, Any]:
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
        manager_pw = _rrn_front_password(manager_rrn or "")
        if manager_pw:
            _upsert_eval_user(
                db,
                login_id=manager_login,
                name=manager_name,
                password_plain=manager_pw,
                site=site,
            )
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
                if worker:
                    worker.assigned_evaluator_login_id = manager_login
                    db.add(worker)
                    assigned_workers += 1
            continue

        by_rep: dict[str, list[ParsedAttendanceRow]] = defaultdict(list)
        for row in workers_today:
            rep = (row.rep_name or "").strip() or manager_name
            by_rep[rep].append(row)

        for rep_name, team_rows in by_rep.items():
            if rep_name == manager_name:
                evaluator_login = manager_login
                role = "소장팀"
            else:
                evaluator_login = build_eval_login_id(reg.site_alias, rep_name)
                role = "팀장"
                rep_rrn = name_rrn.get(rep_name)
                rep_pw = _rrn_front_password(rep_rrn or "")
                if rep_pw and evaluator_login:
                    _upsert_eval_user(
                        db,
                        login_id=evaluator_login,
                        name=rep_name,
                        password_plain=rep_pw,
                        site=site,
                    )
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

            for row in team_rows:
                worker = (
                    db.query(FunctionalEvalWorker)
                    .filter(
                        FunctionalEvalWorker.period_id == period.id,
                        FunctionalEvalWorker.rrn_hash == row.rrn_hash,
                    )
                    .first()
                )
                if worker:
                    worker.assigned_evaluator_login_id = evaluator_login
                    db.add(worker)
                    assigned_workers += 1

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
