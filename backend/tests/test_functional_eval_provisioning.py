from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.functional_eval.constants import TEAM_LEADER_SPLIT_THRESHOLD
from app.modules.functional_eval.eval_provisioning import (
    apply_attendance_report_file,
    apply_monthly_site_aggregate_file,
    normalize_erp_site_label,
)
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry
from app.modules.functional_eval.rep_name import is_person_rep_name, resolve_team_rep_name
from app.modules.functional_eval.site_alias import build_eval_login_id, derive_site_alias
from app.modules.functional_eval.site_aggregate import parse_monthly_site_aggregate
from app.modules.functional_eval.attendance import parse_attendance_report
from app.modules.sites.models import Site
from app.modules.users.models import User


@pytest.fixture()
def db_session(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'fe_prov.db'}", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    from app.modules.functional_eval import models as fe_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = Session()
    period = FunctionalEvalPeriod(title="t", deadline_date=date(2099, 12, 31), is_active=True)
    session.add(period)
    session.commit()
    yield session, period
    session.close()


def test_derive_site_alias_c18():
    name = "[1.대우건설] 청라C18BL 오피스텔 신축공사"
    assert derive_site_alias(name) == "대우청라"


def test_build_eval_login_id():
    assert build_eval_login_id("금호마곡", "이성영") == "금호마곡-이성영"


def test_parse_monthly_aggregate_sample():
    path = Path(__file__).resolve().parents[2] / "docs"
    files = list(path.glob("*20260604121607*.xls"))
    if not files:
        pytest.skip("월별현장별집계 sample not in docs/")
    rows = parse_monthly_site_aggregate(files[0])
    assert len(rows) >= 50
    c18 = next(r for r in rows if "C18BL" in r.erp_site_name)
    assert c18.site_code == "24025"
    assert c18.manager_name == "박명식"


def test_aggregate_and_attendance_flow(db_session):
    session, period = db_session
    docs = Path(__file__).resolve().parents[2] / "docs"
    agg = next(docs.glob("*20260604121607*.xls"), None)
    att = next(docs.glob("*20260604122302*.xls"), None)
    if not agg or not att:
        pytest.skip("sample xls files not in docs/")

    agg_result = apply_monthly_site_aggregate_file(session, period, agg, original_filename=agg.name)
    assert agg_result["site_count"] >= 50
    reg = session.query(FunctionalEvalSiteRegistry).filter(FunctionalEvalSiteRegistry.site_code == "24025").first()
    assert reg is not None
    assert reg.site_alias == "대우청라"
    assert reg.manager_login_id == "대우청라-박명식"

    att_result = apply_attendance_report_file(session, period, att, original_filename=att.name)
    assert att_result["linked_workers"] > 0
    assert att_result["created_accounts"] >= 1
    manager = session.query(User).filter(User.login_id == "대우청라-박명식").first()
    assert manager is not None
    assert manager.password_hash
    assert TEAM_LEADER_SPLIT_THRESHOLD == 10


def test_normalize_erp_label():
    assert normalize_erp_site_label("현장명: [1.대우건설] 청라C18BL") == "[1.대우건설] 청라C18BL"


def test_is_person_rep_name():
    assert is_person_rep_name("김철수")
    assert is_person_rep_name("박명식")
    assert not is_person_rep_name("올라이트라이프")
    assert not is_person_rep_name("한결아이앤씨")
    assert not is_person_rep_name("직영")
    assert not is_person_rep_name("")


def test_resolve_team_rep_name():
    assert resolve_team_rep_name("김철수", "박명식") == "김철수"
    assert resolve_team_rep_name("올라이트라이프", "박명식") == "박명식"
    assert resolve_team_rep_name("", "박명식") == "박명식"
    assert resolve_team_rep_name("박명식", "박명식") == "박명식"
