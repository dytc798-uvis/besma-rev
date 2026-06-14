"""출역 기준 평가 · 퇴사자 기록 유지 · 재출역 시 이력 복원."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.functional_eval.attendance import ParsedAttendanceRow
from app.modules.functional_eval.eval_provisioning import apply_attendance_report_diff
from app.modules.functional_eval.models import (
    FunctionalEvalAssessment,
    FunctionalEvalPeriod,
    FunctionalEvalSiteRegistry,
    FunctionalEvalWorker,
)
from app.modules.functional_eval.roster import parse_daily_roster_xlsx
from app.modules.functional_eval.service import apply_daily_roster_diff


def _rrn_hash(digits: str) -> str:
    return hashlib.sha256(digits.encode()).hexdigest()


def _write_roster_xlsx(path: Path, rows: list[tuple]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["성   명", "주민번호", "노임단가", "입사일", "퇴사일", "외국인", "직종", "소속현장코드"])
    for row in rows:
        ws.append(list(row))
    wb.save(path)


@pytest.fixture()
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'persist.db'}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = Session()
    period = FunctionalEvalPeriod(title="t", deadline_date=date(2026, 12, 31), is_active=True)
    session.add(period)
    session.flush()
    session.add(
        FunctionalEvalSiteRegistry(
            site_code="24025",
            erp_site_label="[1.대우건설] 청라C18BL",
            site_alias="대우청라",
            manager_name="박명식",
            manager_login_id="대우청라-박명식",
            erp_headcount=10,
        )
    )
    session.commit()
    yield session, period, tmp_path
    session.close()


def _attendance_row(*, work_date: date, name: str, rrn: str) -> ParsedAttendanceRow:
    digits = rrn.replace("-", "")
    return ParsedAttendanceRow(
        work_date=work_date,
        name=name,
        rrn_raw=digits,
        rrn_hash=_rrn_hash(digits),
        rrn_masked=None,
        job_name="6",
        rep_name="박명식",
        erp_site_label="[1.대우건설] 청라C18BL",
    )


def test_roster_diff_does_not_deactivate_attendance_only_worker(db_session):
    session, period, tmp_path = db_session
    rrn = "900101-1234567"
    apply_attendance_report_diff(
        session,
        period,
        [_attendance_row(work_date=date(2026, 6, 10), name="출역근로", rrn=rrn)],
        original_filename="att.xlsx",
        stored_path="storage/att.xlsx",
    )
    worker = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.name == "출역근로").first()
    assert worker is not None
    assert worker.is_on_reference_roster is False
    assert worker.is_active is True

    path = tmp_path / "empty_roster.xlsx"
    _write_roster_xlsx(path, [("다른사람", "850505-2234567", "", "", "", "", "6", "24025")])
    apply_daily_roster_diff(
        session,
        period,
        parse_daily_roster_xlsx(path),
        original_filename="roster.xlsx",
        stored_path=str(path),
    )

    session.refresh(worker)
    assert worker.is_active is True
    assert worker.removed_at is None


def test_re_attendance_reactivates_worker_and_preserves_assessment(db_session):
    session, period, _tmp_path = db_session
    rrn = "900101-1234567"
    work_date = date(2026, 6, 10)

    apply_attendance_report_diff(
        session,
        period,
        [_attendance_row(work_date=work_date, name="복귀근로", rrn=rrn)],
        original_filename="att1.xlsx",
        stored_path="storage/att1.xlsx",
    )
    worker = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.name == "복귀근로").first()
    assert worker is not None
    worker_id = worker.id

    session.add(
        FunctionalEvalAssessment(
            worker_id=worker_id,
            eval_type="FUNCTIONAL",
            scores_json={"A1": "5"},
            total_score=100,
            max_score=100,
            grade_code="S",
            grade_label="S",
        )
    )
    worker.is_active = False
    worker.removed_at = worker.updated_at
    session.commit()

    apply_attendance_report_diff(
        session,
        period,
        [_attendance_row(work_date=date(2026, 6, 15), name="복귀근로", rrn=rrn)],
        original_filename="att2.xlsx",
        stored_path="storage/att2.xlsx",
    )

    session.refresh(worker)
    assert worker.id == worker_id
    assert worker.is_active is True
    assert worker.removed_at is None

    assessment = (
        session.query(FunctionalEvalAssessment)
        .filter(
            FunctionalEvalAssessment.worker_id == worker_id,
            FunctionalEvalAssessment.eval_type == "FUNCTIONAL",
        )
        .first()
    )
    assert assessment is not None
    assert assessment.grade_code == "S"
