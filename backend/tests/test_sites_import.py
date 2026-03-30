from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.modules.sites.models import Site
from app.modules.sites.service import (
    parse_amount,
    parse_construction_period,
    parse_gross_area,
    parse_int_from_text,
    upsert_site_from_row,
)
from app.modules.users.models import User


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # import models so that Base.metadata has all tables
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        site = Site(site_code="S1", site_name="S1")
        session.add(site)
        session.commit()
        user = User(id=1, name="tester", login_id="tester", password_hash="x", site_id=site.id)
        session.add(user)
        session.commit()
        yield session
    finally:
        session.close()


def test_parse_construction_period():
    s, e = parse_construction_period("2022-01-24 ~ 2025-11-10")
    assert s == date(2022, 1, 24)
    assert e == date(2025, 11, 10)

    s, e = parse_construction_period("-")
    assert s is None and e is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1개동", 1),
        ("지하3층", 3),
        ("지상49층", 49),
        ("629세대", 629),
        ("-", None),
        ("", None),
    ],
)
def test_parse_int_from_text(value, expected):
    assert parse_int_from_text(value) == expected


def test_parse_gross_area():
    amount, unit = parse_gross_area("46,155PY")
    assert amount == 46155
    assert unit == "PY"

    amount, unit = parse_gross_area("-")
    assert amount is None and unit is None


def test_parse_amount():
    assert parse_amount("6,829,000,000") == 6829000000
    assert parse_amount("-") is None


def test_upsert_site_created_and_updated(db):
    user = db.query(User).first()

    row = {
        "site_code": "NEW01",
        "site_name": "신규공사",
        "construction_period": "2022-01-24 ~ 2025-11-10",
        "project_amount": "6,829,000,000",
        "building_count": "1개동",
        "floor_underground": "지하3층",
        "floor_ground": "지상49층",
        "household_count": "629세대",
        "gross_area_raw": "46,155PY",
        "project_manager": "소장A",
    }

    site, created = upsert_site_from_row(db, row, user)
    assert created is True
    db.commit()

    fetched = db.query(Site).filter(Site.site_code == "NEW01").first()
    assert fetched is not None
    assert fetched.created_by_user_id == user.id
    assert fetched.updated_by_user_id == user.id
    assert fetched.project_amount == 6829000000
    assert fetched.building_count == 1
    assert fetched.floor_underground == 3
    assert fetched.floor_ground == 49
    assert fetched.household_count == 629
    assert fetched.gross_area == 46155
    assert fetched.gross_area_unit == "PY"

    # update path
    row2 = dict(row)
    row2["project_amount"] = "7,000,000,000"
    site2, created2 = upsert_site_from_row(db, row2, user)
    assert created2 is False
    db.commit()
    fetched2 = db.query(Site).filter(Site.site_code == "NEW01").first()
    assert fetched2.project_amount == 7000000000
    assert fetched2.created_by_user_id == user.id
    assert fetched2.updated_by_user_id == user.id

