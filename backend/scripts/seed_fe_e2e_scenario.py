"""기능인제 E2E 시뮬레이션용 청라 C18(24025) 시나리오 시드.

Usage:
  cd backend && PYTHONPATH=. python scripts/seed_fe_e2e_scenario.py
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
from app.core.enums import Role, UIType  # noqa: E402
from app.modules.functional_eval import models as fe_models  # noqa: F401
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

SITE_CODE = "24025"
SITE_NAME = "[1.대우건설] 청라C18BL 오피스텔 신축공사"
SITE_ALIAS = "대우청라"
MANAGER_LOGIN = "대우청라-박명식"
MANAGER_PW = "661123"
LEADER_LOGIN = "대우청라-김팀장"
LEADER_PW = "750101"
TEAM_SIZE = 8
DIRECT_SIZE = 4


def _rrn_hash(digits: str) -> str:
    return hashlib.sha256(digits.encode()).hexdigest()


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
        user.name = name
        user.password_hash = pw_hash
        user.role = Role.SITE_FUNCTIONAL_EVAL
        user.ui_type = UIType.SITE
        user.site_id = site_id
        user.is_active = True
        user.must_change_password = False
    db.flush()
    return user


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        site = db.query(Site).filter(Site.site_code == SITE_CODE).first()
        if site is None:
            site = Site(
                site_code=SITE_CODE,
                site_name=SITE_NAME,
                start_date=date.today(),
                status="ACTIVE",
                manager_name="박명식",
            )
            db.add(site)
            db.flush()

        reg = db.query(FunctionalEvalSiteRegistry).filter(FunctionalEvalSiteRegistry.site_code == SITE_CODE).first()
        if reg is None:
            reg = FunctionalEvalSiteRegistry(
                site_code=SITE_CODE,
                site_alias=SITE_ALIAS,
                manager_name="박명식",
                manager_login_id=MANAGER_LOGIN,
                erp_site_label="청라C18",
            )
            db.add(reg)
        else:
            reg.site_alias = SITE_ALIAS
            reg.manager_name = "박명식"
            reg.manager_login_id = MANAGER_LOGIN

        period = db.query(FunctionalEvalPeriod).filter(FunctionalEvalPeriod.is_active.is_(True)).first()
        if period is None:
            period = FunctionalEvalPeriod(
                title="E2E 기능인제",
                deadline_date=date(2026, 12, 31),
                is_active=True,
            )
            db.add(period)
            db.flush()
        period.deadline_date = date(2026, 12, 31)

        _upsert_user(db, name="박명식", login_id=MANAGER_LOGIN, password=MANAGER_PW, site_id=site.id)
        _upsert_user(db, name="김팀장", login_id=LEADER_LOGIN, password=LEADER_PW, site_id=site.id)

        # 기존 E2E 근로자·평가·승인 초기화
        old_workers = (
            db.query(FunctionalEvalWorker)
            .filter(FunctionalEvalWorker.period_id == period.id, FunctionalEvalWorker.site_code == SITE_CODE)
            .all()
        )
        old_ids = [w.id for w in old_workers]
        if old_ids:
            db.query(FunctionalEvalAssessment).filter(FunctionalEvalAssessment.worker_id.in_(old_ids)).delete(
                synchronize_session=False
            )
            db.query(FunctionalEvalAttendanceEntry).filter(FunctionalEvalAttendanceEntry.worker_id.in_(old_ids)).delete(
                synchronize_session=False
            )
            db.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.id.in_(old_ids)).delete(synchronize_session=False)

        db.query(FunctionalEvalSiteApproval).filter(
            FunctionalEvalSiteApproval.period_id == period.id,
            FunctionalEvalSiteApproval.site_code == SITE_CODE,
        ).delete(synchronize_session=False)

        work_date = date(2026, 6, 4)
        batch = FunctionalEvalAttendanceImportBatch(
            period_id=period.id,
            work_date=work_date,
            original_filename="e2e_attendance.xls",
            stored_path="storage/e2e_attendance.xls",
            total_rows=TEAM_SIZE + DIRECT_SIZE,
            linked_workers=TEAM_SIZE + DIRECT_SIZE,
        )
        db.add(batch)
        db.flush()

        row_no = 1
        for i in range(TEAM_SIZE):
            rrn = f"90010{i + 1:02d}1234567"
            w = FunctionalEvalWorker(
                period_id=period.id,
                site_code=SITE_CODE,
                site_name=SITE_NAME,
                row_no=row_no,
                name=f"팀원{i + 1}",
                rrn_hash=_rrn_hash(rrn),
                rrn_masked=f"{rrn[:6]}-{rrn[6:]}",
                assigned_evaluator_login_id=LEADER_LOGIN,
                is_site_manager=False,
                is_active=True,
            )
            db.add(w)
            db.flush()
            db.add(
                FunctionalEvalAttendanceEntry(
                    period_id=period.id,
                    work_date=work_date,
                    worker_id=w.id,
                    site_code=SITE_CODE,
                    rrn_hash=w.rrn_hash,
                    name=w.name,
                    batch_id=batch.id,
                )
            )
            row_no += 1

        for i in range(DIRECT_SIZE):
            rrn = f"88020{i + 1:02d}1234567"
            w = FunctionalEvalWorker(
                period_id=period.id,
                site_code=SITE_CODE,
                site_name=SITE_NAME,
                row_no=row_no,
                name=f"직영{i + 1}",
                rrn_hash=_rrn_hash(rrn),
                rrn_masked=f"{rrn[:6]}-{rrn[6:]}",
                assigned_evaluator_login_id=MANAGER_LOGIN,
                is_site_manager=False,
                is_active=True,
            )
            db.add(w)
            db.flush()
            db.add(
                FunctionalEvalAttendanceEntry(
                    period_id=period.id,
                    work_date=work_date,
                    worker_id=w.id,
                    site_code=SITE_CODE,
                    rrn_hash=w.rrn_hash,
                    name=w.name,
                    batch_id=batch.id,
                )
            )
            row_no += 1

        period.last_attendance_date = work_date
        db.commit()

        total = TEAM_SIZE + DIRECT_SIZE
        print(f"seeded site={SITE_CODE} period={period.id} workers={total}")
        print(f"  manager {MANAGER_LOGIN} / {MANAGER_PW}")
        print(f"  leader  {LEADER_LOGIN} / {LEADER_PW}")
        print(f"  team={TEAM_SIZE} direct={DIRECT_SIZE} (split threshold 10)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
