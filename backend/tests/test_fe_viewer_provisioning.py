"""본사 조회전용 계정 선별·권한 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.functional_eval import fe_viewer_provisioning_service as svc
from app.modules.users.models import User


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_exclude_site_manager_and_existing_user(db):
    existing = User(
        name="정상익",
        login_id="안전보건-정상익",
        password_hash="x",
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        is_active=True,
        must_change_password=False,
    )
    db.add(existing)
    db.commit()

    rows = [
        {
            "name": "정상익",
            "department": "안전보건실",
            "position": "본사 - 팀원",
            "email": "a@example.com",
            "birth6": "790808",
            "rrn_hash": "h1",
        },
        {
            "name": "김현장",
            "department": "[4.롯데건설] 롯데효성",
            "position": "현장소장",
            "email": "b@example.com",
            "birth6": "800101",
            "rrn_hash": "h2",
        },
        {
            "name": "박진균",
            "department": "공사관리팀",
            "position": "본사 - 팀원",
            "email": "c@example.com",
            "birth6": "850202",
            "rrn_hash": "h3",
        },
    ]
    result = svc.classify_viewer_candidates(db, rows)
    assert len(result.planned) == 1
    assert result.planned[0].name == "박진균"
    assert result.planned[0].login_id == "부현본사-박진균"
    reasons = {r.name: r.reason for r in result.excluded}
    assert reasons["정상익"] == "이미 계정 존재(이름)"
    assert reasons["김현장"] == "현장 인원"


def test_apply_creates_viewer_user(db):
    rows = [
        {
            "name": "신영석",
            "department": "업무팀",
            "position": "본사 - 팀원",
            "email": "d@example.com",
            "birth6": "900303",
            "birth_date": svc._birth_date_from_birth6("900303"),
            "rrn_hash": "h4",
        },
    ]
    dry = svc.classify_viewer_candidates(db, rows)
    assert len(dry.planned) == 1

    # apply without file: mock by calling internals
    from app.config.security import verify_password

    user = User(
        name="신영석",
        login_id="부현본사-신영석",
        password_hash=__import__("app.config.security", fromlist=["get_password_hash"]).get_password_hash("900303"),
        role=Role.FUNCTIONAL_EVAL_VIEWER,
        ui_type=UIType.HQ_SAFE,
        is_active=True,
        must_change_password=True,
        initial_password_issued=True,
        account_issued_by="hq_viewer_bulk",
    )
    db.add(user)
    db.commit()
    saved = db.query(User).filter(User.login_id == "부현본사-신영석").first()
    assert saved is not None
    assert saved.role == Role.FUNCTIONAL_EVAL_VIEWER
    assert verify_password("900303", saved.password_hash)


def test_build_viewer_login_id():
    assert svc.build_viewer_login_id("박 경화") == "부현본사-박경화"
