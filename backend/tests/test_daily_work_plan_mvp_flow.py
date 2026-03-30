import base64
from datetime import date, datetime, timedelta
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import create_user_access_token, get_current_user_with_bypass, get_db
from app.core.enums import Role
from app.core.database import Base
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_submissions.models import DocumentReviewHistory
from app.modules.document_submissions.routes import router as document_submissions_router
from app.modules.documents.models import Document
from app.modules.documents.routes import router as documents_router
from app.modules.risk_library.models import (
    DailyWorkPlanDocumentLink,
    RiskLibraryItem,
    RiskLibraryItemRevision,
    RiskLibraryKeyword,
)
from app.modules.risk_library.routes import router as daily_work_plan_router
from app.modules.sites.models import Site
from app.modules.users.models import User
from app.modules.workers.models import Employment, Person


def test_daily_work_plan_end_to_end_api_flow(tmp_path):
    db_file = tmp_path / "test_daily_work_plan.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 테이블 등록을 위해 모델 import 유지
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-DWP-001", site_name="테스트현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    user = User(
        id=1,
        name="tester",
        login_id="tester",
        password_hash="x",
        site_id=site_id,
    )
    setup_db.add(user)
    setup_db.flush()

    risk_item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    setup_db.add(risk_item)
    setup_db.flush()
    risk_item_id = risk_item.id
    risk_item_id = risk_item.id
    risk_revision = RiskLibraryItemRevision(
        item_id=risk_item.id,
        revision_no=1,
        is_current=True,
        effective_from=date.today(),
        effective_to=None,
        work_category="철근",
        trade_type="트레이",
        risk_factor="사다리 작업 중 추락",
        risk_cause="미기재",
        countermeasure="2인1조/발판고정",
        risk_f=3,
        risk_s=4,
        risk_r=12,
        revised_by_user_id=user.id,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    setup_db.add(risk_revision)
    setup_db.flush()
    setup_db.add_all(
        [
            RiskLibraryKeyword(
                risk_revision_id=risk_revision.id,
                keyword="트레이",
                weight=1.5,
            ),
            RiskLibraryKeyword(
                risk_revision_id=risk_revision.id,
                keyword="추락",
                weight=2.0,
            ),
        ]
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(daily_work_plan_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(id=1)

    client = TestClient(app)

    create_plan_res = client.post(
        "/daily-work-plans",
        json={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert create_plan_res.status_code == 201
    plan = create_plan_res.json()
    plan_id = plan["id"]
    assert plan["status"] == "DRAFT"

    create_item_res = client.post(
        f"/daily-work-plans/{plan_id}/items",
        json={
            "work_name": "트레이 설치",
            "work_description": "사다리 사용 구간 추락 위험 점검",
            "team_label": "A조",
        },
    )
    assert create_item_res.status_code == 201
    item_id = create_item_res.json()["id"]

    recommend_res = client.post(
        f"/daily-work-plan-items/{item_id}/recommend-risks",
        json={"top_n": 10},
    )
    assert recommend_res.status_code == 200
    recommend_payload = recommend_res.json()
    assert recommend_payload["recommended_count"] >= 1

    refs_res = client.get(f"/daily-work-plan-items/{item_id}/risk-refs")
    assert refs_res.status_code == 200
    refs = refs_res.json()
    assert len(refs) >= 1
    picked_revision_id = refs[0]["risk_revision_id"]

    adopt_res = client.post(
        f"/daily-work-plan-items/{item_id}/adopt-risks",
        json={"risk_revision_ids": [picked_revision_id]},
    )
    assert adopt_res.status_code == 200
    assert adopt_res.json()["adopted_count"] == 1

    refs_after_adopt_res = client.get(f"/daily-work-plan-items/{item_id}/risk-refs")
    assert refs_after_adopt_res.status_code == 200
    refs_after_adopt = refs_after_adopt_res.json()
    adopted_rows = [
        row
        for row in refs_after_adopt
        if row["risk_revision_id"] == picked_revision_id and row["is_selected"] is True
    ]
    assert adopted_rows
    assert adopted_rows[0]["link_type"] == "ADOPTED"

    confirm_first_res = client.post(f"/daily-work-plans/{plan_id}/confirm")
    assert confirm_first_res.status_code == 200
    assert confirm_first_res.json()["created"] is True

    confirm_second_res = client.post(f"/daily-work-plans/{plan_id}/confirm")
    assert confirm_second_res.status_code == 200
    assert confirm_second_res.json()["created"] is False

    confirm_list_res = client.get(f"/daily-work-plans/{plan_id}/confirmations")
    assert confirm_list_res.status_code == 200
    confirm_list = confirm_list_res.json()
    assert len(confirm_list) == 1

    plan_res = client.get(f"/daily-work-plans/{plan_id}")
    assert plan_res.status_code == 200
    assert plan_res.json()["status"] == "DRAFT"


def test_daily_work_plan_assemble_idempotent_and_submission_bridge(tmp_path):
    db_file = tmp_path / "test_daily_work_plan_assemble.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-DWP-002", site_name="Test Site")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    user = User(
        id=1,
        name="hq-safe",
        login_id="hqsafe1",
        password_hash="x",
        site_id=site_id,
        role=Role.HQ_SAFE,
    )
    setup_db.add(user)
    setup_db.flush()

    risk_item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    setup_db.add(risk_item)
    setup_db.flush()
    risk_item_id = risk_item.id
    risk_revision = RiskLibraryItemRevision(
        item_id=risk_item.id,
        revision_no=1,
        is_current=True,
        effective_from=date.today(),
        effective_to=None,
        work_category="steel",
        trade_type="tray",
        risk_factor="fall from ladder",
        risk_cause="not_specified",
        countermeasure="team work",
        risk_f=3,
        risk_s=4,
        risk_r=12,
        revised_by_user_id=user.id,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    setup_db.add(risk_revision)
    setup_db.flush()
    setup_db.add_all(
        [
            RiskLibraryKeyword(risk_revision_id=risk_revision.id, keyword="tray", weight=1.5),
            RiskLibraryKeyword(risk_revision_id=risk_revision.id, keyword="fall", weight=2.0),
        ]
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(daily_work_plan_router)
    app.include_router(document_submissions_router)
    app.include_router(documents_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.HQ_SAFE,
        site_id=site_id,
    )

    client = TestClient(app)

    create_plan_res = client.post(
        "/daily-work-plans",
        json={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert create_plan_res.status_code == 201
    plan_id = create_plan_res.json()["id"]

    create_item_res = client.post(
        f"/daily-work-plans/{plan_id}/items",
        json={
            "work_name": "tray install",
            "work_description": "ladder fall risk",
            "team_label": "A-team",
        },
    )
    assert create_item_res.status_code == 201
    item_id = create_item_res.json()["id"]

    recommend_res = client.post(
        f"/daily-work-plan-items/{item_id}/recommend-risks",
        json={"top_n": 10},
    )
    assert recommend_res.status_code == 200
    assert recommend_res.json()["recommended_count"] >= 1

    refs_res = client.get(f"/daily-work-plan-items/{item_id}/risk-refs")
    assert refs_res.status_code == 200
    refs = refs_res.json()
    assert refs
    picked_revision_id = refs[0]["risk_revision_id"]

    adopt_res = client.post(
        f"/daily-work-plan-items/{item_id}/adopt-risks",
        json={"risk_revision_ids": [picked_revision_id]},
    )
    assert adopt_res.status_code == 200
    assert adopt_res.json()["adopted_count"] == 1

    assemble_first_res = client.post(
        "/daily-work-plans/assemble-document",
        json={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert assemble_first_res.status_code == 200
    first_payload = assemble_first_res.json()
    assert first_payload["document_type_code"] == "WORKPLAN_DAILY"
    assert first_payload["workflow_status"] == WorkflowStatus.NOT_SUBMITTED
    assert first_payload["adopted_risk_revision_count"] >= 1
    assert first_payload["links_upserted"] == 1
    instance_id = first_payload["instance_id"]
    document_id = first_payload["document_id"]

    db_check = TestingSessionLocal()
    try:
        inst_count_before = db_check.query(DocumentInstance).count()
        doc_count_before = db_check.query(Document).count()
        link_count_before = db_check.query(DailyWorkPlanDocumentLink).count()
    finally:
        db_check.close()

    assemble_second_res = client.post(
        "/daily-work-plans/assemble-document",
        json={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert assemble_second_res.status_code == 200
    second_payload = assemble_second_res.json()
    assert second_payload["instance_id"] == instance_id
    assert second_payload["document_id"] == document_id
    assert second_payload["links_upserted"] == 0
    assert second_payload["workflow_status"] == WorkflowStatus.NOT_SUBMITTED

    db_check = TestingSessionLocal()
    try:
        assert db_check.query(DocumentInstance).count() == inst_count_before
        assert db_check.query(Document).count() == doc_count_before
        assert db_check.query(DailyWorkPlanDocumentLink).count() == link_count_before
        inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        assert inst is not None
        assert inst.workflow_status == WorkflowStatus.NOT_SUBMITTED
    finally:
        db_check.close()

    get_assembled_res = client.get(
        "/daily-work-plans/assembled-document",
        params={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert get_assembled_res.status_code == 200
    assembled_payload = get_assembled_res.json()
    assert assembled_payload["instance_id"] == instance_id
    assert assembled_payload["document_id"] == document_id
    assert len(assembled_payload["plans"]) == 1
    assert assembled_payload["plans"][0]["plan_id"] == plan_id

    content_res = client.get(f"/documents/{document_id}/content")
    assert content_res.status_code == 200
    content_payload = content_res.json()
    assert content_payload["document_id"] == document_id
    assert content_payload["instance_id"] == instance_id
    assert content_payload["site_id"] == site_id
    assert content_payload["work_date"] == "2026-03-18"
    assert len(content_payload["plans"]) == 1
    plan_payload = content_payload["plans"][0]
    assert plan_payload["plan_id"] == plan_id
    assert plan_payload["site_id"] == site_id
    assert plan_payload["work_date"] == "2026-03-18"
    assert plan_payload["author_user_id"] == 1
    assert len(plan_payload["items"]) == 1
    item_payload = plan_payload["items"][0]
    assert item_payload["work_name"] == "tray install"
    assert item_payload["work_description"] == "ladder fall risk"
    assert item_payload["team_label"] == "A-team"
    assert item_payload["leader_person_id"] is None
    assert len(item_payload["risks"]) == 1
    risk_payload = item_payload["risks"][0]
    assert risk_payload["risk_revision_id"] == picked_revision_id
    assert risk_payload["risk_item_id"] == risk_item_id
    assert risk_payload["risk_factor"] == "fall from ladder"
    assert risk_payload["counterplan"] == "team work"
    assert risk_payload["frequency"] == 3
    assert risk_payload["severity"] == 4
    assert risk_payload["risk_level"] == 12

    upload_res = client.post(
        "/document-submissions/upload",
        data={"instance_id": str(instance_id)},
        files={"file": ("workplan.txt", b"assembled workplan draft", "text/plain")},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["workflow_status"] == WorkflowStatus.SUBMITTED
    uploaded_doc_id = upload_res.json()["document_id"]
    assert uploaded_doc_id == document_id

    review_start_res = client.post(
        f"/documents/{document_id}/review",
        json={"action": "start_review", "comment": "start"},
    )
    assert review_start_res.status_code == 200

    review_approve_res = client.post(
        f"/documents/{document_id}/review",
        json={"action": "approve", "comment": "ok"},
    )
    assert review_approve_res.status_code == 200

    db_check = TestingSessionLocal()
    try:
        inst_after = db_check.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        assert inst_after is not None
        assert inst_after.workflow_status == WorkflowStatus.APPROVED
        history_count = (
            db_check.query(DocumentReviewHistory)
            .filter(DocumentReviewHistory.instance_id == instance_id)
            .count()
        )
        assert history_count >= 3
    finally:
        db_check.close()

    confirm_first_res = client.post(f"/daily-work-plans/{plan_id}/confirm")
    assert confirm_first_res.status_code == 200
    assert confirm_first_res.json()["created"] is True

    confirm_second_res = client.post(f"/daily-work-plans/{plan_id}/confirm")
    assert confirm_second_res.status_code == 200
    assert confirm_second_res.json()["created"] is False

    plan_res = client.get(f"/daily-work-plans/{plan_id}")
    assert plan_res.status_code == 200
    assert plan_res.json()["status"] == "DRAFT"


def test_daily_work_plan_distribution_worker_signature_with_location_and_admin_presence(tmp_path, monkeypatch):
    from app.config.settings import settings as app_settings
    monkeypatch.setattr(app_settings, "test_persona_mode", False)

    db_file = tmp_path / "test_daily_work_plan_distribution_signature.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(
        site_code="S-DWP-003",
        site_name="Signature Site",
        latitude=37.1234,
        longitude=127.1234,
        allowed_radius_m=100,
    )
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id

    admin_user = User(
        id=1,
        name="site-manager",
        login_id="site_manager",
        password_hash="x",
        site_id=site_id,
        role=Role.SITE,
    )
    worker_login_user = User(
        id=2,
        name="worker-login",
        login_id="worker01",
        password_hash="x",
        site_id=site_id,
        role=Role.WORKER,
    )
    setup_db.add(admin_user)
    setup_db.add(worker_login_user)
    setup_db.flush()

    person = Person(name="worker-1", phone_mobile="01011112222")
    person2 = Person(name="worker-2", phone_mobile="01033334444")
    setup_db.add(person)
    setup_db.add(person2)
    setup_db.flush()
    person_id = person.id
    person2_id = person2.id
    worker_login_user.person_id = person_id
    worker_login_user_id = worker_login_user.id
    employment = Employment(
        person_id=person_id,
        source_type="employee",
        site_code=site.site_code,
        is_active=True,
        hire_date=date(2026, 3, 1),
        termination_date=None,
    )
    employment2 = Employment(
        person_id=person2_id,
        source_type="employee",
        site_code=site.site_code,
        is_active=True,
        hire_date=date(2026, 3, 1),
        termination_date=None,
    )
    risk_item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    setup_db.add(risk_item)
    setup_db.flush()
    risk_revision = RiskLibraryItemRevision(
        item_id=risk_item.id,
        revision_no=1,
        is_current=True,
        effective_from=date(2026, 3, 1),
        effective_to=None,
        work_category="tbm",
        trade_type="install",
        risk_factor="낙하 위험",
        risk_cause="작업 발판 불안정",
        countermeasure="추락방지망 설치",
        risk_f=3,
        risk_s=4,
        risk_r=12,
        revised_by_user_id=admin_user.id,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    setup_db.add(risk_revision)
    setup_db.flush()
    setup_db.add(
        RiskLibraryKeyword(
            risk_revision_id=risk_revision.id,
            keyword="위험",
            weight=2.0,
        )
    )
    setup_db.add(employment)
    setup_db.add(employment2)
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(daily_work_plan_router)
    app.include_router(documents_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.SITE,
        site_id=site_id,
    )

    client = TestClient(app)

    create_plan_res = client.post(
        "/daily-work-plans",
        json={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert create_plan_res.status_code == 201
    plan_id = create_plan_res.json()["id"]

    create_item_res = client.post(
        f"/daily-work-plans/{plan_id}/items",
        json={
            "work_name": "TBM 작업",
            "work_description": "고소 작업 낙하 위험 점검",
            "team_label": "TBM-A",
        },
    )
    assert create_item_res.status_code == 201
    item_id = create_item_res.json()["id"]

    recommend_res = client.post(
        f"/daily-work-plan-items/{item_id}/recommend-risks",
        json={"top_n": 10},
    )
    assert recommend_res.status_code == 200
    refs_res = client.get(f"/daily-work-plan-items/{item_id}/risk-refs")
    assert refs_res.status_code == 200
    picked_revision_id = refs_res.json()[0]["risk_revision_id"]
    adopt_res = client.post(
        f"/daily-work-plan-items/{item_id}/adopt-risks",
        json={"risk_revision_ids": [picked_revision_id]},
    )
    assert adopt_res.status_code == 200

    assemble_res = client.post(
        "/daily-work-plans/assemble-document",
        json={"site_id": site_id, "work_date": "2026-03-18"},
    )
    assert assemble_res.status_code == 200
    document_id = assemble_res.json()["document_id"]

    distribute_res = client.post(
        "/daily-work-plans/distributions",
        json={
            "plan_id": plan_id,
            "target_date": "2026-03-18",
            "visible_from": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
            "person_ids": [person_id, person2_id],
        },
    )
    assert distribute_res.status_code == 201
    distribution_id = distribute_res.json()["id"]

    future_distribute_res = client.post(
        "/daily-work-plans/distributions",
        json={
            "plan_id": plan_id,
            "target_date": "2026-03-19",
            "visible_from": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
            "person_ids": [person_id],
        },
    )
    assert future_distribute_res.status_code == 201
    future_distribution_id = future_distribute_res.json()["id"]

    distribution_detail_res = client.get(f"/daily-work-plans/distributions/{distribution_id}")
    assert distribution_detail_res.status_code == 200
    assert distribution_detail_res.json()["tbm_started_at"] is None
    assert distribution_detail_res.json()["is_tbm_active"] is False
    workers = distribution_detail_res.json()["workers"]
    assert len(workers) == 2
    worker_token = workers[0]["access_token"]
    worker2_token = workers[1]["access_token"]

    future_distribution_detail_res = client.get(
        f"/daily-work-plans/distributions/{future_distribution_id}"
    )
    assert future_distribution_detail_res.status_code == 200
    future_workers = future_distribution_detail_res.json()["workers"]
    assert len(future_workers) == 1
    future_worker_token = future_workers[0]["access_token"]

    future_worker_detail = client.get(
        f"/worker/my-daily-work-plans/{future_distribution_id}",
        params={"access_token": future_worker_token},
    )
    assert future_worker_detail.status_code == 403
    assert future_worker_detail.json()["detail"] == "Distribution not visible yet"

    worker_detail_first = client.get(
        f"/worker/my-daily-work-plans/{distribution_id}",
        params={"access_token": worker_token},
    )
    assert worker_detail_first.status_code == 200
    first_viewed_at = worker_detail_first.json()["viewed_at"]
    assert first_viewed_at is not None
    assert worker_detail_first.json()["ack_status"] == "VIEWED"
    assert worker_detail_first.json()["is_completed"] is False

    worker_detail_second = client.get(
        f"/worker/my-daily-work-plans/{distribution_id}",
        params={"access_token": worker_token},
    )
    assert worker_detail_second.status_code == 200
    assert worker_detail_second.json()["viewed_at"] == first_viewed_at
    assert worker_detail_second.json()["ack_status"] == "VIEWED"

    worker_bearer = create_user_access_token(worker_login_user_id)
    worker_auth_headers = {"Authorization": f"Bearer {worker_bearer}"}
    worker_login_list_res = client.get(
        "/worker/my-daily-work-plans",
        headers=worker_auth_headers,
    )
    assert worker_login_list_res.status_code == 200
    assert any(row["distribution_id"] == distribution_id for row in worker_login_list_res.json())

    worker_login_detail_res = client.get(
        f"/worker/my-daily-work-plans/{distribution_id}",
        headers=worker_auth_headers,
    )
    assert worker_login_detail_res.status_code == 200
    assert worker_login_detail_res.json()["distribution_id"] == distribution_id

    fake_png_bytes = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 300)
    signature_data = "data:image/png;base64," + base64.b64encode(fake_png_bytes).decode("ascii")

    out_of_radius_sign_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign",
        json={
            "access_token": worker_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.2234,
            "lng": 127.2234,
        },
    )
    assert out_of_radius_sign_res.status_code == 403
    assert out_of_radius_sign_res.json()["detail"] == "아직 TBM이 시작되지 않았습니다. 관리자 안내 후 서명하세요."

    no_tbm_sign_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert no_tbm_sign_res.status_code == 403
    assert no_tbm_sign_res.json()["detail"] == "아직 TBM이 시작되지 않았습니다. 관리자 안내 후 서명하세요."

    start_tbm_res = client.post(f"/daily-work-plans/distributions/{distribution_id}/start-tbm")
    assert start_tbm_res.status_code == 200
    assert start_tbm_res.json()["distribution_id"] == distribution_id
    assert start_tbm_res.json()["is_tbm_active"] is True
    first_tbm_started_at = start_tbm_res.json()["tbm_started_at"]
    assert first_tbm_started_at is not None

    start_tbm_res_2 = client.post(f"/daily-work-plans/distributions/{distribution_id}/start-tbm")
    assert start_tbm_res_2.status_code == 200
    assert start_tbm_res_2.json()["distribution_id"] == distribution_id
    assert start_tbm_res_2.json()["is_tbm_active"] is True
    assert start_tbm_res_2.json()["tbm_started_at"] == first_tbm_started_at

    distribution_detail_after_tbm = client.get(f"/daily-work-plans/distributions/{distribution_id}")
    assert distribution_detail_after_tbm.status_code == 200
    assert distribution_detail_after_tbm.json()["is_tbm_active"] is True
    assert distribution_detail_after_tbm.json()["tbm_started_at"] == first_tbm_started_at

    no_admin_sign_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert no_admin_sign_res.status_code == 403
    assert no_admin_sign_res.json()["detail"] == "active_admin_presence_not_found"

    ping_res = client.post(
        "/daily-work-plans/admin-presence/ping",
        json={"site_id": site_id, "lat": 37.1234, "lng": 127.1234},
    )
    assert ping_res.status_code == 200

    out_of_radius_after_tbm_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.2234,
            "lng": 127.2234,
        },
    )
    assert out_of_radius_after_tbm_res.status_code == 403
    assert out_of_radius_after_tbm_res.json()["detail"] == "관리자가 있는 TBM장소로 이동하여 서명하세요."

    end_without_start_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-end",
        json={
            "access_token": worker2_token,
            "end_status": "NORMAL",
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert end_without_start_res.status_code == 403
    assert end_without_start_res.json()["detail"] == "start_signature_required"

    sign_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert sign_res.status_code == 200
    signed_payload = sign_res.json()
    assert signed_payload["ack_status"] == "START_SIGNED"
    assert signed_payload["start_signed_at"] is not None
    assert signed_payload["signature_hash"]
    assert signed_payload["message"] == "안전하지 않으면 작업하지 않습니다. 위험한 상황은 바로 신고바랍니다."

    worker_detail_after_start = client.get(
        f"/worker/my-daily-work-plans/{distribution_id}",
        params={"access_token": worker_token},
    )
    assert worker_detail_after_start.status_code == 200
    assert worker_detail_after_start.json()["ack_status"] == "START_SIGNED"
    assert worker_detail_after_start.json()["is_completed"] is False

    end_sign_normal_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-end",
        json={
            "access_token": worker_token,
            "end_status": "NORMAL",
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert end_sign_normal_res.status_code == 200
    assert end_sign_normal_res.json()["ack_status"] == "COMPLETED"
    assert end_sign_normal_res.json()["end_status"] == "NORMAL"
    assert end_sign_normal_res.json()["issue_flag"] is False

    sign2_start_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker2_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert sign2_start_res.status_code == 200

    end_sign_issue_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-end",
        json={
            "access_token": worker2_token,
            "end_status": "ISSUE",
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert end_sign_issue_res.status_code == 200
    assert end_sign_issue_res.json()["ack_status"] == "COMPLETED"
    assert end_sign_issue_res.json()["end_status"] == "ISSUE"
    assert end_sign_issue_res.json()["issue_flag"] is True

    worker_detail_after_end = client.get(
        f"/worker/my-daily-work-plans/{distribution_id}",
        params={"access_token": worker_token},
    )
    assert worker_detail_after_end.status_code == 200
    assert worker_detail_after_end.json()["is_completed"] is True

    tbm_summary_res = client.get(f"/documents/{document_id}/tbm-summary")
    assert tbm_summary_res.status_code == 200
    tbm_payload = tbm_summary_res.json()
    assert tbm_payload["education_count"] == 2
    assert tbm_payload["site_id"] == site_id
    assert tbm_payload["table_rows"]
    assert len(tbm_payload["top_risks"]) <= 5
    assert len(tbm_payload["participants"]) == 2
    assert tbm_payload["participants"][0]["start_signature_data"]

    re_sign_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker_token,
            "signature_data": signature_data,
            "signature_mime": "image/png",
            "lat": 37.12345,
            "lng": 127.12345,
        },
    )
    assert re_sign_res.status_code == 403
    assert re_sign_res.json()["detail"] == "already_signed"


def test_feedback_reassignment_and_hq_safety_record_flow(tmp_path, monkeypatch):
    from app.config.settings import settings as app_settings

    monkeypatch.setattr(app_settings, "test_persona_mode", True)

    db_file = tmp_path / "test_feedback_reassignment.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-DWP-004", site_name="Feedback Site", latitude=37.5, longitude=127.0)
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id

    site_user = User(
        id=1,
        name="site-manager",
        login_id="site_manager_2",
        password_hash="x",
        site_id=site_id,
        role=Role.SITE,
    )
    hq_user = User(
        id=2,
        name="hq-safe",
        login_id="hq_safe_2",
        password_hash="x",
        site_id=site_id,
        role=Role.HQ_SAFE,
    )
    worker_user = User(
        id=3,
        name="worker-user",
        login_id="worker_2",
        password_hash="x",
        site_id=site_id,
        role=Role.WORKER,
    )
    setup_db.add_all([site_user, hq_user, worker_user])
    setup_db.flush()

    person1 = Person(name="worker-alpha", phone_mobile="01011110000")
    person2 = Person(name="worker-beta", phone_mobile="01022220000")
    setup_db.add_all([person1, person2])
    setup_db.flush()
    person1_id = person1.id
    person2_id = person2.id
    worker_user.person_id = person1_id

    employment1 = Employment(
        person_id=person1_id,
        source_type="employee",
        site_code=site.site_code,
        department_name="전기팀",
        position_name="반장",
        is_active=True,
        hire_date=date(2026, 3, 1),
    )
    employment2 = Employment(
        person_id=person2_id,
        source_type="employee",
        site_code=site.site_code,
        department_name="전기팀",
        position_name="작업자",
        is_active=True,
        hire_date=date(2026, 3, 1),
    )
    setup_db.add_all([employment1, employment2])

    risk_item = RiskLibraryItem(source_scope="HQ_STANDARD", owner_site_id=None, is_active=True)
    setup_db.add(risk_item)
    setup_db.flush()
    revision = RiskLibraryItemRevision(
        item_id=risk_item.id,
        revision_no=1,
        is_current=True,
        effective_from=date(2026, 3, 1),
        effective_to=None,
        unit_work="전기 설비 설치",
        work_category="전기",
        trade_type="배관",
        process="천장슬라브 배관",
        risk_factor="사다리 작업 중 추락",
        risk_cause="작업대 미고정",
        countermeasure="작업발판 고정 및 2인1조",
        note="테스트",
        risk_f=3,
        risk_s=4,
        risk_r=12,
        revised_by_user_id=site_user.id,
        revised_at=datetime.utcnow(),
        revision_note=None,
    )
    setup_db.add(revision)
    setup_db.flush()
    setup_db.add_all(
        [
            RiskLibraryKeyword(risk_revision_id=revision.id, keyword="배관", weight=2.0),
            RiskLibraryKeyword(risk_revision_id=revision.id, keyword="추락", weight=2.0),
        ]
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(daily_work_plan_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    current_user = {"value": SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)}

    def override_current_user():
        return current_user["value"]

    app.dependency_overrides[get_current_user_with_bypass] = override_current_user
    client = TestClient(app)

    create_plan_res = client.post(
        "/daily-work-plans",
        json={"site_id": site_id, "work_date": "2026-03-20"},
    )
    assert create_plan_res.status_code == 201
    plan_id = create_plan_res.json()["id"]

    create_item_res = client.post(
        f"/daily-work-plans/{plan_id}/items",
        json={
            "work_name": "배관 작업",
            "work_description": "천장슬라브 배관 및 사다리 작업",
            "team_label": "A조",
        },
    )
    assert create_item_res.status_code == 201
    item_id = create_item_res.json()["id"]

    recommend_res = client.post(
        f"/daily-work-plan-items/{item_id}/recommend-risks",
        json={"top_n": 10},
    )
    assert recommend_res.status_code == 200

    refs_res = client.get(f"/daily-work-plan-items/{item_id}/risk-refs")
    assert refs_res.status_code == 200
    picked_revision_id = refs_res.json()[0]["risk_revision_id"]

    adopt_res = client.post(
        f"/daily-work-plan-items/{item_id}/adopt-risks",
        json={"risk_revision_ids": [picked_revision_id]},
    )
    assert adopt_res.status_code == 200

    distribute_res = client.post(
        "/daily-work-plans/distributions",
        json={
            "plan_id": plan_id,
            "target_date": "2026-03-20",
            "visible_from": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
            "person_ids": [person1_id, person2_id],
        },
    )
    assert distribute_res.status_code == 201
    distribution_id = distribute_res.json()["id"]

    start_tbm_res = client.post(f"/daily-work-plans/distributions/{distribution_id}/start-tbm")
    assert start_tbm_res.status_code == 200

    distribution_detail_res = client.get(f"/daily-work-plans/distributions/{distribution_id}")
    assert distribution_detail_res.status_code == 200
    workers = distribution_detail_res.json()["workers"]
    worker1_token = next(row["access_token"] for row in workers if row["person_id"] == person1_id)

    signature_data_a = "data:image/png;base64," + base64.b64encode(b"x" * 512).decode()
    signature_data_b = "data:image/png;base64," + base64.b64encode(b"y" * 512).decode()

    worker_start_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/sign-start",
        json={
            "access_token": worker1_token,
            "signature_data": signature_data_a,
            "signature_mime": "image/png",
            "lat": 0,
            "lng": 0,
        },
    )
    assert worker_start_res.status_code == 200

    feedback_res = client.post(
        f"/worker/my-daily-work-plans/{distribution_id}/feedback",
        json={
            "access_token": worker1_token,
            "feedback_type": "risk",
            "content": "천장 배관 구간에서 사다리 흔들림이 발생했습니다.",
            "plan_item_id": item_id,
        },
    )
    assert feedback_res.status_code == 201
    feedback_id = feedback_res.json()["id"]

    feedback_list_res = client.get(f"/daily-work-plans/distributions/{distribution_id}/feedbacks")
    assert feedback_list_res.status_code == 200
    assert feedback_list_res.json()[0]["status"] == "pending"

    review_res = client.post(
        f"/feedbacks/{feedback_id}/review",
        json={"status": "approved", "review_note": "현장 확인 완료"},
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "approved"

    promote_res = client.post(f"/feedbacks/{feedback_id}/promote-candidate")
    assert promote_res.status_code == 200
    assert promote_res.json()["inferred_risk_factor"] == "천장 배관 구간에서 사다리 흔들림이 발생했습니다."

    reassign_res = client.post(
        f"/daily-work-plans/distributions/{distribution_id}/reassign-workers",
        json={
            "person_ids": [person1_id],
            "new_work_name": "배관 보강 작업",
            "new_work_description": "사다리 대신 작업대를 사용하여 천장 배관을 재정비",
            "team_label": "A조",
            "selected_risk_revision_ids": [picked_revision_id],
            "reason": "사다리 흔들림 제보 반영",
        },
    )
    assert reassign_res.status_code == 200
    reassignment_distribution_id = reassign_res.json()["reassignment_distribution_id"]

    reassignment_detail_res = client.get(
        f"/daily-work-plans/distributions/{reassignment_distribution_id}"
    )
    assert reassignment_detail_res.status_code == 200
    assert reassignment_detail_res.json()["is_reassignment"] is True
    reassignment_worker_token = reassignment_detail_res.json()["workers"][0]["access_token"]

    reassignment_worker_detail_res = client.get(
        f"/worker/my-daily-work-plans/{reassignment_distribution_id}",
        params={"access_token": reassignment_worker_token},
    )
    assert reassignment_worker_detail_res.status_code == 200
    assert reassignment_worker_detail_res.json()["is_reassignment"] is True

    reassignment_sign_res = client.post(
        f"/worker/my-daily-work-plans/{reassignment_distribution_id}/sign-start",
        json={
            "access_token": reassignment_worker_token,
            "signature_data": signature_data_b,
            "signature_mime": "image/png",
            "lat": 0,
            "lng": 0,
        },
    )
    assert reassignment_sign_res.status_code == 200

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    safety_record_res = client.get(f"/hq-safe/workers/{person1_id}/safety-record")
    assert safety_record_res.status_code == 200
    payload = safety_record_res.json()
    assert payload["person"]["name"] == "worker-alpha"
    assert len(payload["distributions"]) >= 2
    assert any(entry["is_reassignment"] for entry in payload["distributions"])
    assert payload["feedbacks"][0]["id"] == feedback_id
    assert payload["feedbacks"][0]["candidate_status"] == "pending"
