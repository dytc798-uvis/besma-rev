"""GET /search/risk-library: HQ 안전 UI와 동일하게 ACCIDENT_ADMIN 접근 허용."""

from datetime import date, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_db, get_current_user_with_bypass
from app.core.database import Base
from app.core.enums import Role
from app.main import app
from app.modules.risk_library.models import RiskLibraryItem, RiskLibraryItemRevision


def test_search_risk_library_get_allows_accident_admin(tmp_path):
    db_file = tmp_path / "risk_search_route.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.risk_library import models as risk_library_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    db.add(item)
    db.flush()
    db.add(
        RiskLibraryItemRevision(
            item_id=item.id,
            revision_no=1,
            is_current=True,
            effective_from=date.today(),
            effective_to=None,
            work_category="테스트작업군",
            trade_type="테스트",
            process="미기재",
            risk_factor="테스트 위험",
            risk_cause="미기재",
            countermeasure="테스트 대책",
            risk_f=1,
            risk_s=1,
            risk_r=5,
            revised_by_user_id=None,
            revised_at=datetime.utcnow(),
            revision_note=None,
        )
    )
    db.commit()
    db.close()

    def override_get_db():
        local = TestingSessionLocal()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.ACCIDENT_ADMIN,
    )

    client = TestClient(app)
    try:
        res = client.get("/search/risk-library", params={"limit": 10, "offset": 0})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total"] == 1
        assert len(body["results"]) == 1
        assert body["results"][0]["risk_factor"] == "테스트 위험"
    finally:
        app.dependency_overrides.clear()


def test_search_risk_library_get_forbids_worker(tmp_path):
    db_file = tmp_path / "risk_search_route2.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.risk_library import models as risk_library_models  # noqa: F401
    from app.modules.sites import models as site_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        local = TestingSessionLocal()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=2,
        role=Role.WORKER,
    )

    client = TestClient(app)
    try:
        res = client.get("/search/risk-library")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()
