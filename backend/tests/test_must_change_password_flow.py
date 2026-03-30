from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.security import get_password_hash
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

    # Override get_db via importing the symbol used in app.core.auth.
    from app.core.auth import get_db as core_get_db  # noqa: WPS433

    app.dependency_overrides[core_get_db] = override_get_db

    client = TestClient(app)

    # 1) Login succeeds and must_change_password is returned.
    login_res = client.post(
        "/auth/login",
        data={"username": "admin1", "password": "InitP@ssw0rd!"},
    )
    assert login_res.status_code == 200
    body = login_res.json()
    assert body["must_change_password"] is True
    token = body["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 2) /auth/me is exempt and must return even before password change.
    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["must_change_password"] is True

    # 3) A protected endpoint should be blocked until password change.
    users_me_res = client.get("/users/me", headers=headers)
    assert users_me_res.status_code == 403
    assert users_me_res.json()["detail"] == "PASSWORD_CHANGE_REQUIRED"

    # 4) Change password.
    change_res = client.post(
        "/auth/change-password",
        headers=headers,
        json={
            "current_password": "InitP@ssw0rd!",
            "new_password": "NewP@ssw0rd!23",
        },
    )
    assert change_res.status_code == 200
    assert change_res.json()["result"] == "ok"

    # 5) After change: /users/me allowed.
    users_me_res2 = client.get("/users/me", headers=headers)
    assert users_me_res2.status_code == 200
    assert users_me_res2.json()["must_change_password"] is False

    assert users_me_res2.json()["id"] == token_user_id

