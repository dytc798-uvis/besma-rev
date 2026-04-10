from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.safety_policy_goals.routes import router as safety_policy_goals_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_hq_upload_and_site_view_policy_goal(tmp_path: Path):
    db_file = tmp_path / "test_safety_policy_goals.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.safety_policy_goals import models as spg_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-SPG-001", site_name="방침목표 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add_all(
        [
            User(id=1, name="hq", login_id="hq_spg", password_hash="x", site_id=site.id, role=Role.HQ_SAFE),
            User(id=2, name="site", login_id="site_spg", password_hash="x", site_id=site.id, role=Role.SITE),
        ]
    )
    setup_db.commit()
    site_id = site.id
    setup_db.close()

    app = FastAPI()
    app.include_router(safety_policy_goals_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    current_user = {"value": SimpleNamespace(id=1, role=Role.HQ_SAFE, site_id=site_id)}
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    up_hq_policy = client.post(
        "/safety-policy-goals/upload",
        data={"scope": "HQ", "kind": "POLICY", "title": "본사 방침"},
        files={"file": ("hq_policy.txt", b"hq policy", "text/plain")},
    )
    assert up_hq_policy.status_code == 200

    up_site_target = client.post(
        "/safety-policy-goals/upload",
        data={"scope": "SITE", "kind": "TARGET", "title": "현장 목표", "site_id": str(site_id)},
        files={"file": ("site_target.txt", b"site target", "text/plain")},
    )
    assert up_site_target.status_code == 200

    current_user["value"] = SimpleNamespace(id=2, role=Role.SITE, site_id=site_id)
    site_view = client.get("/safety-policy-goals/view", params={"scope": "SITE"})
    assert site_view.status_code == 200
    assert site_view.json()["target"]["title"] == "현장 목표"

    hq_view = client.get("/safety-policy-goals/view", params={"scope": "HQ"})
    assert hq_view.status_code == 200
    assert hq_view.json()["policy"]["title"] == "본사 방침"
