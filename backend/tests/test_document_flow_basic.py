from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
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


def _make_image_bytes(size: tuple[int, int] = (3000, 2000), color: tuple[int, int, int] = (210, 210, 210)) -> bytes:
    image = Image.new("RGB", size, color)
    out = io.BytesIO()
    image.save(out, format="JPEG")
    return out.getvalue()


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


def test_daily_upload_file_name_and_supervisor_daily_override(tmp_path: Path):
    db_file = tmp_path / "test_document_daily_name.db"
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
    site = Site(site_code="C18BL", site_name="청라 C18BL")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id

    cycle = SubmissionCycle(code="WEEKLY", name="주간", sort_order=1, is_auto_generatable=True)
    setup_db.add(cycle)
    setup_db.flush()
    doc_type = DocumentTypeMaster(
        code="INSPECTION",
        name="점검",
        default_cycle_id=cycle.id,
        generation_rule="WEEKLY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    setup_db.add(doc_type)
    setup_db.flush()

    req = DocumentRequirement(
        site_id=site_id,
        document_type_id=doc_type.id,
        code="SUPERVISOR_CHECKLIST",
        title="관리감독자 점검표",
        frequency="WEEKLY",
        is_required=True,
        is_enabled=True,
        display_order=1,
        due_rule_text="주 1회 점검 후 작성",
    )
    setup_db.add(req)
    setup_db.add(
        User(
            id=1,
            name="site-manager",
            login_id="site_doc_manager",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    setup_db.commit()
    requirement_id = req.id
    setup_db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)
    client = TestClient(app)

    today = date(2026, 4, 10).isoformat()
    tbm_upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_TBM",
            "work_date": today,
        },
        files={"file": ("tbm.hwp", b"tbm", "application/octet-stream")},
    )
    assert tbm_upload.status_code == 200
    tbm_document_id = int(tbm_upload.json()["document_id"])

    supervisor_upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "requirement_id": str(requirement_id),
            "document_type_code": "SUPERVISOR_CHECKLIST",
            "work_date": today,
        },
        files={"file": ("supervisor.pdf", b"check", "application/pdf")},
    )
    assert supervisor_upload.status_code == 200
    supervisor_document_id = int(supervisor_upload.json()["document_id"])

    db_check = TestingSessionLocal()
    try:
        tbm_doc = db_check.query(Document).filter(Document.id == tbm_document_id).first()
        supervisor_doc = db_check.query(Document).filter(Document.id == supervisor_document_id).first()
        assert tbm_doc is not None
        assert supervisor_doc is not None
        assert tbm_doc.file_name == "TBM_C18BL_260410.hwp"
        assert supervisor_doc.file_name == "SUPERVISOR_CHECKLIST_C18BL_260410.pdf"

        supervisor_inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == supervisor_doc.instance_id).first()
        assert supervisor_inst is not None
        assert supervisor_inst.period_start.isoformat() == today
        assert supervisor_inst.period_end.isoformat() == today
        assert supervisor_inst.cycle_code == "DAILY"
    finally:
        db_check.close()


def test_document_upload_rejects_file_over_10mb(tmp_path: Path):
    db_file = tmp_path / "test_document_upload_limit.db"
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
    site = Site(site_code="S-LIMIT-001", site_name="용량 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    setup_db.add(
        User(
            id=1,
            name="site-manager",
            login_id="site_limit_manager",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    setup_db.commit()
    setup_db.close()

    app = FastAPI()
    app.include_router(document_submissions_router)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(id=1, role=Role.SITE, site_id=site_id)
    client = TestClient(app)

    payload = b"x" * (10 * 1024 * 1024 + 1)
    res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_DOC",
            "work_date": date(2026, 4, 10).isoformat(),
        },
        files={"file": ("too-large.bin", payload, "application/octet-stream")},
    )
    assert res.status_code == 413


def test_document_upload_image_keeps_original_and_optimized_derivatives(tmp_path: Path):
    db_file = tmp_path / "test_document_image_derivatives.db"
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
    site = Site(site_code="IMG001", site_name="이미지 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    setup_db.add(
        User(
            id=1,
            name="site-manager",
            login_id="site_image_manager",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
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
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.SITE,
        site_id=site_id,
    )
    client = TestClient(app)

    upload_res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_DOC",
            "work_date": date(2026, 4, 12).isoformat(),
        },
        files={"file": ("photo.jpg", _make_image_bytes(), "image/jpeg")},
    )
    assert upload_res.status_code == 200
    payload = upload_res.json()
    assert payload["file_path"].endswith(".pdf")
    assert payload["original_file_path"].endswith(".jpg")
    assert payload["optimized_file_path"]

    db_check = TestingSessionLocal()
    try:
        doc = db_check.query(Document).filter(Document.id == int(payload["document_id"])).first()
        assert doc is not None
        assert doc.file_path and (settings.storage_root / doc.file_path).exists()
        assert doc.original_file_path and (settings.storage_root / doc.original_file_path).exists()
        assert doc.optimized_file_path and (settings.storage_root / doc.optimized_file_path).exists()
    finally:
        db_check.close()
