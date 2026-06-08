from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.functional_eval.eval_catalog import compute_assessment, get_criteria
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalWorker
from app.modules.functional_eval.service import apply_daily_roster_diff, resequence_site_row_numbers


def _write_roster_xlsx(path: Path, rows: list[tuple]) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["성   명", "주민번호", "노임단가", "입사일", "퇴사일", "외국인", "직종", "소속현장코드"])
    for row in rows:
        ws.append(list(row))
    wb.save(path)


@pytest.fixture()
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fe.db'}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = Session()
    period = FunctionalEvalPeriod(title="t", deadline_date=date(2026, 12, 31), is_active=True)
    session.add(period)
    session.commit()
    yield session, period, tmp_path
    session.close()


def test_roster_apply_assigns_sequential_row_numbers(db_session):
    session, period, tmp_path = db_session
    path = tmp_path / "r.xlsx"
    _write_roster_xlsx(
        path,
        [
            ("가", "900101-1234567", "", "", "", "", "6", "26025"),
            ("나", "900102-1234567", "", "", "", "", "6", "26025"),
            ("다", "900103-1234567", "", "", "", "", "6", "26025"),
        ],
    )
    from app.modules.functional_eval.roster import parse_daily_roster_xlsx

    parsed = parse_daily_roster_xlsx(path)
    apply_daily_roster_diff(session, period, parsed, original_filename="r.xlsx", stored_path=str(path))
    workers = (
        session.query(FunctionalEvalWorker)
        .filter(FunctionalEvalWorker.site_code == "26025")
        .order_by(FunctionalEvalWorker.row_no.asc())
        .all()
    )
    assert [w.row_no for w in workers] == [1, 2, 3]


def test_resequence_fixes_duplicate_row_numbers(db_session):
    session, period, tmp_path = db_session
    for name, rrn in [("가", "a1"), ("나", "a2")]:
        session.add(
            FunctionalEvalWorker(
                period_id=period.id,
                site_code="26025",
                row_no=1,
                name=name,
                rrn_hash=rrn,
                is_active=True,
            )
        )
    session.commit()
    resequence_site_row_numbers(session, period.id, "26025")
    session.commit()
    workers = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.site_code == "26025").all()
    assert sorted(w.row_no for w in workers) == [1, 2]


def test_compute_assessment_requires_all_criteria():
    criteria = get_criteria("FUNCTIONAL")
    assert len(criteria) >= 1
    scores = {c["id"]: c["grades"][0]["key"] for c in criteria}
    result = compute_assessment("FUNCTIONAL", scores)
    assert result["total_score"] > 0
    assert result["grade_code"] in {"S", "A", "B", "C"}
