from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user, get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.sites.models import Site
from app.modules.sites.routes import router as sites_router
from app.modules.users.models import User
from app.modules.users.routes import router as users_router


def _setup_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _build_client(db, user):
    app = FastAPI()
    app.include_router(sites_router)
    app.include_router(users_router)
    app.dependency_overrides[get_current_user_with_bypass] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_sites_search_returns_all_sites_for_site_user():
    db = _setup_db()
    site1 = Site(site_code="SITE001", site_name="현장1", address="서울")
    site2 = Site(site_code="SITE002", site_name="현장2", address="부산")
    db.add_all([site1, site2])
    db.flush()
    user = User(
        id=1,
        name="site-user",
        login_id="site_user_1",
        password_hash="x",
        role=Role.SITE,
        ui_type="SITE",
        site_id=site1.id,
        must_change_password=False,
    )
    db.add(user)
    db.commit()

    client = _build_client(db, SimpleNamespace(id=1, role=Role.SITE.value, site_id=site1.id))
    res = client.get("/sites/search")
    assert res.status_code == 200
    names = [row["name"] for row in res.json()]
    assert "현장1" in names
    assert "현장2" in names


def test_patch_users_me_map_preference():
    db = _setup_db()
    site1 = Site(site_code="SITE001", site_name="현장1", address="서울")
    db.add(site1)
    db.flush()
    user = User(
        id=7,
        name="site-user",
        login_id="site_user_7",
        password_hash="x",
        role=Role.SITE,
        ui_type="SITE",
        site_id=site1.id,
        must_change_password=False,
    )
    db.add(user)
    db.commit()

    client = _build_client(db, user)
    ok = client.patch("/users/me/map-preference", json={"map_preference": "TMAP"})
    assert ok.status_code == 200
    assert ok.json()["map_preference"] == "TMAP"

    bad = client.patch("/users/me/map-preference", json={"map_preference": "BAD"})
    assert bad.status_code == 400

