from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.security import get_password_hash, verify_password
from app.core.auth import get_current_user, get_db
from app.core.database import Base
from app.core.datetime_utils import utc_now
from app.core.enums import Role, UIType
from app.modules.account_requests.models import AccountAccessRequest, AccountAccessRequestEvent
from app.modules.account_requests.routes import router as account_requests_router
from app.modules.auth.account_issuance_models import AccountIssuanceLog
from app.modules.auth.routes import router as auth_router
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Person


def _payload(**overrides):
    value = {
        "name": "신규신청자",
        "phone_mobile": "010-1234-5678",
        "company_name": "부현전기",
        "scope": "HQ",
        "department": "예산견적팀",
        "request_reason": "예산견적 업무 수행을 위한 계정 신청",
        "employment_evidence_note": "재직 확인 필요",
        "privacy_consent": True,
    }
    value.update(overrides)
    return value


def test_account_request_workflow_and_existing_find(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'account_requests.db'}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(
        engine,
        tables=[
            Person.__table__,
            Site.__table__,
            User.__table__,
            AccountIssuanceLog.__table__,
            AccountAccessRequest.__table__,
            AccountAccessRequestEvent.__table__,
        ],
    )
    db = SessionLocal()
    admin = User(
        id=1,
        name="승인관리자",
        login_id="approval-admin",
        password_hash=get_password_hash("admin-password"),
        role=Role.HQ_SAFE_ADMIN,
        ui_type=UIType.HQ_SAFE,
        is_active=True,
        must_change_password=False,
    )
    existing_person = Person(
        id=1,
        name="기존직원",
        birth_date=date(1990, 1, 2),
        phone_mobile="01099998888",
    )
    existing = User(
        id=2,
        name="기존직원",
        login_id="legacy-existing",
        password_hash=get_password_hash("existing-password"),
        birth_date=date(1990, 1, 2),
        department="안전보건실",
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        person_id=1,
        is_active=True,
        must_change_password=False,
    )
    viewer = User(
        id=3,
        name="일반조회자",
        login_id="viewer",
        password_hash=get_password_hash("viewer-password"),
        role=Role.FUNCTIONAL_EVAL_VIEWER,
        ui_type=UIType.HQ_SAFE,
        is_active=True,
        must_change_password=False,
    )
    site = Site(id=10, site_code="S-ACCOUNT-01", site_name="등록된 신청 현장", status="ACTIVE")
    db.add_all([admin, existing_person, existing, viewer, site])
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(account_requests_router)

    def override_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    current = {
        "user": SimpleNamespace(
            id=1,
            role=Role.HQ_SAFE_ADMIN,
            login_id="approval-admin",
            name="승인관리자",
            department=None,
            site_id=None,
        )
    }
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: current["user"]
    client = TestClient(app)

    options = client.get("/account-requests/public/options")
    assert options.status_code == 200
    assert "\uacf5\uc0ac\uad00\ub9ac1\ud300" in options.json()["departments"]["HQ"]
    assert "예산견적팀" in options.json()["departments"]["HQ"]
    assert "안전" in options.json()["departments"]["SITE"]
    assert options.json()["sites"] == [{"id": 10, "name": "등록된 신청 현장"}]
    assert "site_code" not in options.json()["sites"][0]

    found = client.post(
        "/auth/issue-accounts",
        json={
            "scope": "hq",
            "department": "안전보건실",
            "name": "기존직원",
            "birth6": "900102",
        },
    )
    assert found.status_code == 200
    assert found.json()["accounts"][0]["login_id"] == "legacy-existing"
    assert found.json()["accounts"][0]["initial_password"] is None
    with SessionLocal() as check:
        assert check.query(User).count() == 3

    submitted = client.post("/account-requests/public", json=_payload())
    assert submitted.status_code == 201
    request_no = submitted.json()["request_no"]
    assert submitted.json()["status"] == "REQUESTED"
    assert client.post("/account-requests/public", json=_payload()).status_code == 409
    site_submitted = client.post(
        "/account-requests/public",
        json=_payload(
            name="현장신청자",
            phone_mobile="010-4444-5555",
            scope="SITE",
            department="안전",
            site_id=10,
            request_reason="등록 현장 안전관리 계정 신청",
        ),
    )
    assert site_submitted.status_code == 201

    current["user"] = SimpleNamespace(
        id=3,
        role=Role.FUNCTIONAL_EVAL_VIEWER,
        login_id="viewer",
        name="일반조회자",
        department=None,
        site_id=None,
    )
    assert client.get("/account-requests/admin").status_code == 403

    current["user"] = SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE_ADMIN,
        login_id="approval-admin",
        name="승인관리자",
        department=None,
        site_id=None,
    )
    rows = client.get("/account-requests/admin").json()
    req = next(row for row in rows if row["request_no"] == request_no)
    assert req["phone_mobile_masked"] == "010-****-5678"
    approved = client.patch(
        f"/account-requests/admin/{req['id']}",
        json={"action": "APPROVE", "comment": "재직 확인 완료"},
    )
    assert approved.status_code == 200
    result = approved.json()
    assert result["item"]["status"] == "APPROVED"
    assert result["item"]["approved_role"] == "HQ_BUDGET_ESTIMATE"
    assert result["temporary_password"]
    assert result["temporary_password"] != "900102"
    assert result["temporary_password_expires_at"]

    with SessionLocal() as check:
        created = check.query(User).filter(User.id == result["item"]["created_account_user_id"]).one()
        assert created.login_id.startswith("besma-")
        assert created.must_change_password is True
        assert created.temporary_password_expires_at is not None
        assert verify_password(result["temporary_password"], created.password_hash)
        assert check.query(AccountAccessRequestEvent).count() >= 2
        site_request = (
            check.query(AccountAccessRequest)
            .filter(AccountAccessRequest.request_no == site_submitted.json()["request_no"])
            .one()
        )
        assert site_request.work_category == "SITE"
        assert site_request.site_id == 10
        assert site_request.site_code == "S-ACCOUNT-01"
        assert site_request.site_name == "등록된 신청 현장"

        created.temporary_password_expires_at = utc_now() - timedelta(minutes=1)
        check.commit()
    expired = client.post(
        "/auth/login",
        data={
            "username": result["temporary_login_id"],
            "password": result["temporary_password"],
        },
    )
    assert expired.status_code == 401
    assert expired.json()["detail"] == "TEMPORARY_PASSWORD_EXPIRED"

    public_reset = client.post(
        "/auth/reset-password-public",
        json={
            "name": "기존직원",
            "birth6": "900102",
            "erp_login_id": "legacy-existing",
            "new_password": "ShouldNotChange!123",
            "new_password_confirm": "ShouldNotChange!123",
        },
    )
    assert public_reset.status_code == 403
    assert public_reset.json()["detail"] == "PASSWORD_RESET_REQUIRES_ADMIN_APPROVAL"
    with SessionLocal() as check:
        unchanged = check.query(User).filter(User.id == 2).one()
        assert verify_password("existing-password", unchanged.password_hash)


def test_unmapped_category_waits_for_role_confirmation(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'unmapped.db'}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(
        engine,
        tables=[
            Person.__table__,
            Site.__table__,
            User.__table__,
            AccountAccessRequest.__table__,
            AccountAccessRequestEvent.__table__,
        ],
    )
    with SessionLocal() as db:
        admin = User(
            name="관리자",
            login_id="admin",
            password_hash="x",
            role=Role.HQ_SAFE_ADMIN,
            ui_type=UIType.HQ_SAFE,
            is_active=True,
            must_change_password=False,
        )
        db.add(admin)
        db.commit()
        admin_id = admin.id

    app = FastAPI()
    app.include_router(account_requests_router)
    app.dependency_overrides[get_db] = lambda: SessionLocal()
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=admin_id,
        role=Role.HQ_SAFE_ADMIN,
        login_id="admin",
        name="관리자",
        department=None,
        site_id=None,
    )
    client = TestClient(app)
    submitted = client.post(
        "/account-requests/public",
        json=_payload(
            department="업무팀",
            phone_mobile="01022223333",
        ),
    )
    assert submitted.status_code == 201
    req = client.get("/account-requests/admin").json()[0]
    assert req["recommended_role"] is None
    assert client.patch(f"/account-requests/admin/{req['id']}", json={"action": "APPROVE"}).status_code == 409
