"""아이디 자가 발급 API."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.security import get_password_hash, verify_password
from app.core.database import Base
from app.core.enums import Role, UIType
from app.modules.auth.account_issuance_models import AccountIssuanceLog  # noqa: F401
from app.modules.auth.routes import router as auth_router
from app.modules.functional_eval.models import FunctionalEvalPeriod, FunctionalEvalSiteRegistry, FunctionalEvalWorker
from app.modules.functional_eval.roster import hash_rrn
from app.modules.sites.models import Site  # noqa: F401
from app.modules.users.models import User  # noqa: F401
from app.modules.workers import models as worker_models  # noqa: F401


def _client(tmp_path: Path) -> tuple[TestClient, sessionmaker]:
    db_file = tmp_path / "issue.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    app = FastAPI()
    app.include_router(auth_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.core.auth import get_db as core_get_db

    app.dependency_overrides[core_get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def test_issue_site_accounts_for_manager(tmp_path: Path):
    client, SessionLocal = _client(tmp_path)
    db = SessionLocal()
    try:
        site = Site(site_code="24044", site_name="롯데효성", manager_name="김영호")
        db.add(site)
        db.flush()
        reg = FunctionalEvalSiteRegistry(
            site_code="24044",
            erp_site_label="롯데효성",
            site_alias="롯데효성",
            manager_name="김영호",
            manager_login_id="롯데효성-김영호",
            erp_headcount=10,
        )
        db.add(reg)
        period = FunctionalEvalPeriod(title="2026-06", deadline_date=date(2026, 6, 30))
        db.add(period)
        db.flush()
        db.add(
            FunctionalEvalWorker(
                period_id=period.id,
                site_code="24044",
                row_no=1,
                name="김영호",
                rrn_hash=hash_rrn("6403031234567"),
                rrn_masked="640303-1******",
                is_active=True,
                is_on_reference_roster=True,
                assigned_evaluator_login_id="롯데효성-김영호",
            )
        )
        db.commit()

        res = client.post(
            "/auth/issue-accounts",
            json={"scope": "site", "site_code": "24044", "name": "김영호", "birth6": "640303"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["scope"] == "site"
        assert any(a["login_id"] == "롯데효성-김영호" for a in body["accounts"])

        user = db.query(User).filter(User.login_id == "롯데효성-김영호").one()
        assert user.must_change_password is True
        assert user.initial_password_issued is True
        assert verify_password("640303", user.password_hash)
    finally:
        db.close()


def test_issue_accounts_generic_failure(tmp_path: Path):
    client, SessionLocal = _client(tmp_path)
    db = SessionLocal()
    try:
        res = client.post(
            "/auth/issue-accounts",
            json={"scope": "site", "site_code": "99999", "name": "없는사람", "birth6": "000000"},
        )
        assert res.status_code == 400
        assert "일치하는 계정" in res.json()["detail"]
    finally:
        db.close()


def test_issue_hq_account(tmp_path: Path):
    client, SessionLocal = _client(tmp_path)
    db = SessionLocal()
    try:
        db.add(
            User(
                name="조동문",
                login_id="안전보건-조동문",
                password_hash=get_password_hash("old"),
                role=Role.HQ_SAFE,
                ui_type=UIType.HQ_SAFE,
                department="안전보건실(전무)",
                must_change_password=False,
                is_active=True,
            )
        )
        db.commit()

        res = client.post(
            "/auth/issue-accounts",
            json={"scope": "hq", "name": "조동문", "birth6": "600321"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["accounts"][0]["login_id"] == "안전보건-조동문"
        user = db.query(User).filter(User.login_id == "안전보건-조동문").one()
        assert user.must_change_password is True
        assert verify_password("600321", user.password_hash)
    finally:
        db.close()
