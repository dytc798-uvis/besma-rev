from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry, FunctionalEvalWorker
from app.modules.functional_eval.roster import hash_rrn
from app.modules.functional_eval.team_leader_login import (
    collect_team_leader_evaluator_logins_deduped,
    reconcile_team_leader_assignments,
    resolve_canonical_team_leader_login,
)
from app.modules.sites.models import Site


@pytest.fixture()
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tl.db'}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = Session()
    period = FunctionalEvalPeriod(title="t", deadline_date=date(2099, 12, 31), is_active=True)
    session.add(period)
    session.flush()

    for code, alias, label in (
        ("25001", "신세계청라", "[2.신세계건설] 스타필드 청라 신축공사 전기공사"),
        ("25002", "신세계청라02", "[2.신세계건설] 스타필드 청라 소방전기공사 2공구"),
    ):
        session.add(Site(site_code=code, site_name=label, manager_name="소장"))
        session.add(
            FunctionalEvalSiteRegistry(
                site_code=code,
                erp_site_label=label,
                site_alias=alias,
                manager_name="소장",
                manager_login_id=f"{alias}-소장",
            )
        )
    session.commit()
    yield session, period
    session.close()


def _worker(session, period, site_code: str, name: str, evaluator: str) -> FunctionalEvalWorker:
    row = FunctionalEvalWorker(
        period_id=period.id,
        site_code=site_code,
        site_name=site_code,
        name=name,
        rrn_hash=hash_rrn(f"900101-1{name}"),
        rrn_masked="900101-1******",
        assigned_evaluator_login_id=evaluator,
    )
    session.add(row)
    session.flush()
    return row


def test_resolve_imjeongseok_to_cheongra_fire_site(db_session):
    session, period = db_session
    canonical = resolve_canonical_team_leader_login(
        session,
        site_code="25002",
        person_name="임정석",
        candidate_logins={"신세계청라-임정석", "신세계청라02-임정석"},
        period_id=period.id,
    )
    assert canonical == "신세계청라02-임정석"


def test_collect_team_leader_logins_deduped_by_name(db_session):
    session, period = db_session
    _worker(session, period, "25002", "김종오", "신세계청라02-임정석")
    _worker(session, period, "25002", "송신영", "신세계청라-임정석")
    session.commit()

    rows = session.query(FunctionalEvalWorker).filter(FunctionalEvalWorker.site_code == "25002").all()
    logins = collect_team_leader_evaluator_logins_deduped(
        session,
        rows,
        "신세계청라02-소장",
        site_code="25002",
        period_id=period.id,
    )
    assert logins == {"신세계청라02-임정석"}


def test_reconcile_updates_stale_assignment(db_session):
    session, period = db_session
    _worker(session, period, "25002", "김종오", "신세계청라02-임정석")
    stale = _worker(session, period, "25002", "송신영", "신세계청라-임정석")
    session.commit()

    changed = reconcile_team_leader_assignments(session, period, "25002")
    session.commit()

    assert changed == 1
    session.refresh(stale)
    assert stale.assigned_evaluator_login_id == "신세계청라02-임정석"
