"""기능인인정제 일일 진행현황 보고서 테스트."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.functional_eval import daily_report_service, service
from app.modules.functional_eval.daily_report_pdf import generate_daily_report_pdf
from app.modules.functional_eval.grade_inflation_guard import compute_grade_inflation_review
from app.modules.functional_eval.models import FunctionalEvalDailyReport, FunctionalEvalPeriod


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.settings.storage_root", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'fe_daily.db'}", connect_args={"check_same_thread": False})
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _seed_period(db) -> FunctionalEvalPeriod:
    period = FunctionalEvalPeriod(
        title="2026 상반기 기능인인정제",
        deadline_date=date(2026, 6, 30),
        is_active=True,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


def test_snapshot_zero_workers(db):
    period = _seed_period(db)
    snap = daily_report_service.build_daily_report_snapshot(db, period, report_date=date(2026, 6, 16))
    assert snap["summary"]["total_workers"] == 0
    assert snap["summary"]["completion_rate_pct"] == 0.0
    pdf = generate_daily_report_pdf(snap)
    assert len(pdf) > 500


def test_generate_and_duplicate_prevention(db):
    period = _seed_period(db)
    row1 = daily_report_service.generate_daily_report(db, period, report_date=date(2026, 6, 16), generated_by="system")
    assert row1.id
    assert Path(row1.report_path).is_file()
    row2 = daily_report_service.generate_daily_report(db, period, report_date=date(2026, 6, 16), generated_by="system")
    assert row2.id == row1.id


def test_manual_regenerate_increments_version(db):
    period = _seed_period(db)
    row1 = daily_report_service.generate_daily_report(db, period, report_date=date(2026, 6, 16), generated_by="manual")
    row2 = daily_report_service.generate_daily_report(
        db, period, report_date=date(2026, 6, 16), generated_by="manual", force=True
    )
    assert row2.id == row1.id
    assert row2.version == 2
    assert row2.regenerated_at is not None


def test_site_completion_rate_calculation():
    workers = [
        {"functional_assessment": {"is_complete": True, "grade_code": "S"}, "safety_assessment": {"is_complete": True, "grade_code": "A"}},
        {"functional_assessment": {"is_complete": True, "grade_code": "A"}, "safety_assessment": {"is_complete": False}},
    ]
    evaluated = sum(1 for w in workers if service._is_fully_evaluated(w))
    assert evaluated == 1
    rate = round(100.0 * evaluated / len(workers), 1)
    assert rate == 50.0


def test_functional_s_over_limit_flag():
    workers = []
    for _ in range(8):
        workers.append(
            {
                "functional_assessment": {"is_complete": True, "grade_code": "S"},
                "safety_assessment": {"is_complete": True, "grade_code": "S"},
            }
        )
    for _ in range(2):
        workers.append(
            {
                "functional_assessment": {"is_complete": True, "grade_code": "A"},
                "safety_assessment": {"is_complete": True, "grade_code": "A"},
            }
        )
    review = compute_grade_inflation_review(workers)
    assert review["s_over_limit"] is True


def test_safety_many_s_not_flagged_as_functional_over():
    workers = [
        {
            "functional_assessment": {"is_complete": True, "grade_code": "A"},
            "safety_assessment": {"is_complete": True, "grade_code": "S"},
        }
        for _ in range(10)
    ]
    review = compute_grade_inflation_review(workers)
    assert review["s_over_limit"] is False


def test_list_daily_reports_api_shape(db):
    period = _seed_period(db)
    daily_report_service.generate_daily_report(db, period, report_date=date(2026, 6, 16))
    items = daily_report_service.list_daily_reports(db, period)
    assert len(items) == 1
    assert items[0]["report_date"] == "2026-06-16"
    assert items[0]["has_document"] is True


def test_criteria_at_kst_label():
    assert daily_report_service.criteria_at_kst_label(date(2026, 6, 16)) == "2026-06-16 21:00 KST"
