"""로컬 기능인제 데모 시드 — 대우청라만 미평가, 나머지 현장은 전원 보통(MID) 완료.

Usage:
  cd backend && PYTHONPATH=. python scripts/repair_fe_db_schema.py
  cd backend && PYTHONPATH=. python scripts/seed_fe_local_demo.py
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.config.security import get_password_hash  # noqa: E402
from app.core.database import SessionLocal, init_db  # noqa: E402
from app.core.datetime_utils import utc_now  # noqa: E402
from app.core.enums import Role, UIType  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
from app.modules.functional_eval.eval_catalog import compute_assessment, get_criteria  # noqa: E402
from app.modules.functional_eval.models import (  # noqa: E402
    FunctionalEvalAssessment,
    FunctionalEvalAttendanceEntry,
    FunctionalEvalAttendanceImportBatch,
    FunctionalEvalPeriod,
    FunctionalEvalSiteApproval,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.sites.models import Site  # noqa: E402
from app.modules.users.models import User  # noqa: E402

CHEONGRA_CODE = "24025"
CHEONGRA_ALIAS = "대우청라"
CHEONGRA_MANAGER = "대우청라-박명식"
CHEONGRA_MANAGER_PW = "661123"
CHEONGRA_LEADER = "대우청라-김팀장"
CHEONGRA_LEADER_PW = "750101"
CHEONGRA_TEAM = 8
CHEONGRA_DIRECT = 4
OTHER_WORKERS_PER_SITE = 3
DEFAULT_MANAGER_PW = "111111"
WORK_DATE = date(2026, 6, 10)


def _rrn_hash(digits: str) -> str:
    return hashlib.sha256(digits.encode()).hexdigest()


def _mid_scores(eval_type: str) -> dict[str, str]:
    return {str(c["id"]): "MID" for c in get_criteria(eval_type)}  # type: ignore[arg-type]


def _upsert_user(
    db,
    *,
    name: str,
    login_id: str,
    password: str,
    site_id: int,
) -> User:
    user = db.query(User).filter(User.login_id == login_id).first()
    pw_hash = get_password_hash(password)
    if user is None:
        user = User(
            name=name,
            login_id=login_id,
            password_hash=pw_hash,
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=site_id,
            must_change_password=False,
            is_active=True,
        )
        db.add(user)
    else:
        user.name = name or user.name
        user.password_hash = pw_hash
        user.role = Role.SITE_FUNCTIONAL_EVAL
        user.ui_type = UIType.SITE
        user.site_id = site_id
        user.is_active = True
        user.must_change_password = False
    db.flush()
    return user


def _ensure_site(db, reg: FunctionalEvalSiteRegistry) -> Site:
    site = db.query(Site).filter(Site.site_code == reg.site_code).first()
    if site is None:
        site = Site(
            site_code=reg.site_code,
            site_name=reg.erp_site_label[:200],
            manager_name=reg.manager_name,
            status="ACTIVE",
        )
        db.add(site)
        db.flush()
    return site


def _clear_site_period_data(db, period_id: int, site_code: str) -> None:
    workers = (
        db.query(FunctionalEvalWorker)
        .filter(FunctionalEvalWorker.period_id == period_id, FunctionalEvalWorker.site_code == site_code)
        .all()
    )
    ids = [w.id for w in workers]
    if ids:
        db.query(FunctionalEvalAssessment).filter(FunctionalEvalAssessment.worker_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(FunctionalEvalAttendanceEntry).filter(
            FunctionalEvalAttendanceEntry.period_id == period_id,
            FunctionalEvalAttendanceEntry.site_code == site_code,
        ).delete(synchronize_session=False)
        db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id.in_(ids)).delete(synchronize_session=False)
    db.query(FunctionalEvalSiteApproval).filter(
        FunctionalEvalSiteApproval.period_id == period_id,
        FunctionalEvalSiteApproval.site_code == site_code,
    ).delete(synchronize_session=False)


def _save_assessments(db, worker_id: int, *, complete: bool) -> None:
    if not complete:
        return
    for eval_type in ("FUNCTIONAL", "SAFETY"):
        computed = compute_assessment(eval_type, _mid_scores(eval_type))  # type: ignore[arg-type]
        db.add(
            FunctionalEvalAssessment(
                worker_id=worker_id,
                eval_type=eval_type,
                scores_json=computed["scores"],
                total_score=computed["total_score"],
                max_score=computed["max_score"],
                grade_code=computed["grade_code"],
                grade_label=computed["grade_label"],
            )
        )


def _seed_cheongra(db, period: FunctionalEvalPeriod, reg: FunctionalEvalSiteRegistry) -> int:
    site = _ensure_site(db, reg)
    _upsert_user(db, name=reg.manager_name, login_id=CHEONGRA_MANAGER, password=CHEONGRA_MANAGER_PW, site_id=site.id)
    _upsert_user(db, name="김팀장", login_id=CHEONGRA_LEADER, password=CHEONGRA_LEADER_PW, site_id=site.id)
    _clear_site_period_data(db, period.id, CHEONGRA_CODE)

    batch = FunctionalEvalAttendanceImportBatch(
        period_id=period.id,
        work_date=WORK_DATE,
        original_filename="local_demo_attendance.xls",
        stored_path="storage/local_demo_attendance.xls",
        total_rows=CHEONGRA_TEAM + CHEONGRA_DIRECT,
        linked_workers=CHEONGRA_TEAM + CHEONGRA_DIRECT,
    )
    db.add(batch)
    db.flush()

    row_no = 1
    count = 0
    for i in range(CHEONGRA_TEAM):
        rrn = f"90010{i + 1:02d}1234567"
        w = FunctionalEvalWorker(
            period_id=period.id,
            site_code=CHEONGRA_CODE,
            site_name=reg.erp_site_label[:300],
            row_no=row_no,
            name=f"팀원{i + 1}",
            rrn_hash=_rrn_hash(rrn),
            rrn_masked=f"{rrn[:6]}-{rrn[6:]}",
            assigned_evaluator_login_id=CHEONGRA_LEADER,
            is_site_manager=False,
            is_active=True,
        )
        db.add(w)
        db.flush()
        db.add(
            FunctionalEvalAttendanceEntry(
                period_id=period.id,
                work_date=WORK_DATE,
                worker_id=w.id,
                site_code=CHEONGRA_CODE,
                rrn_hash=w.rrn_hash,
                name=w.name,
                rep_name="김팀장",
                batch_id=batch.id,
            )
        )
        row_no += 1
        count += 1

    for i in range(CHEONGRA_DIRECT):
        rrn = f"88020{i + 1:02d}1234567"
        w = FunctionalEvalWorker(
            period_id=period.id,
            site_code=CHEONGRA_CODE,
            site_name=reg.erp_site_label[:300],
            row_no=row_no,
            name=f"직영{i + 1}",
            rrn_hash=_rrn_hash(rrn),
            rrn_masked=f"{rrn[:6]}-{rrn[6:]}",
            assigned_evaluator_login_id=CHEONGRA_MANAGER,
            is_site_manager=False,
            is_active=True,
        )
        db.add(w)
        db.flush()
        db.add(
            FunctionalEvalAttendanceEntry(
                period_id=period.id,
                work_date=WORK_DATE,
                worker_id=w.id,
                site_code=CHEONGRA_CODE,
                rrn_hash=w.rrn_hash,
                name=w.name,
                batch_id=batch.id,
            )
        )
        row_no += 1
        count += 1
    return count


def _seed_other_site(db, period: FunctionalEvalPeriod, reg: FunctionalEvalSiteRegistry) -> int:
    site = _ensure_site(db, reg)
    manager_login = (reg.manager_login_id or reg.site_code).strip()
    manager_name = (reg.manager_name or "소장").strip()
    _upsert_user(db, name=manager_name, login_id=manager_login, password=DEFAULT_MANAGER_PW, site_id=site.id)
    _clear_site_period_data(db, period.id, reg.site_code)

    batch = FunctionalEvalAttendanceImportBatch(
        period_id=period.id,
        work_date=WORK_DATE,
        original_filename="local_demo_attendance.xls",
        stored_path="storage/local_demo_attendance.xls",
        total_rows=OTHER_WORKERS_PER_SITE,
        linked_workers=OTHER_WORKERS_PER_SITE,
    )
    db.add(batch)
    db.flush()

    count = 0
    for i in range(OTHER_WORKERS_PER_SITE):
        rrn = f"{reg.site_code[-4:]}{i + 1:02d}0101234567"
        w = FunctionalEvalWorker(
            period_id=period.id,
            site_code=reg.site_code,
            site_name=reg.erp_site_label[:300],
            row_no=i + 1,
            name=f"{reg.site_alias}근로{i + 1}",
            rrn_hash=_rrn_hash(rrn),
            rrn_masked=f"{rrn[:6]}-{rrn[6:]}",
            assigned_evaluator_login_id=manager_login,
            is_site_manager=False,
            is_active=True,
        )
        db.add(w)
        db.flush()
        db.add(
            FunctionalEvalAttendanceEntry(
                period_id=period.id,
                work_date=WORK_DATE,
                worker_id=w.id,
                site_code=reg.site_code,
                rrn_hash=w.rrn_hash,
                name=w.name,
                batch_id=batch.id,
            )
        )
        _save_assessments(db, w.id, complete=True)
        count += 1
    return count


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.is_active.is_(True)).first()
        if period is None:
            period = FunctionalEvalPeriod(
                title="기능인제 인사고과",
                deadline_date=date(2026, 12, 31),
                is_active=True,
            )
            db.add(period)
            db.flush()
        period.last_attendance_date = WORK_DATE
        period.deadline_date = date(2026, 12, 31)

        regs = db.query(FunctionalEvalSiteRegistry).order_by(FunctionalEvalSiteRegistry.site_code.asc()).all()
        if not regs:
            print("functional_eval_site_registry 가 비어 있습니다. 월별집계 xls를 먼저 반영하세요.")
            return

        cheongra_workers = 0
        other_sites = 0
        other_workers = 0

        for reg in regs:
            if reg.site_code == CHEONGRA_CODE:
                cheongra_workers = _seed_cheongra(db, period, reg)
            else:
                n = _seed_other_site(db, period, reg)
                other_sites += 1
                other_workers += n

        db.commit()
        print(f"period_id={period.id} work_date={WORK_DATE}")
        print(f"대우청라({CHEONGRA_CODE}): workers={cheongra_workers} - 미평가")
        print(f"  소장 {CHEONGRA_MANAGER} / {CHEONGRA_MANAGER_PW}")
        print(f"  팀장 {CHEONGRA_LEADER} / {CHEONGRA_LEADER_PW}")
        print(f"기타 현장: {other_sites}곳 x {OTHER_WORKERS_PER_SITE}명 = {other_workers}명 - 보통(B) 완료")
        print(f"  (기타 현장 소장 PW: {DEFAULT_MANAGER_PW})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
