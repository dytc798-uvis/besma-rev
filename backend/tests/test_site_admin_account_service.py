from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.new_site_deployment import models as deployment_models
from app.modules.sites import models as site_models
from app.modules.users import site_admin_account_service as service
from app.modules.users.models import User
from app.modules.workers import models as worker_models


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            site_models.Site.__table__,
            worker_models.Person.__table__,
            User.__table__,
            deployment_models.NewSiteDeployment.__table__,
            deployment_models.NewSiteDeploymentAdministrator.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _employee(name: str, position_code: str, birth6: str) -> dict:
    return {
        "name": name,
        "position_code": position_code,
        "birth6": birth6,
        "birth_date": date(1980, 1, 1),
        "rrn_hash": f"hash-{name}",
        "termination_date": None,
    }


def _sources(monkeypatch):
    monkeypatch.setattr(
        service,
        "load_site_rows",
        lambda _path: [
            {
                "현장코드": "26001",
                "현장명": "테스트 현장",
                "도급사명": "부현전기",
                "공사기간": "2026-01-01 ~ 2027-12-31",
                "소장": "김소장",
                "공무": "박공무",
                "기타": "이안전",
            }
        ],
    )
    monkeypatch.setattr(
        service,
        "load_viewer_rows_from_path",
        lambda _path: (
            [
                _employee("김소장", "9", "800101"),
                _employee("박공무", "19", "810202"),
                _employee("이안전", "22", "820303"),
            ],
            "employees.xls",
        ),
    )
    monkeypatch.setattr(
        service,
        "derive_deployment_site_alias",
        lambda _contractor, _site_name: "테스트",
    )


def test_plan_includes_manager_gongmu_and_safety(db, monkeypatch):
    _sources(monkeypatch)
    db.add(site_models.Site(site_code="26001", site_name="테스트 현장"))
    db.commit()

    plans, excluded = service.build_site_admin_plan(
        db,
        site_source=Path("sites.xls"),
        employee_source=Path("employees.xls"),
        as_of=date(2026, 7, 28),
    )

    assert excluded == []
    assert {plan.name for plan in plans} == {"김소장", "박공무", "이안전"}
    assert {plan.name: plan.admin_role for plan in plans} == {
        "김소장": "SITE_MANAGER",
        "박공무": "GONGMU",
        "이안전": "SAFETY",
    }


def test_apply_preserves_changed_password_and_assigns_site_roles(db, monkeypatch):
    _sources(monkeypatch)
    site = site_models.Site(site_code="26001", site_name="테스트 현장")
    db.add(site)
    db.flush()
    existing = User(
        name="박공무",
        login_id="테스트-박공무",
        password_hash="changed-password",
        role=Role.SITE,
        ui_type=UIType.SITE,
        site_id=site.id,
        is_active=True,
        must_change_password=False,
        password_changed_at=datetime(2026, 7, 1),
    )
    db.add(existing)
    db.commit()

    result = service.apply_site_admin_plan(
        db,
        site_source=Path("sites.xls"),
        employee_source=Path("employees.xls"),
        as_of=date(2026, 7, 28),
    )

    users = {user.name: user for user in db.query(User).all()}
    assert result["created_count"] == 2
    assert result["updated_count"] == 1
    assert users["김소장"].role == Role.SITE_FUNCTIONAL_EVAL
    assert users["박공무"].role == Role.SITE
    assert users["이안전"].role == Role.SITE
    assert users["박공무"].password_hash == "changed-password"
    assert users["박공무"].must_change_password is False
