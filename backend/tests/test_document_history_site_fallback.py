"""SITE 전용 /documents/history 문서 폴백 병합(업로드 이력 없이 documents만 있는 경우)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.auth import get_current_user_with_bypass, get_db
from app.core.database import Base
from app.core.enums import Role
from app.modules.document_generation.models import DocumentInstance, DocumentInstanceStatus, WorkflowStatus
from app.modules.document_settings.models import DocumentRequirement, DocumentTypeMaster, SubmissionCycle
from app.modules.documents.models import Document, DocumentUploadHistory
from app.modules.documents.routes import router as documents_router
from app.modules.sites.models import Site
from app.modules.users.models import User


def _engine(tmp_path: Path, name: str):
    db_file = tmp_path / name
    eng = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    from app.modules.workers import models as worker_models  # noqa: F401
    from app.modules.documents import models as document_models  # noqa: F401
    from app.modules.approvals import models as approval_models  # noqa: F401
    from app.modules.opinions import models as opinion_models  # noqa: F401
    from app.modules.document_settings import models as document_settings_models  # noqa: F401
    from app.modules.document_generation import models as document_generation_models  # noqa: F401
    from app.modules.document_submissions import models as document_submissions_models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    return eng


def test_site_history_merges_document_without_upload_history(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "hist_fb1.db")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    site = Site(site_code="S-HFB-1", site_name="폴백 테스트 현장")
    db.add(site)
    db.flush()
    site_id = int(site.id)

    cycle = SubmissionCycle(code="C1", name="일반", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="TYPE_FB",
        name="폴백 타입",
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
        code="TYPE_FB",
        title="폴백 요구",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
    )
    db.add(req)
    db.flush()
    inst = DocumentInstance(
        site_id=site_id,
        document_type_code="TYPE_FB",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 1),
        generation_anchor_date=date(2026, 5, 1),
        due_date=date(2026, 5, 1),
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=req.id,
        workflow_status=WorkflowStatus.SUBMITTED,
        period_basis="CYCLE",
        rule_is_required=True,
    )
    db.add(inst)
    db.flush()
    doc = Document(
        document_no="FB-ONLY-1",
        title="no history row",
        document_type="TYPE_FB",
        site_id=site_id,
        submitter_user_id=1,
        current_status="SUBMITTED",
        description="",
        source_type="MANUAL",
        instance_id=inst.id,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 1),
        file_path="documents/fb_only.pdf",
        file_name="fb_only.pdf",
        file_size=1,
        uploaded_by_user_id=1,
        uploaded_at=datetime(2026, 5, 10, 8, 0, 0),
        version_no=1,
    )
    db.add(doc)
    db.add(
        User(
            id=1,
            name="site",
            login_id="site_fb",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    db.add(
        User(
            id=2,
            name="hq",
            login_id="hq_fb",
            password_hash="x",
            site_id=None,
            role=Role.HQ_SAFE,
        )
    )
    db.commit()
    req_id = int(req.id)
    doc_id = int(doc.id)
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

    site_res = client.get("/documents/history", params={"site_id": site_id, "requirement_id": req_id})
    assert site_res.status_code == 200
    body = site_res.json()
    assert body["merged_document_fallback"] is True
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["source_type"] == "current_document"
    assert item["history_id"] is None
    assert item["document_id"] == doc_id
    assert item["file_download_url"] == f"/documents/{doc_id}/file"

    app.dependency_overrides[get_current_user_with_bypass] = lambda: SimpleNamespace(
        id=2, role=Role.HQ_SAFE, site_id=None
    )
    hq_res = client.get("/documents/history", params={"site_id": site_id, "requirement_id": req_id})
    assert hq_res.status_code == 200
    hq_body = hq_res.json()
    assert hq_body["merged_document_fallback"] is False
    assert len(hq_body["items"]) == 0


def test_site_history_dedupes_when_upload_history_exists(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "hist_fb2.db")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    site = Site(site_code="S-HFB-2", site_name="중복 제거 현장")
    db.add(site)
    db.flush()
    site_id = int(site.id)
    cycle = SubmissionCycle(code="C2", name="일반", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="TYPE_FB2",
        name="타입2",
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
        code="TYPE_FB2",
        title="요구2",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
    )
    db.add(req)
    db.flush()
    inst = DocumentInstance(
        site_id=site_id,
        document_type_code="TYPE_FB2",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 1),
        generation_anchor_date=date(2026, 5, 1),
        due_date=date(2026, 5, 1),
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=req.id,
        workflow_status=WorkflowStatus.SUBMITTED,
        period_basis="CYCLE",
        rule_is_required=True,
    )
    db.add(inst)
    db.flush()
    doc = Document(
        document_no="FB-DEDUP-1",
        title="with history",
        document_type="TYPE_FB2",
        site_id=site_id,
        submitter_user_id=1,
        current_status="SUBMITTED",
        description="",
        source_type="MANUAL",
        instance_id=inst.id,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 1),
        file_path="documents/dedup.pdf",
        file_name="dedup.pdf",
        file_size=1,
        uploaded_by_user_id=1,
        uploaded_at=datetime(2026, 5, 10, 8, 0, 0),
        version_no=1,
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentUploadHistory(
            document_id=doc.id,
            instance_id=inst.id,
            version_no=1,
            action_type="UPLOAD",
            document_status="SUBMITTED",
            file_path="documents/dedup.pdf",
            file_name="dedup.pdf",
            file_size=1,
            uploaded_by_user_id=1,
            uploaded_at=datetime(2026, 5, 10, 8, 0, 0),
        )
    )
    db.add(
        User(
            id=1,
            name="site",
            login_id="site_fb2",
            password_hash="x",
            site_id=site_id,
            role=Role.SITE,
        )
    )
    db.commit()
    req_id = int(req.id)
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
    site_res = client.get("/documents/history", params={"site_id": site_id, "requirement_id": req_id})
    assert site_res.status_code == 200
    body = site_res.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["source_type"] == "upload_history"
    assert body["merged_document_fallback"] is False


def test_site_history_forbidden_other_site(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "hist_fb3.db")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    s1 = Site(site_code="S-HFB-3A", site_name="A")
    s2 = Site(site_code="S-HFB-3B", site_name="B")
    db.add_all([s1, s2])
    db.flush()
    cycle = SubmissionCycle(code="C3", name="일반", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="TYPE_FB3",
        name="타입3",
        default_cycle_id=cycle.id,
        generation_rule="DAILY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add(dt)
    db.flush()
    req = DocumentRequirement(
        site_id=s1.id,
        document_type_id=dt.id,
        code="TYPE_FB3",
        title="요구3",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
    )
    db.add(req)
    db.flush()
    db.add_all(
        [
            User(id=1, name="a", login_id="sa", password_hash="x", site_id=s1.id, role=Role.SITE),
            User(id=2, name="b", login_id="sb", password_hash="x", site_id=s2.id, role=Role.SITE),
        ]
    )
    db.commit()
    req_id = int(req.id)
    s1_id = int(s1.id)
    s2_id = int(s2.id)
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
        id=2, role=Role.SITE, site_id=s2_id
    )
    client = TestClient(app)
    res = client.get("/documents/history", params={"site_id": s1_id, "requirement_id": req_id})
    assert res.status_code == 403


def test_site_history_legacy_file_source_type(tmp_path: Path) -> None:
    engine = _engine(tmp_path, "hist_fb4.db")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    site = Site(site_code="S-HFB-4", site_name="레거시 타입 현장")
    db.add(site)
    db.flush()
    site_id = int(site.id)
    cycle = SubmissionCycle(code="C4", name="일반", sort_order=1, is_auto_generatable=True)
    db.add(cycle)
    db.flush()
    dt = DocumentTypeMaster(
        code="TYPE_LEG",
        name="공통 타입",
        default_cycle_id=cycle.id,
        generation_rule="DAILY",
        generation_value=None,
        due_offset_days=0,
        is_required_default=True,
    )
    db.add(dt)
    db.flush()
    req_a = DocumentRequirement(
        site_id=site_id,
        document_type_id=dt.id,
        code="TYPE_LEG",
        title="요구 A",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=1,
    )
    req_b = DocumentRequirement(
        site_id=site_id,
        document_type_id=dt.id,
        code="TYPE_LEG_ALT",
        title="요구 B",
        frequency="DAILY",
        is_required=True,
        is_enabled=True,
        display_order=2,
    )
    db.add_all([req_a, req_b])
    db.flush()
    inst = DocumentInstance(
        site_id=site_id,
        document_type_code="TYPE_LEG",
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 1),
        generation_anchor_date=date(2026, 5, 1),
        due_date=date(2026, 5, 1),
        status=DocumentInstanceStatus.GENERATED,
        status_reason="OK",
        selected_requirement_id=req_b.id,
        workflow_status=WorkflowStatus.SUBMITTED,
        period_basis="CYCLE",
        rule_is_required=True,
    )
    db.add(inst)
    db.flush()
    doc = Document(
        document_no="LEG-INST-1",
        title="other req selected",
        document_type="TYPE_LEG",
        site_id=site_id,
        submitter_user_id=1,
        current_status="SUBMITTED",
        description="",
        source_type="MANUAL",
        instance_id=inst.id,
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 1),
        file_path="documents/legacy_inst.pdf",
        file_name="legacy_inst.pdf",
        file_size=1,
        uploaded_by_user_id=1,
        uploaded_at=datetime(2026, 5, 11, 9, 0, 0),
        version_no=1,
    )
    db.add(doc)
    db.add(User(id=1, name="site", login_id="site_leg", password_hash="x", site_id=site_id, role=Role.SITE))
    db.commit()
    req_a_id = int(req_a.id)
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
    site_res = client.get("/documents/history", params={"site_id": site_id, "requirement_id": req_a_id})
    assert site_res.status_code == 200
    items = site_res.json()["items"]
    assert len(items) == 1
    assert items[0]["source_type"] == "legacy_file"
