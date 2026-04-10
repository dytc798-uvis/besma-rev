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
from app.modules.notices.routes import router as notices_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_notices_create_list_and_comment(tmp_path: Path):
    db_file = tmp_path / "test_notices.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.notices import models as notices_models  # noqa: F401
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-NOTICE-001", site_name="공지 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    setup_db.add_all(
        [
            User(
                id=1,
                name="hq-user",
                login_id="hq_notice_user",
                password_hash="x",
                site_id=site.id,
                role=Role.HQ_SAFE,
            ),
            User(
                id=2,
                name="site-user",
                login_id="site_notice_user",
                password_hash="x",
                site_id=site.id,
                role=Role.SITE,
            ),
        ]
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(notices_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    current_user = {"value": SimpleNamespace(id=1, role=Role.HQ_SAFE, site_id=1)}
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    create_res = client.post("/notices", json={"title": "공지 제목", "body": "공지 본문"})
    assert create_res.status_code == 200
    notice_id = int(create_res.json()["id"])

    list_res = client.get("/notices")
    assert list_res.status_code == 200
    assert list_res.json()["items"][0]["title"] == "공지 제목"

    current_user["value"] = SimpleNamespace(id=2, role=Role.SITE, site_id=1)
    comment_res = client.post(f"/notices/{notice_id}/comments", json={"body": "확인했습니다."})
    assert comment_res.status_code == 200

    detail_res = client.get(f"/notices/{notice_id}")
    assert detail_res.status_code == 200
    assert len(detail_res.json()["comments"]) == 1
    assert detail_res.json()["comments"][0]["body"] == "확인했습니다."
