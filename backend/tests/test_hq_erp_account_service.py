from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.sites import models as site_models  # noqa: F401
from app.modules.users import hq_erp_account_service as service
from app.modules.users.models import User
from app.modules.workers import models as worker_models  # noqa: F401
from app.modules.sites.latest_sync import is_current_missing_site, site_attrs


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            site_models.Site.__table__,
            worker_models.Person.__table__,
            worker_models.Employment.__table__,
            User.__table__,
        ],
    )
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def employee_row(
    name: str,
    *,
    department_code: str,
    erp_login_id: str,
    birth6: str = "790808",
) -> dict:
    return {
        "name": name,
        "department_code": department_code,
        "department": service.DEPARTMENT_LABELS[department_code],
        "position": "차장",
        "position_code": "5",
        "email": None,
        "birth6": birth6,
        "birth_date": date(1979, 8, 8),
        "rrn_hash": f"hash-{name}",
        "employee_code": "100",
        "erp_login_id": erp_login_id,
        "termination_date": None,
    }


def test_plan_links_dedicated_safety_account_and_keeps_legacy_login(db, monkeypatch):
    db.add_all(
        [
            User(
                name="정상익",
                login_id="hq01",
                password_hash="x",
                role=Role.ACCIDENT_ADMIN,
                ui_type=UIType.HQ_SAFE,
                department="안전보건실",
                is_active=True,
            ),
            User(
                name="정상익",
                login_id="안전보건-정상익",
                password_hash="x",
                role=Role.HQ_SAFE,
                ui_type=UIType.HQ_SAFE,
                department="안전보건실(차장)",
                is_active=True,
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(
        service,
        "load_viewer_rows_from_path",
        lambda _path: (
            [
                employee_row(
                    "정상익",
                    department_code="04",
                    erp_login_id="erp-normal",
                )
            ],
            "employees.xls",
        ),
    )

    plans, excluded, _rows, _label = service.build_account_plan(
        db, Path("employees.xls")
    )

    assert excluded == []
    assert len(plans) == 1
    assert plans[0].action == "LINK_LEGACY_ACCOUNT"
    assert plans[0].target is not None
    assert plans[0].target.login_id == "안전보건-정상익"
    assert plans[0].role == Role.HQ_SAFE


def test_plan_creates_hq_account_when_only_site_account_has_same_name(db, monkeypatch):
    db.add(
        User(
            name="김용갑",
            login_id="현장50-김용갑",
            password_hash="x",
            role=Role.SITE_FUNCTIONAL_EVAL,
            ui_type=UIType.SITE,
            site_id=None,
            is_active=True,
        )
    )
    db.commit()
    monkeypatch.setattr(
        service,
        "load_viewer_rows_from_path",
        lambda _path: (
            [
                employee_row(
                    "김용갑",
                    department_code="13",
                    erp_login_id="erp-pm",
                )
            ],
            "employees.xls",
        ),
    )

    plans, excluded, _rows, _label = service.build_account_plan(
        db, Path("employees.xls")
    )

    assert excluded == []
    assert plans[0].action == "CREATE"
    assert plans[0].role == Role.FUNCTIONAL_EVAL_VIEWER


def test_current_missing_site_includes_north_osan_and_excludes_completed():
    north_osan = {
        "현장코드": "26058",
        "현장명": "북오산자이리버블시티 전기공사",
        "주소": "오산시 내삼미동 905번지",
        "공사기간": "2026-07-09 ~ 2029-07-31",
        "소장": "홍길동",
        "공무": "김공무",
    }
    completed = {
        **north_osan,
        "현장코드": "22003",
        "공사기간": "2022-01-24 ~ 2025-11-10",
    }

    assert is_current_missing_site(north_osan, date(2026, 7, 28)) == (True, None)
    assert is_current_missing_site(completed, date(2026, 7, 28)) == (
        False,
        "COMPLETED",
    )
    attrs = site_attrs(north_osan)
    assert attrs["project_manager"] == "홍길동"
    assert attrs["site_manager"] == "김공무"
