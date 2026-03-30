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
from app.modules.document_submissions.routes import router as document_submissions_router
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.routes import router as documents_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def test_document_upload_review_basic_flow(tmp_path: Path):
    db_file = tmp_path / "test_document_flow_basic.db"
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
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-DOC-001", site_name="문서 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    site_user = User(
        id=1,
        name="site-manager",
        login_id="site_doc_manager",
        password_hash="x",
        site_id=site_id,
        role=Role.SITE,
    )
    hq_user = User(
        id=2,
        name="hq-safe",
        login_id="hq_doc_reviewer",
        password_hash="x",
        site_id=site_id,
        role=Role.HQ_SAFE,
    )
    setup_db.add_all([site_user, hq_user])
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)
    app.include_router(documents_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    current_user = {"value": SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)}
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current_user["value"]
    client = TestClient(app)

    today = date(2026, 3, 20).isoformat()
    upload_res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_DOC",
            "work_date": today,
        },
        files={"file": ("daily.txt", b"daily upload content", "text/plain")},
    )
    assert upload_res.status_code == 200
    upload_payload = upload_res.json()
    first_instance_id = int(upload_payload["instance_id"])
    first_document_id = int(upload_payload["document_id"])

    db_check = TestingSessionLocal()
    try:
        assert db_check.query(DocumentInstance).count() == 1
        assert db_check.query(Document).count() == 1
        inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == first_instance_id).first()
        doc = db_check.query(Document).filter(Document.id == first_document_id).first()
        assert inst is not None
        assert doc is not None
        assert inst.workflow_status == WorkflowStatus.SUBMITTED
        assert doc.instance_id == inst.id
        assert doc.file_path is not None
    finally:
        db_check.close()

    upload_again_res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_DOC",
            "work_date": today,
        },
        files={"file": ("daily_v2.txt", b"daily upload second content", "text/plain")},
    )
    assert upload_again_res.status_code == 409

    list_res = client.get(
        "/documents",
        params={
            "site_id": site_id,
            "document_type": "DAILY_DOC",
            "work_date": today,
        },
    )
    assert list_res.status_code == 200
    listed = list_res.json()
    assert listed
    assert any(int(row["id"]) == first_document_id for row in listed)

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    start_review_res = client.post(
        f"/documents/{first_document_id}/review",
        json={"action": "start_review", "comment": "검토 시작"},
    )
    assert start_review_res.status_code == 200
    approve_res = client.post(
        f"/documents/{first_document_id}/review",
        json={"action": "approve", "comment": "승인"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["current_status"] == DocumentStatus.APPROVED

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)
    second_upload_res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "INSPECTION",
            "work_date": today,
        },
        files={"file": ("inspection.txt", b"inspection content", "text/plain")},
    )
    assert second_upload_res.status_code == 200
    second_document_id = int(second_upload_res.json()["document_id"])

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id)
    start_review_second_res = client.post(
        f"/documents/{second_document_id}/review",
        json={"action": "start_review", "comment": "검토 시작"},
    )
    assert start_review_second_res.status_code == 200
    reject_res = client.post(
        f"/documents/{second_document_id}/review",
        json={"action": "reject", "comment": "보완 필요"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["current_status"] == DocumentStatus.REJECTED
    assert reject_res.json()["rejection_reason"] == "보완 필요"
