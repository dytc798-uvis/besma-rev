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
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.document_submissions.routes import router as document_submissions_router
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.routes import router as documents_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_site_hq_document_dashboard_e2e(tmp_path: Path):
    db_file = tmp_path / "test_document_dashboard_flow.db"
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
    site = Site(site_code="S-DASH-001", site_name="대시보드 테스트 현장")
    db.add(site)
    db.flush()
    site_id = site.id

    cycle = SubmissionCycle(code="DAILY", name="일간", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="DAILY_DOC",
        name="일상점검",
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
        code="DAILY_SAFETY_LOG",
        title="일일안전일지",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
        due_rule_text="매일 업무 종료 전 제출",
    )
    db.add(req)

    site_user = User(
        id=1,
        name="site-manager",
        login_id="site_dash_manager",
        password_hash="x",
        site_id=site_id,
        role=Role.SITE,
    )
    hq_user = User(
        id=2,
        name="hq-safe",
        login_id="hq_dash_reviewer",
        password_hash="x",
        site_id=site_id,
        role=Role.HQ_SAFE,
    )
    db.add_all([site_user, hq_user])
    db.commit()
    req_id = req.id
    db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)
    app.include_router(documents_router)

    def override_get_db():
        local_db = TestingSessionLocal()
        try:
            yield local_db
        finally:
            local_db.close()

    app.dependency_overrides[get_db] = override_get_db
    current_user = {"value": SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)}
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    today = date(2026, 3, 21).isoformat()
    before = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": today},
    )
    assert before.status_code == 200
    before_items = before.json()["items"]
    assert len(before_items) == 1
    assert before_items[0]["status"] == "NOT_SUBMITTED"
    week_view = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "week", "date": today},
    )
    month_view = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "month", "date": today},
    )
    assert week_view.status_code == 200
    assert month_view.status_code == 200
    assert len(week_view.json()["items"]) == 1
    assert len(month_view.json()["items"]) == 1

    upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "requirement_id": str(req_id),
            "document_type_code": "DAILY_SAFETY_LOG",
            "work_date": today,
        },
        files={"file": ("daily-log.txt", b"daily safety log", "text/plain")},
    )
    assert upload.status_code == 200
    document_id = int(upload.json()["document_id"])

    after_upload = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": today},
    )
    assert after_upload.status_code == 200
    uploaded_item = after_upload.json()["items"][0]
    assert uploaded_item["status"] == "SUBMITTED"
    assert int(uploaded_item["latest_document_id"]) == document_id
    after_upload_month = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "month", "date": today},
    )
    assert after_upload_month.status_code == 200
    assert after_upload_month.json()["items"][0]["status"] == "SUBMITTED"

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    hq_dashboard_before = client.get("/documents/hq-dashboard", params={"period": "day", "date": today})
    assert hq_dashboard_before.status_code == 200
    # SUBMITTED는 HQ에서 "검토대기(조치 필요)"로 집계되어야 한다.
    assert hq_dashboard_before.json()["pending_review_count"] == 1
    assert any(
        row["document_id"] == document_id and row["status"] == DocumentStatus.SUBMITTED
        for row in hq_dashboard_before.json().get("pending_documents", [])
    )

    start_review = client.post(
        f"/documents/{document_id}/review",
        json={"action": "start_review", "comment": "검토 시작"},
    )
    assert start_review.status_code == 200
    assert start_review.json()["current_status"] == DocumentStatus.UNDER_REVIEW

    reject = client.post(
        f"/documents/{document_id}/review",
        json={"action": "reject", "comment": "위험요인/대책 부적절"},
    )
    assert reject.status_code == 200
    assert reject.json()["current_status"] == DocumentStatus.REJECTED

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)
    after_reject = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": today},
    )
    assert after_reject.status_code == 200
    rejected_item = after_reject.json()["items"][0]
    assert rejected_item["status"] == "REJECTED"
    assert rejected_item["review_note"] == "위험요인/대책 부적절"
    # 다음날에도 최신 반려 이력은 재업로드 TODO로 보여야 한다.
    after_reject_next_day = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": date(2026, 3, 22).isoformat()},
    )
    assert after_reject_next_day.status_code == 200
    assert after_reject_next_day.json()["items"][0]["status"] == "REJECTED"

    reupload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "requirement_id": str(req_id),
            "document_type_code": "DAILY_SAFETY_LOG",
            "work_date": today,
        },
        files={"file": ("daily-log-v2.txt", b"daily safety log v2", "text/plain")},
    )
    assert reupload.status_code == 200

    after_reupload = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": today},
    )
    assert after_reupload.status_code == 200
    submitted_item = after_reupload.json()["items"][0]
    assert submitted_item["status"] == "SUBMITTED"

    history = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id},
    )
    assert history.status_code == 200
    history_items = history.json()["items"]
    assert len(history_items) >= 2
    assert any(item["status"] == "REJECTED" for item in history_items)
    assert any(item["version_no"] >= 2 for item in history_items)

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    hq_site_view = client.get(
        "/documents/hq-dashboard",
        params={"period": "day", "date": today, "site_id": site_id},
    )
    assert hq_site_view.status_code == 200
    hq_items = hq_site_view.json()["items"]
    assert any(item["site_id"] == site_id and item["status"] in {"SUBMITTED", "IN_REVIEW"} for item in hq_items)

    db_check = TestingSessionLocal()
    try:
        doc = db_check.query(Document).filter(Document.id == document_id).first()
        inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == doc.instance_id).first()
        assert doc is not None
        assert inst is not None
        assert doc.current_status in {DocumentStatus.SUBMITTED, DocumentStatus.REJECTED}
        assert inst.workflow_status in {WorkflowStatus.SUBMITTED, WorkflowStatus.REJECTED}
    finally:
        db_check.close()
