"""SITE 사이드바 배지 incomplete_count는 대시보드 '제출대기'(CURRENT_TASK+NOT_SUBMITTED)와 동일하다."""

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
from app.modules.documents.service import count_site_dashboard_pending_current_task
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_site_badge_incomplete_matches_pending_current_task(tmp_path: Path) -> None:
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
    half_c = SubmissionCycle(code="HALF_YEARLY", name="반기", sort_order=50, is_auto_generatable=True)
    db.add_all([daily_c, monthly_c, half_c])
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
    dt_half = DocumentTypeMaster(
        code="OTHER_HALF_DOC",
        name="반기 점검",
        default_cycle_id=half_c.id,
        generation_rule="HALF_YEARLY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add_all([dt_daily, dt_half])
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
                document_type_id=dt_half.id,
                code="OTHER_HALF_DOC",
                title="반기 문서 B",
                frequency="HALF_YEARLY",
                is_required=True,
                is_enabled=True,
                display_order=2,
                due_rule_text="반기 1회",
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
    items = status_res.json()["items"]
    expected_pending = count_site_dashboard_pending_current_task(items)
    assert len(items) == 2
    assert expected_pending == 1

    badge_res = client.get("/documents/badges/site", params={"date": d})
    assert badge_res.status_code == 200
    assert badge_res.json()["incomplete_count"] == expected_pending


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
    assert row["site_display_bucket"] == "CURRENT_TASK"
    assert "상반기" in (row.get("current_period_label") or "")

    rows2 = get_site_requirement_status(db, site_id=site.id, period="all", target_date=date(2026, 9, 1))
    row2 = next(r for r in rows2 if r.get("document_type_code") == "EMERGENCY_DRILL_REPORT")
    assert row2["site_display_bucket"] == "CURRENT_TASK"
    assert "하반기" in (row2.get("current_period_label") or "")

    db.close()


def test_non_emergency_half_yearly_bucket_is_periodic(tmp_path: Path) -> None:
    from app.modules.documents.service import get_site_requirement_status
    db_file = tmp_path / "test_half_year_other.db"
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
    site = Site(site_code="S-HY-02", site_name="반기 일반")
    db.add(site)
    db.flush()
    half_c = SubmissionCycle(code="HALF_YEARLY", name="반기", sort_order=50, is_auto_generatable=True)
    db.add(half_c)
    db.flush()
    dt = DocumentTypeMaster(
        code="OTHER_HALF",
        name="기타 반기",
        default_cycle_id=half_c.id,
        generation_rule="HALF_YEARLY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add(dt)
    db.flush()
    db.add(
        DocumentRequirement(
            site_id=site.id,
            document_type_id=dt.id,
            code="OTHER_HALF",
            title="기타 반기 문서",
            frequency="HALF_YEARLY",
            is_required=True,
            is_enabled=True,
            display_order=1,
            due_rule_text="반기",
        )
    )
    db.commit()
    rows = get_site_requirement_status(db, site_id=site.id, period="all", target_date=date(2026, 3, 15))
    row = next(r for r in rows if r.get("document_type_code") == "OTHER_HALF")
    assert row["site_display_bucket"] == "PERIODIC_OTHER"
    db.close()


def test_document_history_instance_fallback_and_permissions(tmp_path: Path) -> None:
    from datetime import datetime

    from app.modules.document_generation.models import DocumentInstance, DocumentInstanceStatus, WorkflowStatus
    from app.modules.documents.models import Document, DocumentUploadHistory

    db_file = tmp_path / "test_hist_inst.db"
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
    site = Site(site_code="S-HIST-1", site_name="이력 테스트")
    db.add(site)
    db.flush()
    site_id = site.id
    other_site = Site(site_code="S-HIST-2", site_name="타 현장")
    db.add(other_site)
    db.flush()
    other_site_id = other_site.id
    cycle = SubmissionCycle(code="DAILY", name="일간", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="TYPE_X",
        name="타입 X",
        default_cycle_id=cycle.id,
        generation_rule="DAILY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add(dt)
    db.flush()
    req = DocumentRequirement(
        site_id=site_id,
        document_type_id=dt.id,
        code="REQ_LEGACY",
        title="레거시 요구",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
    )
    db.add(req)
    db.flush()
    db.add_all(
        [
            User(
                id=1,
                name="site",
                login_id="site_hist2",
                password_hash="x",
                site_id=site_id,
                role=Role.SITE,
            ),
            User(
                id=2,
                name="other",
                login_id="site_other",
                password_hash="x",
                site_id=other_site_id,
                role=Role.SITE,
            ),
        ]
    )
    db.flush()
    inst = DocumentInstance(
        site_id=site_id,
        document_type_code="TYPE_X",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 1),
        generation_anchor_date=date(2026, 1, 1),
        due_date=date(2026, 1, 1),
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=req.id,
        workflow_status=WorkflowStatus.SUBMITTED,
        period_basis="AS_OF_FALLBACK",
        rule_is_required=True,
    )
    db.add(inst)
    db.flush()
    doc = Document(
        document_no="LEG-1",
        title="legacy doc",
        document_type="ORPHAN_TYPE",
        site_id=site_id,
        submitter_user_id=1,
        current_status="SUBMITTED",
        description="",
        source_type="MANUAL",
        instance_id=inst.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 1),
        file_path="x/y.pdf",
        file_name="y.pdf",
        file_size=1,
        uploaded_by_user_id=1,
        uploaded_at=datetime(2026, 1, 1, 12, 0, 0),
        version_no=1,
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentUploadHistory(
            document_id=doc.id,
            instance_id=None,
            version_no=1,
            action_type="UPLOAD",
            document_status="SUBMITTED",
            file_path="x/y.pdf",
            file_name="y.pdf",
            file_size=1,
            uploaded_by_user_id=1,
            uploaded_at=datetime(2026, 1, 1, 12, 0, 0),
        )
    )
    inst_new = DocumentInstance(
        site_id=site_id,
        document_type_code="TYPE_X",
        period_start=date(2026, 5, 14),
        period_end=date(2026, 5, 14),
        generation_anchor_date=date(2026, 5, 14),
        due_date=date(2026, 5, 14),
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=req.id,
        workflow_status=WorkflowStatus.SUBMITTED,
        period_basis="CYCLE",
        rule_is_required=True,
    )
    db.add(inst_new)
    db.flush()
    doc_new = Document(
        document_no="NEW-1",
        title="today doc",
        document_type="TYPE_X",
        site_id=site_id,
        submitter_user_id=1,
        current_status="SUBMITTED",
        description="",
        source_type="MANUAL",
        instance_id=inst_new.id,
        period_start=date(2026, 5, 14),
        period_end=date(2026, 5, 14),
        file_path="x/new.pdf",
        file_name="new.pdf",
        file_size=1,
        uploaded_by_user_id=1,
        uploaded_at=datetime(2026, 5, 14, 10, 0, 0),
        version_no=1,
    )
    db.add(doc_new)
    db.flush()
    db.add(
        DocumentUploadHistory(
            document_id=doc_new.id,
            instance_id=inst_new.id,
            version_no=1,
            action_type="UPLOAD",
            document_status="SUBMITTED",
            file_path="x/new.pdf",
            file_name="new.pdf",
            file_size=1,
            uploaded_by_user_id=1,
            uploaded_at=datetime(2026, 5, 14, 10, 0, 0),
        )
    )
    db.add(
        User(
            id=3,
            name="hq",
            login_id="hq_hist",
            password_hash="x",
            site_id=None,
            role=Role.HQ_SAFE,
        )
    )
    db.commit()
    req_id = req.id
    inst_id = inst.id
    inst_new_id = inst_new.id
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

    res_req_only = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id},
    )
    assert res_req_only.status_code == 200
    assert len(res_req_only.json()["items"]) == 2

    res_inst = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id, "document_instance_id": inst_id},
    )
    assert res_inst.status_code == 200
    assert len(res_inst.json()["items"]) == 2
    assert res_inst.json()["document_instance_id"] == inst_id

    res_new_inst = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id, "document_instance_id": inst_new_id},
    )
    assert res_new_inst.status_code == 200
    assert len(res_new_inst.json()["items"]) == 2

    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=3, role=Role.HQ_SAFE, site_id=None
    )
    hq_res = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id},
    )
    assert hq_res.status_code == 200
    assert len(hq_res.json()["items"]) == 2
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.SITE, site_id=site_id
    )

    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=2, role=Role.SITE, site_id=other_site_id
    )
    forbidden = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id},
    )
    assert forbidden.status_code == 403

    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1, role=Role.SITE, site_id=site_id
    )
    bad_inst = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id, "document_instance_id": 999999},
    )
    assert bad_inst.status_code == 404
