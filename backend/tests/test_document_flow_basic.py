from __future__ import annotations

import io
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.core.auth import get_current_user_with_bypass, get_db
from app.core.datetime_utils import utc_now
from app.core.database import Base
from app.core.enums import Role
from app.modules.document_generation.models import DocumentInstance, WorkflowStatus
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.document_submissions.routes import router as document_submissions_router
from app.modules.documents.models import Document, DocumentStatus
from app.modules.documents.routes import router as documents_router
from app.modules.documents.service import get_site_requirement_status
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
    current_user = {"value": SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_doc_manager")}
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

    site_comment_res = client.post(
        f"/documents/{first_document_id}/comments",
        json={"comment_text": "현장 확인 요청 사항 메모"},
    )
    assert site_comment_res.status_code == 201
    assert site_comment_res.json()["user_role"] == "SITE"
    assert int(site_comment_res.json()["instance_id"]) == first_instance_id

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id, login_id="hq_doc_reviewer")
    hq_comment_list_res = client.get(f"/documents/{first_document_id}/comments")
    assert hq_comment_list_res.status_code == 200
    assert [row["comment_text"] for row in hq_comment_list_res.json()] == ["현장 확인 요청 사항 메모"]
    assert hq_comment_list_res.json()[0]["user_name"] == "site-manager"

    hq_comment_res = client.post(
        f"/documents/{first_document_id}/comments",
        json={"comment_text": "본사 검토 예정, 추가 자료는 승인 흐름과 별개로 남깁니다."},
    )
    assert hq_comment_res.status_code == 201
    assert hq_comment_res.json()["user_role"] == "HQ"

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

    comm_res = client.get("/documents/hq-communications", params={"limit": 20})
    assert comm_res.status_code == 200
    comm_items = comm_res.json()["items"]
    assert any(item["document_id"] == first_document_id for item in comm_items)

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_doc_manager")
    site_comment_list_res = client.get(f"/documents/{first_document_id}/comments")
    assert site_comment_list_res.status_code == 200
    timeline = site_comment_list_res.json()
    assert [row["user_role"] for row in timeline] == ["SITE", "HQ", "HQ"]
    assert [row.get("source", "comment") for row in timeline] == ["comment", "comment", "approval"]
    assert timeline[0]["comment_text"] == "현장 확인 요청 사항 메모"
    assert timeline[1]["comment_text"] == "본사 검토 예정, 추가 자료는 승인 흐름과 별개로 남깁니다."
    assert "[파일:" in timeline[2]["comment_text"] and "승인" in timeline[2]["comment_text"]

    comment_rows = [row for row in timeline if row.get("source", "comment") == "comment"]
    site_comment_id = int(comment_rows[0]["id"])
    hq_comment_id = int(comment_rows[1]["id"])

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id, login_id="hq_doc_reviewer")
    assert client.delete(f"/documents/{first_document_id}/comments/{site_comment_id}").status_code == 403

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_doc_manager")
    assert client.delete(f"/documents/{first_document_id}/comments/{hq_comment_id}").status_code == 403

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id, login_id="hq01")
    assert client.delete(f"/documents/{first_document_id}/comments/{site_comment_id}").status_code == 204
    after_delete_res = client.get(f"/documents/{first_document_id}/comments")
    assert after_delete_res.status_code == 200
    after_rows = after_delete_res.json()
    assert [row.get("source", "comment") for row in after_rows] == ["comment", "approval"]
    assert after_rows[0]["comment_text"] == "본사 검토 예정, 추가 자료는 승인 흐름과 별개로 남깁니다."
    assert after_rows[1].get("source") == "approval"

    current_user["value"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_doc_manager")

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

    current_user["value"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id, login_id="hq_doc_reviewer")
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


def test_reupload_repairs_rejected_under_review_workflow_mismatch(tmp_path: Path):
    db_file = tmp_path / "test_document_reupload_mismatch.db"
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
    site = Site(site_code="S-DOC-002", site_name="재업로드 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    setup_db.add(
        User(
            id=1,
            name="site-manager",
            login_id="site_reupload_manager",
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
    payload = upload_res.json()
    instance_id = int(payload["instance_id"])
    document_id = int(payload["document_id"])

    corrupt_db = TestingSessionLocal()
    try:
        doc = corrupt_db.query(Document).filter(Document.id == document_id).first()
        inst = corrupt_db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        assert doc is not None
        assert inst is not None
        doc.current_status = DocumentStatus.REJECTED
        doc.rejection_reason = "보완 필요"
        inst.workflow_status = WorkflowStatus.UNDER_REVIEW
        corrupt_db.add_all([doc, inst])
        corrupt_db.commit()
    finally:
        corrupt_db.close()

    reupload_res = client.post(
        "/document-submissions/upload",
        data={"instance_id": str(instance_id)},
        files={"file": ("daily_v2.txt", b"daily upload second content", "text/plain")},
    )
    assert reupload_res.status_code == 200

    verify_db = TestingSessionLocal()
    try:
        doc = verify_db.query(Document).filter(Document.id == document_id).first()
        inst = verify_db.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        assert doc is not None
        assert inst is not None
        assert doc.current_status == DocumentStatus.SUBMITTED
        assert doc.rejection_reason is None
        assert inst.workflow_status == WorkflowStatus.SUBMITTED
    finally:
        verify_db.close()


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
    req_site_manager = DocumentRequirement(
        site_id=site_id,
        document_type_id=doc_type.id,
        code="SITE_MANAGER_CHECKLIST",
        title="현장소장 점검표",
        frequency="WEEKLY",
        is_required=True,
        is_enabled=True,
        display_order=2,
        due_rule_text="주 1회 점검 후 작성",
    )
    setup_db.add(req_site_manager)
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
    site_manager_requirement_id = req_site_manager.id
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

    site_manager_upload = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "requirement_id": str(site_manager_requirement_id),
            "document_type_code": "SITE_MANAGER_CHECKLIST",
            "work_date": today,
        },
        files={"file": ("site-manager.pdf", b"check-site", "application/pdf")},
    )
    assert site_manager_upload.status_code == 200
    site_manager_document_id = int(site_manager_upload.json()["document_id"])

    db_check = TestingSessionLocal()
    try:
        tbm_doc = db_check.query(Document).filter(Document.id == tbm_document_id).first()
        supervisor_doc = db_check.query(Document).filter(Document.id == supervisor_document_id).first()
        site_manager_doc = db_check.query(Document).filter(Document.id == site_manager_document_id).first()
        assert tbm_doc is not None
        assert supervisor_doc is not None
        assert site_manager_doc is not None
        assert tbm_doc.file_name == "TBM_C18BL_260410.hwp"
        assert supervisor_doc.file_name == "관리감독자점검표_C18BL_260410.pdf"
        assert site_manager_doc.file_name == "현장소장점검표_C18BL_260410.pdf"

        supervisor_inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == supervisor_doc.instance_id).first()
        assert supervisor_inst is not None
        assert supervisor_inst.period_start.isoformat() == today
        assert supervisor_inst.period_end.isoformat() == today
        assert supervisor_inst.cycle_code == "DAILY"
        site_manager_inst = db_check.query(DocumentInstance).filter(DocumentInstance.id == site_manager_doc.instance_id).first()
        assert site_manager_inst is not None
        assert site_manager_inst.period_start.isoformat() == today
        assert site_manager_inst.period_end.isoformat() == today
        assert site_manager_inst.cycle_code == "DAILY"

        status_rows = get_site_requirement_status(
            db_check,
            site_id=site_id,
            period="all",
            target_date=date.fromisoformat(today),
        )
        sup_row = next(r for r in status_rows if r.get("document_type_code") == "SUPERVISOR_CHECKLIST")
        site_manager_row = next(r for r in status_rows if r.get("document_type_code") == "SITE_MANAGER_CHECKLIST")
        assert sup_row["frequency"] == "DAILY"
        assert site_manager_row["frequency"] == "DAILY"
        assert sup_row["latest_document_id"] == supervisor_document_id
        assert site_manager_row["latest_document_id"] == site_manager_document_id
        assert sup_row["latest_instance_id"] == supervisor_doc.instance_id
        assert site_manager_row["latest_instance_id"] == site_manager_doc.instance_id
    finally:
        db_check.close()


def test_document_replace_keeps_instance_and_increments_version(tmp_path: Path):
    db_file = tmp_path / "test_document_replace.db"
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
    site = Site(site_code="S-REPLACE-001", site_name="수정 테스트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
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
    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=1,
        role=Role.SITE,
        site_id=site_id,
        login_id="site_doc_manager",
    )
    client = TestClient(app)

    upload_res = client.post(
        "/document-submissions/upload",
        data={
            "site_id": str(site_id),
            "document_type_code": "DAILY_DOC",
            "work_date": date(2026, 4, 16).isoformat(),
        },
        files={"file": ("origin.txt", b"v1", "text/plain")},
    )
    assert upload_res.status_code == 200
    payload = upload_res.json()
    instance_id = int(payload["instance_id"])
    document_id = int(payload["document_id"])

    db_before = TestingSessionLocal()
    try:
        doc_before = db_before.query(Document).filter(Document.id == document_id).first()
        assert doc_before is not None
        before_version = int(doc_before.version_no)
        before_path = doc_before.file_path
    finally:
        db_before.close()

    replace_res = client.post(
        "/document-submissions/replace",
        data={"instance_id": str(instance_id)},
        files={"file": ("replaced.txt", b"v2", "text/plain")},
    )
    assert replace_res.status_code == 200
    replace_payload = replace_res.json()
    assert int(replace_payload["instance_id"]) == instance_id
    assert int(replace_payload["document_id"]) == document_id
    assert replace_payload["workflow_status"] == WorkflowStatus.SUBMITTED

    db_after = TestingSessionLocal()
    try:
        doc_after = db_after.query(Document).filter(Document.id == document_id).first()
        inst_after = db_after.query(DocumentInstance).filter(DocumentInstance.id == instance_id).first()
        assert doc_after is not None
        assert inst_after is not None
        assert doc_after.version_no == before_version + 1
        assert doc_after.file_path != before_path
        assert doc_after.current_status == DocumentStatus.SUBMITTED
        assert inst_after.workflow_status == WorkflowStatus.SUBMITTED
    finally:
        db_after.close()


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


def test_documents_peer_comment_count_site_sees_hq_only(tmp_path: Path):
    """SITE 티커: 타인(HQ)이 단 문서 코멘트만 집계한다."""
    db_file = tmp_path / "test_peer_comment_count.db"
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

    setup_db = TestingSessionLocal()
    site = Site(site_code="S-PEER-001", site_name="피어카운트 현장")
    setup_db.add(site)
    setup_db.flush()
    site_id = site.id
    setup_db.add_all(
        [
            User(
                id=1,
                name="site",
                login_id="site_peer",
                password_hash="x",
                site_id=site_id,
                role=Role.SITE,
            ),
            User(
                id=2,
                name="hq",
                login_id="hq_peer",
                password_hash="x",
                site_id=site_id,
                role=Role.HQ_SAFE,
            ),
        ]
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
    current = {"user": SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_peer")}
    app.dependency_overrides[get_current_user_with_bypass] = lambda: current["user"]
    client = TestClient(app)

    day = date(2026, 4, 17).isoformat()
    up = client.post(
        "/document-submissions/upload",
        data={"site_id": str(site_id), "document_type_code": "DAILY_DOC", "work_date": day},
        files={"file": ("a.txt", b"x", "text/plain")},
    )
    assert up.status_code == 200
    doc_id = int(up.json()["document_id"])

    assert client.get("/documents/comments/peer-count").json()["peer_comment_count"] == 0

    current["user"] = SimpleNamespace(id=2, role=Role.HQ_SAFE, site_id=site_id, login_id="hq_peer")
    assert (
        client.post(
            f"/documents/{doc_id}/comments",
            json={"comment_text": "본사에서 남긴 메모"},
        ).status_code
        == 201
    )

    current["user"] = SimpleNamespace(id=1, role=Role.SITE, site_id=site_id, login_id="site_peer")
    assert client.get("/documents/comments/peer-count").json()["peer_comment_count"] == 1

    future_after = (utc_now() + timedelta(days=1)).isoformat()
    assert client.get("/documents/comments/peer-count", params={"after": future_after}).json()["peer_comment_count"] == 0
