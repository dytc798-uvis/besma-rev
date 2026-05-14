"""SITE 사이드바 `내 현장 문서` 배지는 대시보드와 동일하게 period=all 스코프를 쓴다."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.documents.routes import router as documents_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_site_badge_incomplete_matches_requirements_status_period_all(tmp_path: Path) -> None:
    db_file = tmp_path / "test_site_documents_badge.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    site = Site(site_code="S-BADGE-01", site_name="배지 테스트 현장")
    db.add(site)
    db.flush()
    site_id = site.id

    daily_c = SubmissionCycle(code="DAILY", name="일간", sort_order=10, is_auto_generatable=True)
    monthly_c = SubmissionCycle(code="MONTHLY", name="월간", sort_order=30, is_auto_generatable=True)
    db.add_all([daily_c, monthly_c])
    db.flush()

    dt_daily = DocumentTypeMaster(
        code="DAILY_DOC",
        name="일상점검",
        default_cycle_id=daily_c.id,
        generation_rule="DAILY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    dt_monthly = DocumentTypeMaster(
        code="INSPECTION",
        name="점검",
        default_cycle_id=monthly_c.id,
        generation_rule="MONTHLY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add_all([dt_daily, dt_monthly])
    db.flush()

    db.add_all(
        [
            DocumentRequirement(
                site_id=site_id,
                document_type_id=dt_daily.id,
                code="DAILY_A",
                title="일간 문서 A",
                frequency="DAILY",
                is_required=True,
                is_enabled=True,
                display_order=1,
                due_rule_text="매일",
            ),
            DocumentRequirement(
                site_id=site_id,
                document_type_id=dt_monthly.id,
                code="MONTHLY_B",
                title="월간 문서 B",
                frequency="MONTHLY",
                is_required=True,
                is_enabled=True,
                display_order=2,
                due_rule_text="월 1회",
            ),
        ]
    )
    db.add(
        User(
            id=1,
            name="site",
            login_id="site_badge_user",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    db.commit()
    db.close()

    app = FastAPI()
    app.include_router(documents_router)

    def override_get_db():
        local = TestingSessionLocal()
        try:
            yield local
        finally:
            local.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.SITE, site_id=site_id
    )
    client = TestClient(app)

    d = date(2026, 5, 10).isoformat()
    status_res = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "all", "date": d},
    )
    assert status_res.status_code == 200
    summary = status_res.json()["summary"]
    expected_incomplete = (
        summary["not_submitted_count"]
        + summary["submitted_pending_count"]
        + summary["in_review_count"]
        + summary["rejected_count"]
    )
    assert len(status_res.json()["items"]) == 2
    assert expected_incomplete == 2

    badge_res = client.get("/documents/badges/site", params={"date": d})
    assert badge_res.status_code == 200
    assert badge_res.json()["incomplete_count"] == expected_incomplete


def test_emergency_drill_requirement_half_yearly_cycle_label(tmp_path: Path) -> None:
    """시드 기준 비상훈련 보고서는 HALF_YEARLY이며 상/하반기 라벨이 붙는다."""
    from app.modules.documents.service import get_site_requirement_status

    db_file = tmp_path / "test_half_year_emergency.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    site = Site(site_code="S-HY-01", site_name="반기 테스트 현장")
    db.add(site)
    db.flush()
    half_c = SubmissionCycle(code="HALF_YEARLY", name="반기", sort_order=50, is_auto_generatable=True)
    adhoc_c = SubmissionCycle(code="ADHOC", name="수시", sort_order=90, is_auto_generatable=False)
    db.add_all([half_c, adhoc_c])
    db.flush()
    dt_acc = DocumentTypeMaster(
        code="ACCIDENT",
        name="사고",
        default_cycle_id=adhoc_c.id,
        generation_rule="ADHOC_MANUAL",
        generation_value=None,
        due_offset_days=None,
        is_required_default=False,
    )
    db.add(dt_acc)
    db.flush()
    db.add(
        DocumentRequirement(
            site_id=site.id,
            document_type_id=dt_acc.id,
            code="EMERGENCY_DRILL_REPORT",
            title="비상사태훈련보고서",
            frequency="HALF_YEARLY",
            is_required=True,
            is_enabled=True,
            display_order=1,
            due_rule_text="반기 1회",
        )
    )
    db.commit()

    rows = get_site_requirement_status(db, site_id=site.id, period="all", target_date=date(2026, 3, 15))
    row = next(r for r in rows if r.get("document_type_code") == "EMERGENCY_DRILL_REPORT")
    assert row["frequency"] == "HALF_YEARLY"
    assert "상반기" in (row.get("current_period_label") or "")

    rows2 = get_site_requirement_status(db, site_id=site.id, period="all", target_date=date(2026, 9, 1))
    row2 = next(r for r in rows2 if r.get("document_type_code") == "EMERGENCY_DRILL_REPORT")
    assert "하반기" in (row2.get("current_period_label") or "")

    db.close()
