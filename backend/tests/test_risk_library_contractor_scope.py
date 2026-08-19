from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.main import app
from app.modules.risk_library.models import (
    RiskLibraryContractor,
    RiskLibraryItem,
    RiskLibraryItemContractor,
    RiskLibraryItemRevision,
)
from app.modules.sites.models import Site


def _add_item(db, label: str, *, is_common: bool) -> RiskLibraryItem:
    item = RiskLibraryItem(
        source_scope="HQ_STANDARD",
        owner_site_id=None,
        is_common=is_common,
        is_active=True,
    )
    db.add(item)
    db.flush()
    db.add(
        RiskLibraryItemRevision(
            item_id=item.id,
            revision_no=1,
            is_current=True,
            effective_from=date.today(),
            unit_work="전기공사",
            work_category=f"{label} 작업",
            trade_type="전기공사",
            process=f"{label} 세부작업",
            risk_factor=f"{label} 위험요인",
            risk_cause=f"{label} 원인",
            countermeasure=f"{label} 개선대책",
            risk_f=2,
            risk_s=4,
            risk_r=8,
        )
    )
    return item


def test_site_scope_designation_and_assignment_are_limited_to_its_contractor(tmp_path):
    db_file = tmp_path / "contractor_scope.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.modules.risk_library import models as risk_library_models  # noqa: F401
    from app.modules.users import models as user_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    site = Site(site_code="TEST-001", site_name="대우 테스트 현장", contractor_name="(주) 대우건설")
    db.add(site)
    db.flush()
    daewoo = RiskLibraryContractor(
        contractor_key="대우건설",
        contractor_name="대우건설",
        evaluation_method="도급사 4×3",
        is_active=True,
    )
    lotte = RiskLibraryContractor(
        contractor_key="롯데건설",
        contractor_name="롯데건설",
        evaluation_method="회사 4×5",
        is_active=True,
    )
    db.add_all([daewoo, lotte])
    db.flush()
    common = _add_item(db, "공통", is_common=True)
    daewoo_only = _add_item(db, "대우", is_common=False)
    lotte_only = _add_item(db, "롯데", is_common=False)
    db.add_all(
        [
            RiskLibraryItemContractor(risk_item_id=daewoo_only.id, contractor_id=daewoo.id),
            RiskLibraryItemContractor(risk_item_id=lotte_only.id, contractor_id=lotte.id),
        ]
    )
    db.commit()
    site_id = site.id
    common_id = common.id
    daewoo_id = daewoo_only.id
    lotte_id = lotte_only.id
    db.close()

    def override_get_db():
        local = TestingSessionLocal()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=9001,
        role=Role.SITE,
        site_id=site_id,
    )
    client = TestClient(app)
    try:
        response = client.get(
            "/search/risk-library",
            params={"contractor": "롯데건설", "limit": 20},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["contractor_name"] == "대우건설"
        assert body["evaluation_method"] == "도급사 4×3"
        assert {row["risk_item_id"] for row in body["results"]} == {common_id, daewoo_id}

        designation = client.put(
            "/search/risk-assessment/designation",
            json={
                "inspector_name": "점검 담당",
                "verifier_name": "확인 담당",
                "appointed_on": "2026-08-19",
                "note": "현장 지정",
            },
        )
        assert designation.status_code == 200, designation.text
        assert designation.json()["inspector_name"] == "점검 담당"

        refreshed = client.get("/search/risk-library", params={"limit": 20}).json()
        assert all(row["improvement_owner_name"] == "점검 담당" for row in refreshed["results"])
        assert all(row["improvement_verifier_name"] == "확인 담당" for row in refreshed["results"])

        own_assignment = client.put(
            f"/search/risk-library/{daewoo_id}/site-assignment",
            json={"improvement_owner_name": "개선 담당", "improvement_verifier_name": "개선 확인"},
        )
        assert own_assignment.status_code == 200, own_assignment.text
        assert own_assignment.json()["improvement_owner_name"] == "개선 담당"

        other_assignment = client.put(
            f"/search/risk-library/{lotte_id}/site-assignment",
            json={"improvement_owner_name": "잘못된 담당", "improvement_verifier_name": "잘못된 확인"},
        )
        assert other_assignment.status_code == 404
    finally:
        app.dependency_overrides.clear()
