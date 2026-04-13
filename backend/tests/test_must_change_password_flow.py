from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.security import get_password_hash, verify_password
from app.core.database import Base
from app.modules.sites import models as site_models  # noqa: F401
from app.modules.workers import models as worker_models  # noqa: F401
from app.modules.auth.routes import router as auth_router
from app.modules.users.routes import router as users_router
from app.modules.users.models import User
from app.core.enums import Role, UIType


def test_must_change_password_forces_password_update(tmp_path: Path):
    db_file = tmp_path / "test_must_change_password.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    user = User(
        name="admin",
        login_id="admin1",
        password_hash=get_password_hash("InitP@ssw0rd!"),
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        site_id=None,
        person_id=None,
        must_change_password=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token_user_id = user.id
    session.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(users_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.core.auth import get_db as core_get_db  # noqa: WPS433

    app.dependency_overrides[core_get_db] = override_get_db

    client = TestClient(app)

    login_res = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "InitP@ssw0rd!"},
    )
    assert login_res.status_code == 200
    body = login_res.json()
    assert body["must_change_password"] is True
    token = body["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["must_change_password"] is True

    users_me_res = client.get("/users/me", headers=headers)
    assert users_me_res.status_code == 403
    assert users_me_res.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"

    short = client.post(
        "/auth/change-password",
        headers=headers,
        json={
            "current_password": "InitP@ssw0rd!",
            "new_password": "abc",
            "new_password_confirm": "abc",
        },
    )
    assert short.status_code == 400
    assert short.json()["detail"] == "비밀번호는 4자리 이상이어야 합니다."

    mismatch = client.post(
        "/auth/change-password",
        headers=headers,
        json={
            "current_password": "InitP@ssw0rd!",
            "new_password": "abcd",
            "new_password_confirm": "abce",
        },
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"] == "NEW_PASSWORD_CONFIRM_MISMATCH"

    wrong_cur = client.post(
        "/auth/change-password",
        headers=headers,
        json={
            "current_password": "wrong",
            "new_password": "abcd",
            "new_password_confirm": "abcd",
        },
    )
    assert wrong_cur.status_code == 400
    assert wrong_cur.json()["detail"] == "CURRENT_PASSWORD_INCORRECT"

    change_res = client.post(
        "/auth/change-password",
        headers=headers,
        json={
            "current_password": "InitP@ssw0rd!",
            "new_password": "abcd",
            "new_password_confirm": "abcd",
        },
    )
    assert change_res.status_code == 200
    assert change_res.json()["result"] == "ok"

    db = TestingSessionLocal()
    row = db.query(User).filter(User.id == token_user_id).first()
    assert row is not None
    assert row.must_change_password is False
    assert row.password_changed_at is not None
    db.close()

    users_me_res2 = client.get("/users/me", headers=headers)
    assert users_me_res2.status_code == 200
    assert users_me_res2.json()["must_change_password"] is False
    assert users_me_res2.json()["id"] == token_user_id


def test_change_password_rejects_blank_new_password(tmp_path: Path):
    db_file = tmp_path / "test_blank_new_pw.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    user = User(
        name="u",
        login_id="u1",
        password_hash=get_password_hash("old"),
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        site_id=None,
        person_id=None,
        must_change_password=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()

    app = FastAPI()
    app.include_router(auth_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.core.auth import get_db as core_get_db  # noqa: WPS433

    app.dependency_overrides[core_get_db] = override_get_db

    client = TestClient(app)
    login_res = client.post("/auth/login", data={"username": "u1", "password": "old"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    bad = client.post(
        "/auth/change-password",
        headers=headers,
        json={"current_password": "old", "new_password": "   ", "new_password_confirm": "   "},
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "NEW_PASSWORD_REQUIRED"


def test_admin_reset_password_sets_must_change(tmp_path: Path):
    db_file = tmp_path / "test_admin_reset_pw.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    s = TestingSessionLocal()
    admin = User(
        name="hq",
        login_id="hq1",
        password_hash=get_password_hash("hqpass"),
        role=Role.HQ_SAFE,
        ui_type=UIType.HQ_SAFE,
        site_id=None,
        person_id=None,
        must_change_password=False,
    )
    target = User(
        name="site",
        login_id="site1",
        password_hash=get_password_hash("oldsite"),
        role=Role.SITE,
        ui_type=UIType.SITE,
        site_id=None,
        person_id=None,
        must_change_password=False,
    )
    s.add_all([admin, target])
    s.commit()
    s.refresh(target)
    target_id = target.id
    s.close()

    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(users_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.core.auth import get_db as core_get_db  # noqa: WPS433

    app.dependency_overrides[core_get_db] = override_get_db

    client = TestClient(app)
    login = client.post("/auth/login", data={"username": "hq1", "password": "hqpass"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    reset = client.post(f"/users/{target_id}/admin-reset-password", headers=headers)
    assert reset.status_code == 200
    temp = reset.json()["temporary_password"]
    assert len(temp) >= 4

    s2 = TestingSessionLocal()
    t2 = s2.query(User).filter(User.id == target_id).first()
    assert t2 is not None
    assert t2.must_change_password is True
    assert verify_password(temp, t2.password_hash)
    s2.close()

    login2 = client.post("/auth/login", data={"username": "site1", "password": temp})
    assert login2.status_code == 200
    assert login2.json()["must_change_password"] is True
