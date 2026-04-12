from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.datetime_utils import utc_now
from app.core.enums import Role
from app.modules.approvals.models import ApprovalAction, ApprovalHistory
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
    assert before_items[0]["current_cycle_status"] == "NOT_SUBMITTED"
    assert before_items[0]["current_cycle_start"] == today
    assert before_items[0]["unresolved_rejected_document_id"] is None
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

    # 과거 데이터/자동화 잔재로 APPROVE 코멘트가 REJECT보다 최신이면 반려 코멘트가 덮어써질 수 있다.
    # UI에는 REJECT 코멘트(또는 documents.rejection_reason)만 노출되어야 한다.
    noise_db = TestingSessionLocal()
    try:
        noise_db.add(
            ApprovalHistory(
                document_id=document_id,
                action_by_user_id=2,
                action_type=ApprovalAction.APPROVE,
                comment="deploy validation reject",
                action_at=utc_now() + timedelta(seconds=5),
            )
        )
        noise_db.commit()
    finally:
        noise_db.close()

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)
    after_reject = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": today},
    )
    assert after_reject.status_code == 200
    rejected_item = after_reject.json()["items"][0]
    assert rejected_item["status"] == "REJECTED"
    assert rejected_item["review_note"] == "위험요인/대책 부적절"
    assert rejected_item["current_cycle_status"] == "NOT_SUBMITTED"
    assert rejected_item["current_cycle_needs_reupload"] is True
    assert rejected_item["unresolved_rejected_document_id"] == document_id
    assert rejected_item["unresolved_rejected_review_note"] == "위험요인/대책 부적절"
    # 다음날에도 최신 반려 이력은 재업로드 TODO로 보여야 한다.
    after_reject_next_day = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": date(2026, 3, 22).isoformat()},
    )
    assert after_reject_next_day.status_code == 200
    assert after_reject_next_day.json()["items"][0]["status"] == "REJECTED"
    assert after_reject_next_day.json()["items"][0]["unresolved_rejected_document_id"] == document_id

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
    assert submitted_item["current_cycle_status"] == "SUBMITTED"
    assert submitted_item["rejected_backlog_count"] == 0

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    approve = client.post(
        f"/documents/{document_id}/review",
        json={"action": "approve", "comment": "승인 완료"},
    )
    assert approve.status_code == 200
    assert approve.json()["current_status"] == DocumentStatus.APPROVED

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)
    after_approve = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "day", "date": today},
    )
    assert after_approve.status_code == 200
    approved_item = after_approve.json()["items"][0]
    assert approved_item["current_cycle_status"] == "APPROVED"
    assert approved_item["rejected_backlog_count"] == 0

    history = client.get(
        "/documents/history",
        params={"site_id": site_id, "requirement_id": req_id},
    )
    assert history.status_code == 200
    history_items = history.json()["items"]
    assert len(history_items) >= 2
    assert any(item["status"] == "REJECTED" for item in history_items)
    rejected_history = next(item for item in history_items if item["status"] == "REJECTED")
    assert rejected_history["review_note"] == "위험요인/대책 부적절"
    assert any(item["version_no"] >= 2 for item in history_items)
    assert history_items[0]["period_start"] == today
    assert history_items[0]["period_label"] == today
    assert history_items[0]["history_file_available"] is True
    assert history_items[0]["file_download_url"].startswith("/documents/history/")

    history_file = client.get(history_items[0]["file_download_url"])
    assert history_file.status_code == 200

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    hq_site_view = client.get(
        "/documents/hq-dashboard",
        params={"period": "day", "date": today, "site_id": site_id},
    )
    assert hq_site_view.status_code == 200
    hq_items = hq_site_view.json()["items"]
    assert any(item["site_id"] == site_id and item["status"] == "APPROVED" for item in hq_items)

    db_check = TestingSessionLocal()
    try:
        doc = db_check.query(Document).filter(Document.id == document_id).first()
        inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == doc.instance_id).first()
        assert doc is not None
        assert inst is not None
        assert doc.current_status == DocumentStatus.APPROVED
        assert inst.workflow_status == WorkflowStatus.APPROVED
    finally:
        db_check.close()


def test_site_requirement_read_model_weekly_and_rolling_uploads(tmp_path: Path):
    db_file = tmp_path / "test_document_dashboard_weekly_rolling.db"
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
    site = Site(site_code="S-DASH-002", site_name="주기 테스트 현장")
    db.add(site)
    db.flush()
    site_id = site.id

    cycle = SubmissionCycle(code="GEN", name="일반", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()

    weekly_type = DocumentTypeMaster(
        code="WEEKLY_DOC",
        name="주간점검",
        default_cycle_id=cycle.id,
        generation_rule="WEEKLY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    rolling_type = DocumentTypeMaster(
        code="ADHOC_DOC",
        name="수시문서",
        default_cycle_id=cycle.id,
        generation_rule="ADHOC",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add_all([weekly_type, rolling_type])
    db.flush()

    weekly_req = DocumentRequirement(
        site_id=site_id,
        document_type_id=weekly_type.id,
        code="WEEKLY_CHECK",
        title="관리감독자 점검표",
        frequency="WEEKLY",
        is_required=True,
        is_enabled=True,
        display_order=1,
        due_rule_text="매주 금요일 제출",
    )
    rolling_req = DocumentRequirement(
        site_id=site_id,
        document_type_id=rolling_type.id,
        code="ADHOC_NOTICE",
        title="수시 안전자료",
        frequency="ROLLING",
        is_required=True,
        is_enabled=True,
        display_order=2,
        due_rule_text="요청 시 즉시 제출",
    )
    db.add_all([weekly_req, rolling_req])

    site_user = User(
        id=1,
        name="site-manager",
        login_id="site_dash_manager_two",
        password_hash="x",
        site_id=site_id,
        role=Role.SITE,
    )
    db.add(site_user)
    db.commit()
    weekly_req_id = weekly_req.id
    rolling_req_id = rolling_req.id
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

    today = date(2026, 4, 10).isoformat()

    weekly_upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "requirement_id": str(weekly_req_id),
            "document_type_code": "WEEKLY_CHECK",
            "work_date": today,
        },
        files={"file": ("weekly.pdf", b"weekly doc", "application/pdf")},
    )
    assert weekly_upload.status_code == 200

    rolling_upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "requirement_id": str(rolling_req_id),
            "document_type_code": "ADHOC_NOTICE",
            "work_date": today,
        },
        files={"file": ("rolling.pdf", b"rolling doc", "application/pdf")},
    )
    assert rolling_upload.status_code == 200

    status_res = client.get(
        "/documents/requirements/status",
        params={"site_id": site_id, "period": "all", "date": today},
    )
    assert status_res.status_code == 200
    items = {item["document_type_code"]: item for item in status_res.json()["items"]}

    weekly_item = items["WEEKLY_CHECK"]
    assert weekly_item["current_cycle_status"] == "SUBMITTED"
    assert weekly_item["site_display_bucket"] == "CURRENT_TASK"
    assert "주차" in weekly_item["current_period_label"]

    rolling_item = items["ADHOC_NOTICE"]
    assert rolling_item["current_cycle_status"] == "SUBMITTED"
    assert rolling_item["site_display_bucket"] == "CURRENT_TASK"
    assert rolling_item["current_period_label"] == today


def test_hq_document_queries_prioritize_site_id_over_site_code(tmp_path: Path):
    db_file = tmp_path / "test_hq_document_queries_prioritize_site_id.db"
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
    pilot_site = Site(site_code="SITE002", site_name="[1.팀] 청라C18BL")
    actual_site = Site(site_code="SITE999", site_name="[1.팀] 청라C18BL")
    db.add_all([pilot_site, actual_site])
    db.flush()

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
        site_id=actual_site.id,
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

    hq_user = User(
        id=2,
        name="hq-safe",
        login_id="hq_dash_reviewer",
        password_hash="x",
        site_id=actual_site.id,
        role=Role.HQ_SAFE,
    )
    site_user = User(
        id=3,
        name="site-manager",
        login_id="site_dash_manager",
        password_hash="x",
        site_id=actual_site.id,
        role=Role.SITE,
    )
    db.add_all([hq_user, site_user])
    db.commit()
    req_id = req.id
    actual_site_id = actual_site.id
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
    current_user = {"value": SimpleNamespace(id=3, role=Role.SITE, site_id=actual_site_id)}
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    today = date(2026, 4, 12).isoformat()
    upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(actual_site_id),
            "requirement_id": str(req_id),
            "document_type_code": "DAILY_SAFETY_LOG",
            "work_date": today,
        },
        files={"file": ("daily-log.txt", b"daily safety log", "text/plain")},
    )
    assert upload.status_code == 200

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=actual_site_id)

    deduped_dashboard = client.get(
        "/documents/hq-dashboard",
        params={"period": "day", "date": today},
    )
    assert deduped_dashboard.status_code == 200
    assert [row["site_id"] for row in deduped_dashboard.json()["site_summaries"]] == [actual_site_id]

    dashboard = client.get(
        "/documents/hq-dashboard",
        params={"period": "day", "date": today, "site_id": actual_site_id, "site_code": "SITE002"},
    )
    assert dashboard.status_code == 200
    assert [row["site_id"] for row in dashboard.json()["site_summaries"]] == [actual_site_id]
    assert all(item["site_id"] == actual_site_id for item in dashboard.json()["items"])

    pending = client.get(
        "/documents/hq-pending",
        params={"site_id": actual_site_id, "site_code": "SITE002"},
    )
    assert pending.status_code == 200
    assert pending.json()["count"] == 1
    assert all(item["site_id"] == actual_site_id for item in pending.json()["items"])
