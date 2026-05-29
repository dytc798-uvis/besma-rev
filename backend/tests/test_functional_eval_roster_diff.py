from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalWorker
from app.modules.functional_eval.roster import parse_daily_roster_xlsx
from app.modules.functional_eval.service import apply_daily_roster_diff, diff_daily_roster_file


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
    engine = create_engine(f"sqlite:///{tmp_path / 'roster.db'}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = Session()
    period = FunctionalEvalPeriod(title="t", deadline_date=date(2026, 12, 31), is_active=True)
    session.add(period)
    session.commit()
    yield session, period, tmp_path
    session.close()


def test_roster_diff_new_update_remove(db_session):
    session, period, tmp_path = db_session
    path1 = tmp_path / "r1.xlsx"
    _write_roster_xlsx(
        path1,
        [
            ("김철수", "900101-1234567", "", "", "", "", "6", "10001"),
            ("이영희", "850505-2234567", "", "", "", "", "6", "10001"),
        ],
    )
    parsed1 = parse_daily_roster_xlsx(path1)
    apply_daily_roster_diff(session, period, parsed1, original_filename="r1.xlsx", stored_path=str(path1))
    assert session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.is_active.is_(True)).count() == 2

    path2 = tmp_path / "r2.xlsx"
    _write_roster_xlsx(
        path2,
        [
            ("김철수", "900101-1234567", "", "", "", "", "6", "10002"),
            ("박민수", "880808-3234567", "", "", "", "", "6", "10001"),
        ],
    )
    diff = diff_daily_roster_file(session, period, path2)
    assert diff["new_count"] == 1
    assert diff["removed_count"] == 1
    assert diff["updated_count"] == 1

    apply_daily_roster_diff(session, period, parse_daily_roster_xlsx(path2), original_filename="r2.xlsx", stored_path=str(path2))
    active = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.is_active.is_(True)).all()
    assert len(active) == 2
    kim = next(w for w in active if w.name == "김철수")
    assert kim.site_code == "10002"
    removed = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.name == "이영희").first()
    assert removed is not None
    assert removed.is_active is False


def test_sanction_preserved_after_roster_reapply(db_session):
    session, period, tmp_path = db_session
    path = tmp_path / "r.xlsx"
    _write_roster_xlsx(path, [("홍길동", "900101-1234567", "", "", "", "", "6", "24018")])
    parsed = parse_daily_roster_xlsx(path)
    apply_daily_roster_diff(session, period, parsed, original_filename="r.xlsx", stored_path=str(path))
    worker = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.name == "홍길동").first()
    assert worker is not None
    worker_id = worker.id

    apply_daily_roster_diff(session, period, parsed, original_filename="r2.xlsx", stored_path=str(path))
    worker2 = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.rrn_hash == worker.rrn_hash).first()
    assert worker2 is not None
    assert worker2.id == worker_id
